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
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


CONFIG_PATHS = [
    "/opt/bitnami/mongodb/conf/mongodb.conf",
    "/etc/mongod.conf",
    "/etc/mongodb.conf",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) if yaml is not None else json.load(fh)
    if not isinstance(data or {}, dict):
        raise ValueError("context-file must contain a YAML object")
    return data or {}


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_yaml(path: str, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
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


def pod_name(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("name")) or "")


def pod_phase(item: Dict[str, Any]) -> str:
    return str(((item.get("status") or {}).get("phase")) or "")


def pod_score(item: Dict[str, Any]) -> int:
    name = pod_name(item).lower()
    labels = ((item.get("metadata") or {}).get("labels")) or {}
    label_text = " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in labels.items())
    score = 0
    if pod_phase(item) == "Running":
        score += 20
    if "mongodb" in label_text or "mongod" in label_text:
        score += 10
    if any(token in name for token in ("shard", "configsvr", "data", "mongodb", "mongo")):
        score += 20
    if "mongos" in name:
        score -= 10
    if "operator" in name:
        score -= 80
    return score


def run(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)


def choose_probe_pod(kubectl: str, namespace: str, target_refs: List[str], artifact_dir: str) -> Dict[str, Any]:
    proc = run([kubectl, "get", "pods", "-n", namespace, "-o", "json"])
    raw_path = os.path.join(artifact_dir, "raw", "pods-for-log-sink-discovery.json")
    os.makedirs(os.path.dirname(raw_path), exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    if proc.returncode != 0:
        return {}
    payload = json.loads(proc.stdout or "{}")
    pods = [item for item in (payload.get("items") or []) if isinstance(item, dict)]
    if target_refs:
        target_set = set(target_refs)
        scoped = [item for item in pods if pod_name(item) in target_set]
        running = [item for item in scoped if pod_phase(item) == "Running"]
        if running:
            return sorted(running, key=pod_score, reverse=True)[0]
    candidates = [item for item in pods if pod_score(item) > 0]
    running = [item for item in candidates if pod_phase(item) == "Running"]
    if running:
        return sorted(running, key=pod_score, reverse=True)[0]
    return sorted(candidates, key=pod_score, reverse=True)[0] if candidates else {}


def parse_log_config(text: str) -> Dict[str, str]:
    result = {"destination": "", "path": ""}
    in_system_log = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"^systemLog\s*:", stripped):
            in_system_log = True
            continue
        if in_system_log and re.match(r"^[A-Za-z0-9_]+\s*:", stripped) and not raw_line.startswith((" ", "\t")):
            in_system_log = False
        if not in_system_log:
            continue
        match = re.match(r"^(destination|path)\s*:\s*(.+)$", stripped)
        if match:
            result[match.group(1)] = match.group(2).strip().strip("'\"")
    return result


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, warnings: List[str], evidence_gaps: List[Dict[str, Any]]) -> None:
    finished_at = now_iso()
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
                    "name": "discover MongoDB application log sink",
                    "target": "mongodb config",
                    "method": "kubectl get pods + kubectl exec read-only config inspection",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "mongodb/log_sink", "reason": summary, "impact": "MongoDB application log source remains unknown"}],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": warnings,
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.logs.discover_sink")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")
    os.makedirs(artifact_dir, exist_ok=True)
    os.makedirs(os.path.join(artifact_dir, "raw"), exist_ok=True)
    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(
            output_file,
            script_id,
            started_at,
            "kubectl command not found in runtime environment",
            ["kubectl binary is missing"],
            [
                {
                    "gap": "MongoDB application log sink not discovered",
                    "gap_type": "critical_gap",
                    "related_stage": "directed_recollection",
                    "why_important": "When kubectl logs is too short, the MongoDB file log path is needed to continue root-cause analysis.",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    probe_pod = choose_probe_pod(kubectl, namespace, [str(item) for item in (targets.get("pod_refs") or []) if item], artifact_dir)
    if not probe_pod:
        blocked_payload(
            output_file,
            script_id,
            started_at,
            "no running MongoDB pod is available for log sink discovery",
            ["could not resolve a running MongoDB pod"],
            [
                {
                    "gap": "MongoDB application log sink not discovered",
                    "gap_type": "critical_gap",
                    "related_stage": "directed_recollection",
                    "why_important": "A healthy peer is needed to inspect MongoDB logging configuration without relying on the crashing Pod.",
                    "recommended_action": "provide a healthy peer Pod or inspect the container image/config manually",
                }
            ],
        )
        return 0

    pod = pod_name(probe_pod)
    config_records: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = [
        {
            "path": "raw/pods-for-log-sink-discovery.json",
            "kind": "raw_command_output",
            "description": "raw pod list used to select MongoDB log sink probe pod",
        }
    ]
    warnings: List[str] = []
    for path in CONFIG_PATHS:
        proc = run([kubectl, "exec", "-n", namespace, pod, "--", "sh", "-lc", "test -r %s && sed -n '1,220p' %s" % (path, path)])
        relpath = os.path.join("raw", "%s-%s.conf" % (safe_name(pod), safe_name(path)))
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
            if proc.stderr:
                fh.write("\n# stderr\n")
                fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "MongoDB config probe for pod/%s path %s" % (pod, path)})
        if proc.returncode != 0 or not proc.stdout.strip():
            continue
        parsed = parse_log_config(proc.stdout)
        parsed["config_path"] = path
        parsed["source_pod_ref"] = pod
        config_records.append(parsed)

    selected = next((item for item in config_records if item.get("destination") or item.get("path")), {})
    evidence_gaps: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    status = "success"
    summary = "discovered MongoDB log sink from pod/%s" % pod
    log_path = str(selected.get("path") or "")
    destination = str(selected.get("destination") or "")
    link_target = ""
    link_is_stdout = False
    if selected:
        successful_items.append({"item": "mongodb/log_sink", "source": "pod/%s" % pod, "note": "destination=%s path=%s" % (destination or "unknown", log_path or "unknown")})
        if log_path:
            proc = run([kubectl, "exec", "-n", namespace, pod, "--", "sh", "-lc", "ls -l %s 2>/dev/null || true; test -L %s && readlink %s || true" % (log_path, log_path, log_path)])
            relpath = os.path.join("raw", "%s-log-path-ls.txt" % safe_name(pod))
            with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
                fh.write(proc.stdout)
                if proc.stderr:
                    fh.write("\n# stderr\n")
                    fh.write(proc.stderr)
            artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "log file path inspection for pod/%s" % pod})
            link_target = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            link_is_stdout = "/dev/stdout" in link_target or "/proc/self/fd/1" in link_target
        if destination == "file" and log_path and not link_is_stdout:
            evidence_gaps.append(
                {
                    "gap": "MongoDB application logs are file-backed and not proven to be in kubectl logs",
                    "gap_type": "critical_gap",
                    "related_stage": "directed_recollection",
                    "why_important": "The root cause may only appear in the MongoDB file log, so kubectl logs alone may be insufficient.",
                    "recommended_action": "collect the file-backed MongoDB log from the mounted volume or node-side Pod volume path",
                    "affects": ["root_cause"],
                }
            )
    else:
        status = "partial"
        summary = "MongoDB log sink was not discovered from known config paths"
        failed_items.append({"item": "mongodb/log_sink", "reason": "known config paths were unreadable or missing", "impact": "application log source remains unknown"})
        evidence_gaps.append(
            {
                "gap": "MongoDB application log sink not discovered",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "When kubectl logs is too short, the MongoDB file log path is needed to continue root-cause analysis.",
                "recommended_action": "inspect container command, args, ConfigMap, or image defaults for MongoDB log configuration",
                "affects": ["root_cause"],
            }
        )

    finished_at = now_iso()
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "log_sinks": [
                    {
                        "source_pod_ref": pod,
                        "namespace": namespace,
                        "config_path": selected.get("config_path", ""),
                        "destination": destination,
                        "path": log_path,
                        "link_target": link_target,
                        "is_stdout_link": link_is_stdout,
                        "collected_at": finished_at,
                    }
                ]
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "discover MongoDB application log sink",
                    "target": "pod/%s" % pod,
                    "method": "kubectl exec read-only config inspection",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": failed_items,
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": warnings,
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
