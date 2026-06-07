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


def condition_map(node: Dict[str, Any]) -> Dict[str, str]:
    conditions = (node.get("status") or {}).get("conditions") or []
    return {str(item.get("type")): str(item.get("status")) for item in conditions if item.get("type")}


def node_addresses(node: Dict[str, Any], address_type: str) -> List[str]:
    addresses = (node.get("status") or {}).get("addresses") or []
    return [str(item.get("address")) for item in addresses if item.get("type") == address_type and item.get("address")]


def status_hint(node: Dict[str, Any]) -> str:
    conditions = condition_map(node)
    if conditions.get("Ready") != "True":
        return "unhealthy"
    pressure_types = ["MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable"]
    if any(conditions.get(name) == "True" for name in pressure_types):
        return "partial"
    return "healthy"


def node_record(node: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    metadata = node.get("metadata") or {}
    status = node.get("status") or {}
    node_info = status.get("nodeInfo") or {}
    return {
        "name": metadata.get("name"),
        "internal_ips": node_addresses(node, "InternalIP"),
        "external_ips": node_addresses(node, "ExternalIP"),
        "hostname": (node_addresses(node, "Hostname") or [metadata.get("name")])[0],
        "labels": metadata.get("labels") or {},
        "taints": (node.get("spec") or {}).get("taints") or [],
        "conditions": condition_map(node),
        "capacity": status.get("capacity") or {},
        "allocatable": status.get("allocatable") or {},
        "kubelet_version": node_info.get("kubeletVersion"),
        "os_image": node_info.get("osImage"),
        "kernel_version": node_info.get("kernelVersion"),
        "container_runtime_version": node_info.get("containerRuntimeVersion"),
        "created_at": metadata.get("creationTimestamp"),
        "status_hint": status_hint(node),
        "collected_at": collected_at,
    }


def blocked_output(
    output_file: str,
    script_id: str,
    started_at: str,
    summary: str,
    warnings: List[str],
    evidence_gaps: List[Dict[str, Any]],
) -> None:
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
                    "name": "collect nodes state",
                    "target": "nodes",
                    "method": "kubectl get nodes -o json",
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


def collect_pod_node_refs(kubectl: str, namespace: str, artifact_dir: str) -> List[str]:
    cmd = [kubectl, "get", "pods", "-n", str(namespace), "-o", "json"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        return []
    raw_relpath = os.path.join("raw", "pods-for-node-resolution.json")
    raw_abspath = os.path.join(artifact_dir, raw_relpath)
    with open(raw_abspath, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    payload = json.loads(proc.stdout or "{}")
    refs = []
    for item in payload.get("items") or []:
        node_name = ((item.get("spec") or {}).get("nodeName"))
        if node_name and node_name not in refs:
            refs.append(str(node_name))
    return refs


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)

    script_id = str(context.get("script_id") or "mongodb.collect.nodes.state")
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
            [
                {
                    "gap": "node state collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "Node status is required to understand scheduling and infrastructure pressure",
                }
            ],
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
            [
                {
                    "gap": "node state collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "Node status is required to understand scheduling and infrastructure pressure",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    node_query = context.get("node_query") or {}
    resolve_from_pods = bool(node_query.get("resolve_from_pods", True))
    target_nodes = [str(item) for item in (targets.get("node_refs") or [])]

    artifacts = []
    if not target_nodes and resolve_from_pods:
        target_nodes = collect_pod_node_refs(kubectl, str(namespace), artifact_dir)
        if target_nodes:
            artifacts.append(
                {
                    "path": os.path.join("raw", "pods-for-node-resolution.json"),
                    "kind": "raw_command_output",
                    "description": "raw kubectl get pods output used to resolve node refs",
                }
            )

    json_cmd = [kubectl, "get", "nodes", "-o", "json"]
    json_proc = subprocess.run(json_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if json_proc.returncode != 0:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl get nodes failed",
            [json_proc.stderr.strip() or "kubectl get nodes returned non-zero exit code"],
            [
                {
                    "gap": "node state collection failed",
                    "related_stage": "signal_collection",
                    "why_important": "Node status is required to understand scheduling and infrastructure pressure",
                }
            ],
        )
        return 0

    raw_json_relpath = os.path.join("raw", "nodes-raw.json")
    raw_json_abspath = os.path.join(artifact_dir, raw_json_relpath)
    with open(raw_json_abspath, "w", encoding="utf-8") as fh:
        fh.write(json_proc.stdout)
    artifacts.append(
        {
            "path": raw_json_relpath,
            "kind": "raw_command_output",
            "description": "raw kubectl get nodes -o json output",
        }
    )

    raw_payload = json.loads(json_proc.stdout or "{}")
    items = raw_payload.get("items") or []
    selected: List[Dict[str, Any]] = []
    missing_nodes: List[str] = []

    if target_nodes:
        lookup = {((item.get("metadata") or {}).get("name")): item for item in items}
        for ref in target_nodes:
            if ref in lookup:
                selected.append(lookup[ref])
            else:
                missing_nodes.append(ref)
    else:
        selected = list(items)

    finished_at = now_iso()
    node_records = [node_record(item, finished_at) for item in selected]
    warnings: List[str] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []

    for ref in missing_nodes:
        failed_items.append(
            {
                "item": f"node/{ref}",
                "reason": "requested node was not found in cluster scan",
                "impact": "partial node inventory for current target set",
            }
        )
        evidence_gaps.append(
            {
                "gap": f"node/{ref} state not collected",
                "related_stage": "signal_collection",
                "why_important": "missing node state may hide scheduling or infrastructure pressure",
            }
        )

    if not node_records:
        warnings.append("no nodes matched current query")
        evidence_gaps.append(
            {
                "gap": "no node state records collected",
                "related_stage": "signal_collection",
                "why_important": "Node inventory is required for infrastructure-level triage",
            }
        )

    for record in node_records:
        successful_items.append(
            {
                "item": f"node/{record['name']}",
                "source": "kubectl get nodes -o json",
                "note": f"ready={record['conditions'].get('Ready')} status_hint={record['status_hint']}",
            }
        )

    if failed_items or not node_records:
        status = "partial"
    else:
        status = "success"

    if node_records:
        summary = f"collected {len(node_records)} node state record(s)"
    else:
        summary = "no nodes matched current query"

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "nodes": node_records,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect nodes state",
                    "target": ",".join(target_nodes) if target_nodes else "all_nodes",
                    "method": "kubectl get nodes -o json",
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
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
