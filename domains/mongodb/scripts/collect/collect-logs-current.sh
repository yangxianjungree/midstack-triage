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
        if yaml is not None:
            data = yaml.safe_load(fh) or {}
        else:
            data = json.load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("context-file must contain a YAML object")
    return data


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


def blocked_output(output_file: str, script_id: str, started_at: str, summary: str, warnings: List[str], evidence_gaps: List[Dict[str, Any]]) -> None:
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
                    "name": "collect current pod logs",
                    "target": "logs",
                    "method": "kubectl logs",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": warnings,
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)


def pod_score(pod: Dict[str, Any]) -> int:
    metadata = pod.get("metadata") or {}
    name = str(metadata.get("name") or "").lower()
    labels = metadata.get("labels") or {}
    label_text = " ".join([str(k).lower() + "=" + str(v).lower() for k, v in labels.items()])
    score = 0
    if "bnmongo" in name or "mongodb" in label_text:
        score += 10
    if "configsvr" in name or "shard" in name or "mongos" in name:
        score += 20
    if "operator" in name:
        score -= 50
    return score


def resolve_target_pods(kubectl: str, namespace: str, target_refs: List[str], artifact_dir: str) -> List[str]:
    if target_refs:
        return target_refs
    proc = subprocess.run([kubectl, "get", "pods", "-n", namespace, "-o", "json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        return []
    raw_relpath = os.path.join("raw", "pods-for-log-resolution.json")
    with open(os.path.join(artifact_dir, raw_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    payload = json.loads(proc.stdout or "{}")
    result: List[str] = []
    for pod in sorted(payload.get("items") or [], key=pod_score, reverse=True):
        if pod_score(pod) < 10:
            continue
        name = str((pod.get("metadata") or {}).get("name") or "")
        if name and name not in result:
            result.append(name)
    return result


def line_count(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)

    script_id = str(context.get("script_id") or "mongodb.collect.logs.current")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(artifact_dir, exist_ok=True)
    raw_dir = os.path.join(artifact_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", False):
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl is not available in current runtime",
            ["capabilities.kubectl_available is false"],
            [{"gap": "current pod logs not collected", "related_stage": "signal_collection", "why_important": "logs are required to identify MongoDB runtime errors"}],
        )
        return 0

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl command not found in runtime environment",
            ["kubectl binary is missing"],
            [{"gap": "current pod logs not collected", "related_stage": "signal_collection", "why_important": "kubectl logs is required for current log collection"}],
        )
        return 0

    targets = context.get("targets") or {}
    logs_query = context.get("logs_query") or {}
    tail_lines = int(logs_query.get("tail_lines", 1000) or 1000)
    log_type = "previous" if script_id.endswith(".previous") or bool(logs_query.get("previous", False)) else "current"
    log_dir_name = "logs-%s" % log_type
    logs_dir = os.path.join(artifact_dir, "raw", log_dir_name)
    os.makedirs(logs_dir, exist_ok=True)
    target_pods = resolve_target_pods(kubectl, str(namespace), [str(item) for item in (targets.get("pod_refs") or [])], artifact_dir)
    artifacts: List[Dict[str, Any]] = [
        {
            "path": os.path.join("raw", "pods-for-log-resolution.json"),
            "kind": "raw_command_output",
            "description": "raw kubectl get pods output used to resolve log target pods",
        }
    ]
    if not target_pods:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "log target pods could not be resolved",
            ["no MongoDB related pods were detected"],
            [{"gap": "log target pods not resolved", "related_stage": "signal_collection", "why_important": "logs must be collected from target MongoDB Pods"}],
        )
        return 0

    log_records: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []

    for pod in target_pods:
        cmd = [kubectl, "logs", "-n", str(namespace), pod, "--tail=%d" % tail_lines]
        if log_type == "previous":
            cmd.append("--previous")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        log_relpath = os.path.join("raw", log_dir_name, "%s.log" % safe_name(pod))
        err_relpath = os.path.join("raw", log_dir_name, "%s.stderr" % safe_name(pod))
        with open(os.path.join(artifact_dir, log_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        with open(os.path.join(artifact_dir, err_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
        artifacts.append({"path": log_relpath, "kind": "raw_log", "description": "%s logs from pod/%s" % (log_type, pod)})
        if proc.stderr:
            artifacts.append({"path": err_relpath, "kind": "raw_command_error", "description": "kubectl logs stderr from pod/%s" % pod})
        if proc.returncode != 0:
            failed_items.append({"item": "pod/%s" % pod, "reason": proc.stderr.strip() or "kubectl logs returned non-zero exit code", "impact": "missing %s logs for this Pod" % log_type})
            evidence_gaps.append({"gap": "%s logs not collected from pod/%s" % (log_type, pod), "related_stage": "signal_collection", "why_important": "missing pod logs may hide MongoDB runtime errors"})
            continue
        log_records.append(
            {
                "pod_ref": pod,
                "namespace": namespace,
                "log_type": log_type,
                "artifact_path": log_relpath,
                "line_count": line_count(proc.stdout),
                "byte_size": len(proc.stdout.encode("utf-8")),
                "tail_lines": tail_lines,
                "collected_at": now_iso(),
            }
        )

    finished_at = now_iso()
    status = "success"
    if failed_items:
        status = "partial"
    if not log_records:
        status = "blocked"
    summary = "collected %s logs from %d pod(s)" % (log_type, len(log_records))
    warnings: List[str] = []
    if failed_items:
        warnings.append("%d pod log collection attempt(s) failed" % len(failed_items))

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "raw_logs": log_records,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect %s pod logs" % log_type,
                    "target": ",".join(target_pods),
                    "method": "kubectl logs --previous" if log_type == "previous" else "kubectl logs",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [
                {"item": "pod/%s" % item["pod_ref"], "source": "kubectl logs", "note": "%d line(s)" % item["line_count"]}
                for item in log_records
            ],
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
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
