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


def first_container_resources(sts: Dict[str, Any]) -> List[Dict[str, Any]]:
    containers = (((sts.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers") or []
    records: List[Dict[str, Any]] = []
    for container in containers:
        records.append(
            {
                "name": container.get("name"),
                "image": container.get("image"),
                "resources": container.get("resources") or {},
                "ports": container.get("ports") or [],
            }
        )
    return records


def volume_claim_template_names(sts: Dict[str, Any]) -> List[str]:
    templates = (sts.get("spec") or {}).get("volumeClaimTemplates") or []
    names: List[str] = []
    for template in templates:
        name = ((template.get("metadata") or {}).get("name"))
        if name:
            names.append(str(name))
    return names


def status_hint(sts: Dict[str, Any]) -> str:
    spec = sts.get("spec") or {}
    status = sts.get("status") or {}
    desired = int(spec.get("replicas", 0) or 0)
    ready = int(status.get("readyReplicas", 0) or 0)
    updated = int(status.get("updatedReplicas", 0) or 0)
    if desired == 0:
        return "unknown"
    if ready < desired:
        return "unhealthy"
    if updated < desired:
        return "partial"
    return "healthy"


def statefulset_record(sts: Dict[str, Any], collected_at: str, include_yaml: bool) -> Dict[str, Any]:
    metadata = sts.get("metadata") or {}
    spec = sts.get("spec") or {}
    status = sts.get("status") or {}
    record: Dict[str, Any] = {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "component_ref": None,
        "service_name": spec.get("serviceName"),
        "replicas": spec.get("replicas"),
        "ready_replicas": status.get("readyReplicas", 0),
        "current_replicas": status.get("currentReplicas", 0),
        "updated_replicas": status.get("updatedReplicas", 0),
        "available_replicas": status.get("availableReplicas", 0),
        "selector": spec.get("selector") or {},
        "pod_management_policy": spec.get("podManagementPolicy"),
        "update_strategy": spec.get("updateStrategy") or {},
        "volume_claim_templates": volume_claim_template_names(sts),
        "containers": first_container_resources(sts),
        "created_at": metadata.get("creationTimestamp"),
        "labels": metadata.get("labels") or {},
        "status_hint": status_hint(sts),
        "collected_at": collected_at,
    }
    if include_yaml:
        record["yaml"] = {
            "apiVersion": sts.get("apiVersion"),
            "kind": sts.get("kind"),
            "metadata": {
                "name": metadata.get("name"),
                "namespace": metadata.get("namespace"),
                "labels": metadata.get("labels") or {},
                "annotations": metadata.get("annotations") or {},
            },
            "spec": spec,
            "status": status,
        }
    return record


def blocked_output(
    *,
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
                    "name": "collect statefulsets yaml",
                    "target": "statefulsets",
                    "method": "kubectl get statefulsets -o json",
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

    script_id = str(context.get("script_id") or "mongodb.collect.statefulsets.yaml")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(artifact_dir, exist_ok=True)
    raw_dir = os.path.join(artifact_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", False):
        blocked_output(
            output_file=output_file,
            script_id=script_id,
            started_at=started_at,
            summary="kubectl is not available in current runtime",
            warnings=["capabilities.kubectl_available is false"],
            evidence_gaps=[
                {
                    "gap": "statefulset yaml collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "StatefulSet spec is required to understand MongoDB workload orchestration",
                }
            ],
        )
        return 0

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_output(
            output_file=output_file,
            script_id=script_id,
            started_at=started_at,
            summary="kubectl command not found in runtime environment",
            warnings=["kubectl binary is missing"],
            evidence_gaps=[
                {
                    "gap": "statefulset yaml collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "StatefulSet spec is required to understand MongoDB workload orchestration",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    statefulset_query = context.get("statefulset_query") or {}
    include_yaml = bool(statefulset_query.get("include_yaml", True))
    target_statefulsets = [str(item) for item in (targets.get("statefulset_refs") or [])]

    json_cmd = [kubectl, "get", "statefulsets", "-n", str(namespace), "-o", "json"]
    json_proc = subprocess.run(json_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if json_proc.returncode != 0:
        blocked_output(
            output_file=output_file,
            script_id=script_id,
            started_at=started_at,
            summary="kubectl get statefulsets failed",
            warnings=[json_proc.stderr.strip() or "kubectl get statefulsets returned non-zero exit code"],
            evidence_gaps=[
                {
                    "gap": "statefulset yaml collection failed",
                    "related_stage": "signal_collection",
                    "why_important": "StatefulSet spec is required to understand MongoDB workload orchestration",
                }
            ],
        )
        return 0

    raw_json_relpath = os.path.join("raw", "statefulsets-raw.json")
    raw_json_abspath = os.path.join(artifact_dir, raw_json_relpath)
    with open(raw_json_abspath, "w", encoding="utf-8") as fh:
        fh.write(json_proc.stdout)

    artifacts = [
        {
            "path": raw_json_relpath,
            "kind": "raw_command_output",
            "description": "raw kubectl get statefulsets -o json output",
        }
    ]

    yaml_warning = ""
    if include_yaml:
        yaml_cmd = [kubectl, "get", "statefulsets", "-n", str(namespace), "-o", "yaml"]
        yaml_proc = subprocess.run(yaml_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if yaml_proc.returncode == 0:
            raw_yaml_relpath = os.path.join("raw", "statefulsets-raw.yaml")
            raw_yaml_abspath = os.path.join(artifact_dir, raw_yaml_relpath)
            with open(raw_yaml_abspath, "w", encoding="utf-8") as fh:
                fh.write(yaml_proc.stdout)
            artifacts.append(
                {
                    "path": raw_yaml_relpath,
                    "kind": "raw_command_output",
                    "description": "raw kubectl get statefulsets -o yaml output",
                }
            )
        else:
            yaml_warning = yaml_proc.stderr.strip() or "kubectl get statefulsets -o yaml failed"

    raw_payload = json.loads(json_proc.stdout or "{}")
    items = raw_payload.get("items") or []
    selected: List[Dict[str, Any]] = []
    missing_statefulsets: List[str] = []

    if target_statefulsets:
        lookup = {((item.get("metadata") or {}).get("name")): item for item in items}
        for ref in target_statefulsets:
            if ref in lookup:
                selected.append(lookup[ref])
            else:
                missing_statefulsets.append(ref)
    else:
        selected = list(items)

    finished_at = now_iso()
    statefulset_records = [statefulset_record(item, finished_at, include_yaml) for item in selected]
    warnings: List[str] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []

    if yaml_warning:
        warnings.append(yaml_warning)
        evidence_gaps.append(
            {
                "gap": "raw statefulset yaml artifact not collected",
                "related_stage": "signal_collection",
                "why_important": "raw YAML helps inspect scheduling, resources, probes and volume templates",
            }
        )

    for ref in missing_statefulsets:
        failed_items.append(
            {
                "item": f"statefulset/{ref}",
                "reason": "requested statefulset was not found in namespace scan",
                "impact": "partial workload orchestration inventory for current target set",
            }
        )
        evidence_gaps.append(
            {
                "gap": f"statefulset/{ref} yaml not collected",
                "related_stage": "signal_collection",
                "why_important": "missing StatefulSet spec may hide resource, scheduling or rollout issues",
            }
        )

    if not statefulset_records:
        warnings.append("no statefulsets matched current query")
        evidence_gaps.append(
            {
                "gap": "no statefulset records collected",
                "related_stage": "signal_collection",
                "why_important": "StatefulSet inventory is required for MongoDB object inventory",
            }
        )

    for record in statefulset_records:
        successful_items.append(
            {
                "item": f"statefulset/{record['name']}",
                "source": "kubectl get statefulsets -o json",
                "note": f"ready={record['ready_replicas']} desired={record['replicas']}",
            }
        )

    if failed_items or not statefulset_records or yaml_warning:
        status = "partial"
    else:
        status = "success"

    if statefulset_records:
        summary = f"collected {len(statefulset_records)} statefulset record(s) in namespace {namespace}"
    else:
        summary = f"no statefulsets matched current query in namespace {namespace}"

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "statefulsets": statefulset_records,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect statefulsets yaml",
                    "target": namespace,
                    "method": "kubectl get statefulsets -o json",
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
