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


def parse_cpu(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    if value.endswith("m"):
        return int(float(value[:-1] or 0))
    if value.endswith("n"):
        return int(float(value[:-1] or 0) / 1000000)
    return int(float(value) * 1000)


def parse_memory_mi(value: str) -> int:
    value = value.strip()
    if not value:
        return 0
    units = (
        ("Ki", 1 / 1024),
        ("Mi", 1),
        ("Gi", 1024),
        ("Ti", 1024 * 1024),
        ("K", 1 / 1024),
        ("M", 1),
        ("G", 1024),
    )
    for suffix, multiplier in units:
        if value.endswith(suffix):
            return int(float(value[: -len(suffix)] or 0) * multiplier)
    return int(float(value) / 1024 / 1024)


def parse_percent(value: str) -> int:
    return int(str(value).strip().rstrip("%") or 0)


def run_kubectl(cmd: List[str], artifact_dir: str, relpath: str) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    raw_path = os.path.join(artifact_dir, relpath)
    with open(raw_path, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    if proc.stderr:
        with open(raw_path + ".stderr", "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
    return proc


def parse_top_nodes(text: str, collected_at: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) < 5 or parts[0].lower() == "name":
            continue
        records.append(
            {
                "node_ref": parts[0],
                "cpu_millicores": parse_cpu(parts[1]),
                "cpu_percent": parse_percent(parts[2]),
                "memory_mi": parse_memory_mi(parts[3]),
                "memory_percent": parse_percent(parts[4]),
                "collected_at": collected_at,
            }
        )
    return records


def parse_top_pods(text: str, namespace: str, collected_at: str) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for raw in text.splitlines():
        parts = raw.split()
        if len(parts) < 3 or parts[0].lower() == "name":
            continue
        records.append(
            {
                "pod_ref": parts[0],
                "namespace": namespace,
                "cpu_millicores": parse_cpu(parts[1]),
                "memory_mi": parse_memory_mi(parts[2]),
                "collected_at": collected_at,
            }
        )
    return records


def output_payload(
    output_file: str,
    script_id: str,
    started_at: str,
    status: str,
    summary: str,
    artifacts: List[Dict[str, str]],
    resource_metrics: Dict[str, Any],
    evidence_gaps: List[Dict[str, Any]],
) -> None:
    finished_at = now_iso()
    successful_items = []
    if resource_metrics.get("nodes") or resource_metrics.get("pods"):
        successful_items.append(
            {
                "item": "resource_metrics",
                "source": "kubectl top",
                "note": "%d node metric(s), %d pod metric(s)" % (len(resource_metrics.get("nodes") or []), len(resource_metrics.get("pods") or [])),
            }
        )
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "resource_metrics": resource_metrics,
            }
        },
        "signal_bundle_patch": {
            "resource_metrics": {
                "node_count": len(resource_metrics.get("nodes") or []),
                "pod_count": len(resource_metrics.get("pods") or []),
                "metrics_available": bool(resource_metrics.get("nodes") or resource_metrics.get("pods")),
            }
        },
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect Kubernetes resource metrics",
                    "target": "nodes,pods",
                    "method": "kubectl top nodes/pods",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": [item["gap"] for item in evidence_gaps],
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.resources.metrics")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(os.path.join(artifact_dir, "raw"), exist_ok=True)
    resource_metrics = {"nodes": [], "pods": []}
    artifacts: List[Dict[str, str]] = []
    evidence_gaps: List[Dict[str, Any]] = []

    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", False):
        evidence_gaps.append(
            {
                "gap": "resource metrics not collected because kubectl is unavailable",
                "gap_type": "expected_gap",
                "related_stage": "signal_collection",
                "why_important": "CPU and memory pressure can explain scheduling, readiness, and latency symptoms.",
            }
        )
        output_payload(output_file, script_id, started_at, "partial", "resource metrics not collected", artifacts, resource_metrics, evidence_gaps)
        return 0

    kubectl = shutil.which("kubectl")
    if not kubectl:
        evidence_gaps.append(
            {
                "gap": "resource metrics not collected because kubectl command is missing",
                "gap_type": "expected_gap",
                "related_stage": "signal_collection",
                "why_important": "CPU and memory pressure can explain scheduling, readiness, and latency symptoms.",
            }
        )
        output_payload(output_file, script_id, started_at, "partial", "resource metrics not collected", artifacts, resource_metrics, evidence_gaps)
        return 0

    nodes_proc = run_kubectl([kubectl, "top", "nodes", "--no-headers"], artifact_dir, os.path.join("raw", "top-nodes.txt"))
    pods_proc = run_kubectl([kubectl, "top", "pods", "-n", str(namespace), "--no-headers"], artifact_dir, os.path.join("raw", "top-pods.txt"))
    if nodes_proc.returncode == 0:
        resource_metrics["nodes"] = parse_top_nodes(nodes_proc.stdout, now_iso())
        artifacts.append({"path": os.path.join("raw", "top-nodes.txt"), "kind": "raw_command_output", "description": "kubectl top nodes output"})
    if pods_proc.returncode == 0:
        resource_metrics["pods"] = parse_top_pods(pods_proc.stdout, str(namespace), now_iso())
        artifacts.append({"path": os.path.join("raw", "top-pods.txt"), "kind": "raw_command_output", "description": "kubectl top pods output"})

    if nodes_proc.returncode != 0 and pods_proc.returncode != 0:
        detail = (nodes_proc.stderr or pods_proc.stderr or "kubectl top failed").strip()
        evidence_gaps.append(
            {
                "gap": "resource metrics API unavailable: %s" % detail,
                "gap_type": "expected_gap",
                "related_stage": "signal_collection",
                "why_important": "Metrics-server is optional; missing live CPU/memory metrics limits resource-pressure confirmation but should not block triage.",
                "recommended_action": "check metrics-server or use platform monitoring for CPU/memory around the incident window",
            }
        )
    elif nodes_proc.returncode != 0 or pods_proc.returncode != 0:
        detail = (nodes_proc.stderr if nodes_proc.returncode != 0 else pods_proc.stderr).strip()
        evidence_gaps.append(
            {
                "gap": "resource metrics partially unavailable: %s" % detail,
                "gap_type": "expected_gap",
                "related_stage": "signal_collection",
                "why_important": "Partial CPU/memory metrics reduce resource-pressure confidence.",
            }
        )

    status = "success" if not evidence_gaps else "partial"
    summary = "collected resource metrics for %d node(s) and %d pod(s)" % (len(resource_metrics["nodes"]), len(resource_metrics["pods"]))
    output_payload(output_file, script_id, started_at, status, summary, artifacts, resource_metrics, evidence_gaps)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
