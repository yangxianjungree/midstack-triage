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


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) if yaml is not None else json.load(fh)
    if not isinstance(data or {}, dict):
        raise ValueError("context-file must contain a YAML object")
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
    total = 0
    for status in (item.get("status") or {}).get("containerStatuses") or []:
        total += int(status.get("restartCount") or 0)
    return total


def pod_score(item: Dict[str, Any]) -> int:
    name = pod_name(item).lower()
    labels = ((item.get("metadata") or {}).get("labels")) or {}
    label_text = " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in labels.items())
    score = 0
    if not pod_ready(item):
        score += 50
    score += min(restart_count(item), 50)
    if "mongodb" in label_text or "mongod" in label_text:
        score += 10
    if any(token in name for token in ("mongos", "shard", "configsvr", "mongodb", "mongo")):
        score += 20
    if "operator" in name:
        score -= 20
    return score


def termination_records(item: Dict[str, Any], collected_at: str) -> List[Dict[str, Any]]:
    metadata = item.get("metadata") or {}
    pod = str(metadata.get("name") or "")
    namespace = str(metadata.get("namespace") or "")
    records: List[Dict[str, Any]] = []
    for status in (item.get("status") or {}).get("containerStatuses") or []:
        terminated = ((status.get("lastState") or {}).get("terminated")) or {}
        if not terminated:
            continue
        container_name = str(status.get("name") or "")
        records.append(
            {
                "pod_container_ref": "%s/%s" % (pod, container_name),
                "pod_ref": pod,
                "namespace": namespace,
                "container_name": container_name,
                "reason": terminated.get("reason"),
                "exit_code": terminated.get("exitCode"),
                "signal": terminated.get("signal"),
                "message": terminated.get("message"),
                "started_at": terminated.get("startedAt"),
                "finished_at": terminated.get("finishedAt"),
                "restart_count": status.get("restartCount"),
                "collected_at": collected_at,
            }
        )
    return records


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, gap: str) -> None:
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
                    "name": "describe unhealthy MongoDB pods",
                    "target": "pods",
                    "method": "kubectl describe pod",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "pods", "reason": summary, "impact": "termination detail remains incomplete"}],
            "blank_items": [],
            "evidence_gaps": [
                {
                    "gap": gap,
                    "gap_type": "critical_gap",
                    "related_stage": "directed_recollection",
                    "why_important": "Container termination reason and exit code can distinguish OOMKilled, command failure, and process crash.",
                    "affects": ["mechanism", "root_cause"],
                }
            ],
        },
        "warnings": [summary],
        "evidence_gaps": [
            {
                "gap": gap,
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "Container termination reason and exit code can distinguish OOMKilled, command failure, and process crash.",
                "affects": ["mechanism", "root_cause"],
            }
        ],
    }
    write_yaml(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.pods.describe")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(os.path.join(artifact_dir, "raw"), exist_ok=True)
    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(output_file, script_id, started_at, "kubectl command not found", "pod describe not collected")
        return 0

    pods_proc = subprocess.run([kubectl, "get", "pods", "-n", namespace, "-o", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    raw_pods_relpath = os.path.join("raw", "pods-for-describe.json")
    with open(os.path.join(artifact_dir, raw_pods_relpath), "w", encoding="utf-8") as fh:
        fh.write(pods_proc.stdout)
        if pods_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(pods_proc.stderr)
    if pods_proc.returncode != 0:
        blocked_payload(output_file, script_id, started_at, "kubectl get pods failed", "pod describe targets not resolved")
        return 0

    payload = json.loads(pods_proc.stdout or "{}")
    pods = [item for item in payload.get("items") or [] if isinstance(item, dict)]
    target_refs = [str(item) for item in ((context.get("targets") or {}).get("pod_refs") or []) if item]
    if target_refs:
        target_set = set(target_refs)
        candidates = [item for item in pods if pod_name(item) in target_set]
    else:
        candidates = pods
    selected = [item for item in sorted(candidates, key=pod_score, reverse=True) if pod_score(item) > 0][:8]
    if not selected:
        blocked_payload(output_file, script_id, started_at, "no unhealthy MongoDB pod selected", "pod describe target pods not selected")
        return 0

    finished_at = now_iso()
    artifacts: List[Dict[str, Any]] = [
        {"path": raw_pods_relpath, "kind": "raw_command_output", "description": "raw pod JSON used for describe target selection"}
    ]
    describes: List[Dict[str, Any]] = []
    terminations: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    signals: List[Dict[str, Any]] = []

    for item in selected:
        pod = pod_name(item)
        proc = subprocess.run([kubectl, "describe", "pod", "-n", namespace, pod], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        relpath = os.path.join("raw", "%s-describe.txt" % safe_name(pod))
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
            if proc.stderr:
                fh.write("\n# stderr\n")
                fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "kubectl describe pod/%s" % pod})
        if proc.returncode != 0:
            failed_items.append({"item": "pod/%s" % pod, "reason": proc.stderr.strip() or "kubectl describe failed", "impact": "termination detail may remain incomplete"})
            continue
        records = termination_records(item, finished_at)
        terminations.extend(records)
        describes.append(
            {
                "pod_ref": pod,
                "namespace": namespace,
                "artifact_path": relpath,
                "restart_count": restart_count(item),
                "phase": pod_phase(item),
                "ready": pod_ready(item),
                "termination_count": len(records),
                "collected_at": finished_at,
            }
        )
        successful_items.append({"item": "pod/%s" % pod, "source": "kubectl describe pod", "note": "%d termination record(s)" % len(records)})
        for record in records:
            exit_code = record.get("exit_code")
            if exit_code not in (None, 0, "0"):
                signals.append(
                    {
                        "signal_id": "container-terminated-nonzero",
                        "severity": "high",
                        "object_ref": "pod/%s" % pod,
                        "detail": "container/%s last terminated reason=%s exit_code=%s message=%s"
                        % (record.get("container_name"), record.get("reason"), exit_code, str(record.get("message") or "")[:300]),
                    }
                )

    status = "partial" if failed_items else "success"
    evidence_gaps: List[Dict[str, Any]] = []
    if not terminations:
        evidence_gaps.append(
            {
                "gap": "pod describe did not expose last termination details for selected unhealthy Pods",
                "gap_type": "expected_gap",
                "related_stage": "directed_recollection",
                "why_important": "Kubernetes may not retain a useful lastState for every restart loop.",
                "recommended_action": "use application file logs or node-side container logs for deeper root-cause evidence",
            }
        )

    payload_out = {
        "script_id": script_id,
        "status": status,
        "summary": "described %d unhealthy MongoDB pod(s)" % len(describes),
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "pod_describes": describes,
                "pod_terminations": terminations,
            }
        },
        "signal_bundle_patch": {
            "abnormal_signals": signals,
        },
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "describe unhealthy MongoDB pods",
                    "target": ",".join(item["pod_ref"] for item in describes),
                    "method": "kubectl describe pod",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": failed_items,
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": [],
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload_out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
