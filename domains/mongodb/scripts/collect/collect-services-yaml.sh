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


def service_ports(service: Dict[str, Any], include_nodeport: bool) -> List[Dict[str, Any]]:
    ports = (service.get("spec") or {}).get("ports") or []
    records: List[Dict[str, Any]] = []
    for port in ports:
        record = {
            "name": port.get("name"),
            "protocol": port.get("protocol"),
            "port": port.get("port"),
            "target_port": port.get("targetPort"),
        }
        if include_nodeport:
            record["node_port"] = port.get("nodePort")
        records.append(record)
    return records


def status_hint(service: Dict[str, Any]) -> str:
    spec = service.get("spec") or {}
    service_type = spec.get("type") or "ClusterIP"
    ports = spec.get("ports") or []
    cluster_ip = spec.get("clusterIP")
    if not ports:
        return "unhealthy"
    if service_type == "NodePort" and not any(port.get("nodePort") for port in ports):
        return "partial"
    if service_type == "ClusterIP" and not cluster_ip:
        return "partial"
    return "healthy"


def service_record(service: Dict[str, Any], collected_at: str, include_nodeport: bool, include_yaml: bool) -> Dict[str, Any]:
    metadata = service.get("metadata") or {}
    spec = service.get("spec") or {}
    record: Dict[str, Any] = {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "component_ref": None,
        "type": spec.get("type"),
        "cluster_ip": spec.get("clusterIP"),
        "cluster_ips": spec.get("clusterIPs") or [],
        "external_ips": spec.get("externalIPs") or [],
        "selector": spec.get("selector") or {},
        "ports": service_ports(service, include_nodeport),
        "created_at": metadata.get("creationTimestamp"),
        "labels": metadata.get("labels") or {},
        "status_hint": status_hint(service),
        "collected_at": collected_at,
    }
    if include_yaml:
        record["yaml"] = {
            "apiVersion": service.get("apiVersion"),
            "kind": service.get("kind"),
            "metadata": {
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "labels": metadata.get("labels") or {},
                "annotations": metadata.get("annotations") or {},
            },
            "spec": spec,
            "status": service.get("status") or {},
        }
    return record


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
                    "name": "collect services yaml",
                    "target": "services",
                    "method": "kubectl get services -o json",
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


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)

    script_id = str(context.get("script_id") or "mongodb.collect.services.yaml")
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
                    "gap": "service yaml collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "Service and NodePort mapping is required to understand MongoDB access paths",
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
                    "gap": "service yaml collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "Service and NodePort mapping is required to understand MongoDB access paths",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    service_query = context.get("service_query") or {}
    include_nodeport = bool(service_query.get("include_nodeport", True))
    include_yaml = bool(service_query.get("include_yaml", True))
    target_services = [str(item) for item in (targets.get("service_refs") or [])]

    json_cmd = [kubectl, "get", "services", "-n", str(namespace), "-o", "json"]
    json_proc = subprocess.run(json_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if json_proc.returncode != 0:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl get services failed",
            [json_proc.stderr.strip() or "kubectl get services returned non-zero exit code"],
            [
                {
                    "gap": "service yaml collection failed",
                    "related_stage": "signal_collection",
                    "why_important": "Service and NodePort mapping is required to understand MongoDB access paths",
                }
            ],
        )
        return 0

    raw_json_relpath = os.path.join("raw", "services-raw.json")
    raw_json_abspath = os.path.join(artifact_dir, raw_json_relpath)
    with open(raw_json_abspath, "w", encoding="utf-8") as fh:
        fh.write(json_proc.stdout)

    artifacts = [
        {
            "path": raw_json_relpath,
            "kind": "raw_command_output",
            "description": "raw kubectl get services -o json output",
        }
    ]

    yaml_warning = ""
    if include_yaml:
        yaml_cmd = [kubectl, "get", "services", "-n", str(namespace), "-o", "yaml"]
        yaml_proc = subprocess.run(yaml_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if yaml_proc.returncode == 0:
            raw_yaml_relpath = os.path.join("raw", "services-raw.yaml")
            raw_yaml_abspath = os.path.join(artifact_dir, raw_yaml_relpath)
            with open(raw_yaml_abspath, "w", encoding="utf-8") as fh:
                fh.write(yaml_proc.stdout)
            artifacts.append(
                {
                    "path": raw_yaml_relpath,
                    "kind": "raw_command_output",
                    "description": "raw kubectl get services -o yaml output",
                }
            )
        else:
            yaml_warning = yaml_proc.stderr.strip() or "kubectl get services -o yaml failed"

    raw_payload = json.loads(json_proc.stdout or "{}")
    items = raw_payload.get("items") or []
    selected: List[Dict[str, Any]] = []
    missing_services: List[str] = []

    if target_services:
        lookup = {((item.get("metadata") or {}).get("name")): item for item in items}
        for ref in target_services:
            if ref in lookup:
                selected.append(lookup[ref])
            else:
                missing_services.append(ref)
    else:
        selected = list(items)

    finished_at = now_iso()
    service_records = [service_record(item, finished_at, include_nodeport, include_yaml) for item in selected]
    warnings: List[str] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []

    if yaml_warning:
        warnings.append(yaml_warning)
        evidence_gaps.append(
            {
                "gap": "raw service yaml artifact not collected",
                "related_stage": "signal_collection",
                "why_important": "raw YAML helps inspect selectors, NodePort and access mapping",
            }
        )

    for ref in missing_services:
        failed_items.append(
            {
                "item": f"service/{ref}",
                "reason": "requested service was not found in namespace scan",
                "impact": "partial service inventory for current target set",
            }
        )
        evidence_gaps.append(
            {
                "gap": f"service/{ref} yaml not collected",
                "related_stage": "signal_collection",
                "why_important": "missing Service spec may hide access path or NodePort issues",
            }
        )

    if not service_records:
        warnings.append("no services matched current query")
        evidence_gaps.append(
            {
                "gap": "no service records collected",
                "related_stage": "signal_collection",
                "why_important": "Service inventory is required for MongoDB access path analysis",
            }
        )

    for record in service_records:
        ports = ",".join(str(port.get("port")) for port in record["ports"])
        successful_items.append(
            {
                "item": f"service/{record['name']}",
                "source": "kubectl get services -o json",
                "note": f"type={record['type']} ports={ports}",
            }
        )

    if failed_items or not service_records or yaml_warning:
        status = "partial"
    else:
        status = "success"

    if service_records:
        summary = f"collected {len(service_records)} service record(s) in namespace {namespace}"
    else:
        summary = f"no services matched current query in namespace {namespace}"

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "services": service_records,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect services yaml",
                    "target": namespace,
                    "method": "kubectl get services -o json",
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
