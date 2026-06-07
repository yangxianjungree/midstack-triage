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
from typing import Any, Dict, List, Optional

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


def last_restart_at(container_statuses: List[Dict[str, Any]]) -> Optional[str]:
    candidates: List[str] = []
    for status in container_statuses:
        last_state = status.get("lastState") or {}
        terminated = last_state.get("terminated") or {}
        finished_at = terminated.get("finishedAt")
        if finished_at:
            candidates.append(finished_at)
    return max(candidates) if candidates else None


def restart_count(container_statuses: List[Dict[str, Any]]) -> int:
    return sum(int(status.get("restartCount", 0) or 0) for status in container_statuses)


def ready_flag(pod: Dict[str, Any], container_statuses: List[Dict[str, Any]]) -> bool:
    for condition in pod.get("status", {}).get("conditions") or []:
        if condition.get("type") == "Ready":
            return condition.get("status") == "True"
    if container_statuses:
        return all(bool(status.get("ready")) for status in container_statuses)
    return False


def container_status_summary(container_statuses: List[Dict[str, Any]]) -> str:
    if not container_statuses:
        return "unknown"
    waiting_reasons = []
    terminated_reasons = []
    running = False
    for status in container_statuses:
        state = status.get("state") or {}
        if "waiting" in state:
            reason = (state.get("waiting") or {}).get("reason")
            if reason:
                waiting_reasons.append(reason)
        elif "terminated" in state:
            reason = (state.get("terminated") or {}).get("reason") or "terminated"
            terminated_reasons.append(reason)
        elif "running" in state:
            running = True
    if waiting_reasons:
        if any(reason == "CrashLoopBackOff" for reason in waiting_reasons):
            return "restarting"
        return waiting_reasons[0]
    if terminated_reasons:
        return terminated_reasons[0]
    if running:
        return "running"
    return "unknown"


def pod_conditions(pod: Dict[str, Any]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for condition in pod.get("status", {}).get("conditions") or []:
        result.append(
            {
                "type": condition.get("type"),
                "status": condition.get("status"),
                "reason": condition.get("reason"),
                "message": condition.get("message"),
                "last_transition_time": condition.get("lastTransitionTime"),
            }
        )
    return result


def infer_statefulset_ref(pod: Dict[str, Any]) -> Optional[str]:
    metadata = pod.get("metadata") or {}
    owner_refs = metadata.get("ownerReferences") or []
    for owner in owner_refs:
        if owner.get("kind") == "StatefulSet" and owner.get("name"):
            return owner["name"]
    pod_name = metadata.get("name") or ""
    for index in range(len(pod_name) - 1, -1, -1):
        if pod_name[index] == "-" and pod_name[index + 1 :].isdigit():
            return pod_name[:index]
    return None


def status_hint(phase: str, ready: bool, restart_count_value: int, container_status: str) -> str:
    if phase != "Running":
        return "unhealthy"
    if not ready:
        return "unhealthy"
    if restart_count_value > 0 or container_status == "restarting":
        return "partial"
    return "healthy"


def pod_record(pod: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    metadata = pod.get("metadata") or {}
    spec = pod.get("spec") or {}
    status = pod.get("status") or {}
    container_statuses = status.get("containerStatuses") or []
    phase = status.get("phase") or "Unknown"
    ready = ready_flag(pod, container_statuses)
    restarts = restart_count(container_statuses)
    container_status = container_status_summary(container_statuses)
    return {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "component_ref": None,
        "statefulset_ref": infer_statefulset_ref(pod),
        "node_ref": spec.get("nodeName"),
        "node_selector": spec.get("nodeSelector") or {},
        "pod_ip": status.get("podIP"),
        "phase": phase,
        "ready": ready,
        "conditions": pod_conditions(pod),
        "created_at": metadata.get("creationTimestamp"),
        "restart_count": restarts,
        "last_restart_at": last_restart_at(container_statuses),
        "container_status": container_status,
        "yaml": {
            "metadata": {
                "labels": metadata.get("labels") or {},
            }
        },
        "status_hint": status_hint(phase, ready, restarts, container_status),
        "collected_at": collected_at,
    }


def write_result(path: str, payload: Dict[str, Any]) -> None:
    write_yaml(path, payload)


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
                    "name": "collect pods state",
                    "target": "pods",
                    "method": "kubectl get pods -o json",
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
    write_result(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)

    script_id = str(context.get("script_id") or "mongodb.collect.pods.state")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    if not os.path.isdir(artifact_dir):
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
                    "gap": "pod state collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "pod status is required for MongoDB object inventory",
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
                    "gap": "pod state collection not executed",
                    "related_stage": "signal_collection",
                    "why_important": "pod status is required for MongoDB object inventory",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    pod_query = context.get("pod_query") or {}
    mode = pod_query.get("mode")
    target_pod_refs = [str(item) for item in (targets.get("pod_refs") or [])]
    target_statefulsets = [str(item) for item in (targets.get("statefulset_refs") or [])]
    if not mode:
        if target_pod_refs:
            mode = "by_pod_refs"
        elif target_statefulsets:
            mode = "by_statefulset"
        else:
            mode = "by_namespace_scan"

    cmd = [kubectl, "get", "pods", "-n", str(namespace), "-o", "json"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        blocked_output(
            output_file=output_file,
            script_id=script_id,
            started_at=started_at,
            summary="kubectl get pods failed",
            warnings=[proc.stderr.strip() or "kubectl get pods returned non-zero exit code"],
            evidence_gaps=[
                {
                    "gap": "pod state collection failed",
                    "related_stage": "signal_collection",
                    "why_important": "pod status is required for MongoDB object inventory",
                }
            ],
        )
        return 0

    raw_relpath = os.path.join("raw", "pods-raw.json")
    raw_abspath = os.path.join(artifact_dir, raw_relpath)
    with open(raw_abspath, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)

    payload = json.loads(proc.stdout or "{}")
    items = payload.get("items") or []
    selected: List[Dict[str, Any]] = []
    missing_pods: List[str] = []
    missing_statefulsets: List[str] = []

    if mode == "by_pod_refs":
        lookup = {((item.get("metadata") or {}).get("name")): item for item in items}
        for pod_ref in target_pod_refs:
            if pod_ref in lookup:
                selected.append(lookup[pod_ref])
            else:
                missing_pods.append(pod_ref)
    elif mode == "by_statefulset":
        wanted = set(target_statefulsets)
        grouped: Dict[str, List[Dict[str, Any]]] = {name: [] for name in wanted}
        for item in items:
            sts_ref = infer_statefulset_ref(item)
            if sts_ref in wanted:
                grouped[sts_ref].append(item)
                selected.append(item)
        missing_statefulsets = [name for name, pods in grouped.items() if not pods]
    elif mode == "by_namespace_scan":
        selected = list(items)
    else:
        blocked_output(
            output_file=output_file,
            script_id=script_id,
            started_at=started_at,
            summary=f"unsupported pod_query.mode: {mode}",
            warnings=[f"unsupported pod_query.mode: {mode}"],
            evidence_gaps=[
                {
                    "gap": "pod selection mode is invalid",
                    "related_stage": "signal_collection",
                    "why_important": "pod targets cannot be resolved for collection",
                }
            ],
        )
        return 0

    finished_at = now_iso()
    pod_records = [pod_record(item, finished_at) for item in selected]
    warnings: List[str] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []

    for pod_ref in missing_pods:
        failed_items.append(
            {
                "item": f"pod/{pod_ref}",
                "reason": "requested pod was not found in namespace scan",
                "impact": "partial pod inventory for current target set",
            }
        )
        evidence_gaps.append(
            {
                "gap": f"pod/{pod_ref} state not collected",
                "related_stage": "signal_collection",
                "why_important": "missing pod status may hide restart or readiness issues",
            }
        )
    for sts_ref in missing_statefulsets:
        failed_items.append(
            {
                "item": f"statefulset/{sts_ref}",
                "reason": "no pods matched requested statefulset",
                "impact": "partial pod inventory for current target set",
            }
        )
        evidence_gaps.append(
            {
                "gap": f"statefulset/{sts_ref} pods not collected",
                "related_stage": "signal_collection",
                "why_important": "missing pod set may hide shard or replica set issues",
            }
        )

    if not pod_records:
        warnings.append("no pods matched current pod query")
        evidence_gaps.append(
            {
                "gap": "no pod state records collected",
                "related_stage": "signal_collection",
                "why_important": "pod inventory is required for MongoDB object inventory",
            }
        )

    for record in pod_records:
        successful_items.append(
            {
                "item": f"pod/{record['name']}",
                "source": "kubectl get pods -o json",
                "note": f"phase={record['phase']} ready={record['ready']}",
            }
        )

    if failed_items or not pod_records:
        status = "partial"
    else:
        status = "success"

    if pod_records:
        summary = f"collected {len(pod_records)} pod state record(s) in namespace {namespace}"
    else:
        summary = f"no pods matched current query in namespace {namespace}"

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": [
            {
                "path": raw_relpath,
                "kind": "raw_command_output",
                "description": "raw kubectl get pods -o json output",
            }
        ],
        "structured_record_patch": {
            "details": {
                "pods": pod_records,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect pods state",
                    "target": namespace,
                    "method": "kubectl get pods -o json",
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
    write_result(output_file, payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
