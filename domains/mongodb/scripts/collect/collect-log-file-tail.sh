#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 --context-file <path> --output-file <path> --artifact-dir <path>" >&2
}

CONTEXT_FILE=""
OUTPUT_FILE=""
ARTIFACT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context-file)
      CONTEXT_FILE="${2:-}"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CONTEXT_FILE" || -z "$OUTPUT_FILE" || -z "$ARTIFACT_DIR" ]]; then
  usage
  exit 1
fi

python3 - "$CONTEXT_FILE" "$OUTPUT_FILE" "$ARTIFACT_DIR" <<'PY'
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


DISCOVER_SCRIPT_ID = "mongodb.collect.logs.discover_sink"
PATTERNS = [
    ("fatal", re.compile(r"\b(fatal|panic|segmentation fault|unclean shutdown|aborting)\b", re.I)),
    ("storage", re.compile(r"\b(wiredtiger|journal|corrupt|bad magic|no space left|filesystem|fsync)\b", re.I)),
    ("error", re.compile(r"\b(error|exception|failed|failure|assertion)\b", re.I)),
    ("resource", re.compile(r"\b(oom|killed|memory|disk|too many open files)\b", re.I)),
    ("timeout", re.compile(r"\b(timeout|timed out|deadline)\b", re.I)),
    ("connection", re.compile(r"\b(connection|network|socket|refused|reset)\b", re.I)),
    ("auth", re.compile(r"\b(auth|authentication|authorized|unauthorized|permission)\b", re.I)),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) if yaml is not None else json.load(fh)
    if not isinstance(data or {}, dict):
        return {}
    return data or {}


def write_yaml(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if yaml is not None:
            yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)
        else:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")


def make_action_id(script_id: str) -> str:
    return script_id.replace(".", "-")


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def run(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)


def classify(line: str) -> str:
    for label, pattern in PATTERNS:
        if pattern.search(line):
            return label
    return ""


def scan_highlights(pod_ref: str, log_type: str, text: str, limit: int = 50) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        category = classify(line)
        if not category:
            continue
        highlights.append(
            {
                "pod_ref": pod_ref,
                "log_type": log_type,
                "line_no": line_no,
                "category": category,
                "message": line[:1000],
            }
        )
        if len(highlights) >= limit:
            break
    return highlights


def discover_output_path(context: Dict[str, Any]) -> str:
    inputs = context.get("inputs") or {}
    files = inputs.get("script_output_files") or {}
    return str(files.get(DISCOVER_SCRIPT_ID) or "")


def log_sinks_from_discover(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    output = load_yaml(path)
    details = ((output.get("structured_record_patch") or {}).get("details")) or {}
    sinks = details.get("log_sinks") or []
    return [item for item in sinks if isinstance(item, dict)]


def selected_log_path(sinks: List[Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
    for sink in sinks:
        path = str(sink.get("path") or "")
        if path and not bool(sink.get("is_stdout_link")):
            return path, sink
    for sink in sinks:
        path = str(sink.get("path") or "")
        if path:
            return path, sink
    return "", {}


def pod_name(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("name")) or "")


def pod_phase(item: Dict[str, Any]) -> str:
    return str(((item.get("status") or {}).get("phase")) or "")


def pod_ready(item: Dict[str, Any]) -> bool:
    for condition in (item.get("status") or {}).get("conditions") or []:
        if condition.get("type") == "Ready":
            return condition.get("status") == "True"
    return False


def restart_count(item: Dict[str, Any]) -> int:
    return sum(int(status.get("restartCount") or 0) for status in (item.get("status") or {}).get("containerStatuses") or [])


def labels_text(item: Dict[str, Any]) -> str:
    labels = ((item.get("metadata") or {}).get("labels")) or {}
    return " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in labels.items())


def pod_score(item: Dict[str, Any], target_refs: List[str]) -> int:
    name = pod_name(item).lower()
    label_text = labels_text(item)
    score = 0
    if pod_name(item) in set(target_refs):
        score += 30
    if not pod_ready(item):
        score += 30
    score += min(restart_count(item), 50)
    if "mongodb" in label_text or "mongod" in label_text:
        score += 10
    if any(token in name for token in ("shard", "configsvr", "mongodb", "mongo")):
        score += 20
    if "mongos" in name:
        score += 5
    if "operator" in name:
        score -= 80
    return score


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, gap: str, action: str = "") -> None:
    finished_at = now_iso()
    evidence_gap = {
        "gap": gap,
        "gap_type": "critical_gap",
        "related_stage": "directed_recollection",
        "why_important": "MongoDB file logs can contain the direct process-internal fatal error that is absent from short kubectl logs.",
        "recommended_action": action or "discover MongoDB log sink first, then collect the file-backed log tail",
        "affects": ["root_cause"],
    }
    payload = {
        "script_id": script_id,
        "status": "blocked",
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": [],
        "structured_record_patch": {},
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect MongoDB file log tail",
                    "target": "mongodb file log",
                    "method": "kubectl exec read-only tail",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "mongodb/file_log", "reason": summary, "impact": "MongoDB process-internal root-cause evidence remains missing"}],
            "blank_items": [],
            "evidence_gaps": [evidence_gap],
        },
        "warnings": [summary],
        "evidence_gaps": [evidence_gap],
    }
    write_yaml(output_file, payload)


def success_noop_payload(output_file: str, script_id: str, started_at: str, summary: str, item_note: str) -> None:
    finished_at = now_iso()
    payload = {
        "script_id": script_id,
        "status": "success",
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": [],
        "structured_record_patch": {},
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect MongoDB file log tail",
                    "target": "mongodb file log",
                    "method": "kubectl exec read-only tail",
                    "status": "success",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [{"item": "mongodb/file_log", "source": "log sink discovery", "note": item_note}],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": [],
        },
        "warnings": [],
        "evidence_gaps": [],
    }
    write_yaml(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.logs.file_tail")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")

    discover_path = discover_output_path(context)
    sinks = log_sinks_from_discover(discover_path)
    log_path, sink = selected_log_path(sinks)
    if not log_path:
        blocked_payload(
            output_file,
            script_id,
            started_at,
            "MongoDB log file path was not available from discover_log_sink",
            "MongoDB file log tail not collected because log sink discovery did not produce a readable path",
            "run mongodb.collect.logs.discover_sink successfully before file log tail collection",
        )
        return 0
    if bool(sink.get("is_stdout_link")):
        success_noop_payload(
            output_file,
            script_id,
            started_at,
            "MongoDB log path points to stdout",
            "discovered log path links to stdout; kubectl logs is the primary application log source",
        )
        return 0

    os.makedirs(os.path.join(artifact_dir, "raw", "logs-file-tail"), exist_ok=True)
    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(output_file, script_id, started_at, "kubectl command not found", "MongoDB file log tail not collected")
        return 0

    pods_proc = run([kubectl, "get", "pods", "-n", namespace, "-o", "json"], timeout=45)
    pods_relpath = os.path.join("raw", "pods-for-file-log-tail.json")
    with open(os.path.join(artifact_dir, pods_relpath), "w", encoding="utf-8") as fh:
        fh.write(pods_proc.stdout)
        if pods_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(pods_proc.stderr)
    if pods_proc.returncode != 0:
        blocked_payload(output_file, script_id, started_at, "kubectl get pods failed", "MongoDB file log tail target pods not resolved")
        return 0

    pods = [item for item in (json.loads(pods_proc.stdout or "{}").get("items") or []) if isinstance(item, dict)]
    target_refs = [str(item) for item in ((context.get("targets") or {}).get("pod_refs") or []) if item]
    selected = [item for item in sorted(pods, key=lambda pod: pod_score(pod, target_refs), reverse=True) if pod_score(item, target_refs) > 0][:8]
    if not selected:
        blocked_payload(output_file, script_id, started_at, "no MongoDB pod selected for file log tail", "MongoDB file log tail target pods not selected")
        return 0

    artifacts: List[Dict[str, Any]] = [
        {"path": pods_relpath, "kind": "raw_command_output", "description": "raw pod JSON used to select file log tail targets"}
    ]
    raw_logs: List[Dict[str, Any]] = []
    highlights: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    blank_items: List[Dict[str, Any]] = []

    for pod in selected:
        pod_ref = pod_name(pod)
        shell = "test -r %s && tail -n 400 %s" % (shlex.quote(log_path), shlex.quote(log_path))
        proc = run([kubectl, "exec", "-n", namespace, pod_ref, "--", "sh", "-lc", shell], timeout=30)
        relpath = os.path.join("raw", "logs-file-tail", "%s.log" % safe_name(pod_ref))
        errpath = os.path.join("raw", "logs-file-tail", "%s.stderr" % safe_name(pod_ref))
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        with open(os.path.join(artifact_dir, errpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_log", "description": "MongoDB file log tail from pod/%s path %s" % (pod_ref, log_path)})
        if proc.stderr:
            artifacts.append({"path": errpath, "kind": "raw_command_error", "description": "file log tail stderr from pod/%s" % pod_ref})
        if proc.returncode != 0:
            failed_items.append({"item": "pod/%s" % pod_ref, "reason": proc.stderr.strip() or "file log tail failed", "impact": "missing file-backed MongoDB log for this pod"})
            continue
        line_count = len(proc.stdout.splitlines()) if proc.stdout else 0
        if line_count == 0:
            blank_items.append({"item": "pod/%s file log" % pod_ref, "reason": "file log tail returned zero lines", "impact": "file log may be empty or not the active log source"})
        pod_highlights = scan_highlights(pod_ref, "file_tail", proc.stdout)
        highlights.extend(pod_highlights)
        raw_logs.append(
            {
                "pod_ref": pod_ref,
                "namespace": namespace,
                "log_type": "file_tail",
                "artifact_path": relpath,
                "source_path": log_path,
                "line_count": line_count,
                "byte_size": len(proc.stdout.encode("utf-8")),
                "tail_lines": 400,
                "highlight_count": len(pod_highlights),
                "collected_at": now_iso(),
            }
        )
        successful_items.append({"item": "pod/%s file log" % pod_ref, "source": log_path, "note": "%d line(s), %d highlight(s)" % (line_count, len(pod_highlights))})

    finished_at = now_iso()
    evidence_gaps: List[Dict[str, Any]] = []
    if not raw_logs:
        evidence_gaps.append(
            {
                "gap": "MongoDB file log tail could not be collected from selected Pods",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "Without file-backed MongoDB logs, root-cause claims for process-internal startup failure remain unsupported.",
                "recommended_action": "collect the log file from the mounted volume or node-side pod volume path",
                "affects": ["root_cause"],
            }
        )
    elif not highlights:
        evidence_gaps.append(
            {
                "gap": "MongoDB file log tail did not include fatal/error highlights",
                "gap_type": "expected_gap",
                "related_stage": "directed_recollection",
                "why_important": "The collected file tail may not cover the failure window or the active log path may differ by pod.",
                "recommended_action": "extend file log window or collect node-side rotated logs if root-cause evidence is still required",
            }
        )

    status = "blocked" if not raw_logs else ("partial" if failed_items or evidence_gaps else "success")
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": "collected MongoDB file log tail from %d pod(s)" % len(raw_logs),
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "raw_logs": raw_logs,
                "processed_logs": {
                    "file_tail_highlights": highlights,
                    "file_tail_highlight_count": len(highlights),
                    "collected_at": finished_at,
                },
            }
        },
        "signal_bundle_patch": {
            "log_highlights": highlights,
        },
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect MongoDB file log tail",
                    "target": ",".join(item["pod_ref"] for item in raw_logs),
                    "method": "kubectl exec read-only tail %s" % log_path,
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": failed_items,
            "blank_items": blank_items,
            "evidence_gaps": evidence_gaps,
        },
        "warnings": [],
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
