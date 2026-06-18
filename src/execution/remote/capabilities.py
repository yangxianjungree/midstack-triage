"""Remote capability checks and pod-target probing helpers."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Tuple

from execution.remote.context import default_targets
from execution.remote.error_contract import (
    BLOCKED_ERROR_CODES,
    capability_result,
    classify_kubectl_error,
    classify_remote_error,
    classify_ssh_error,
    error_payload,
    status_from_error_code,
)
from execution.remote import mongodb_collection_runtime as mcr
from execution.remote.script_output_contract import (
    SCRIPT_OUTPUT_ALLOWED_STATUSES,
    SCRIPT_OUTPUT_REQUIRED_FIELDS,
    validate_script_output_contract,
)

RunSshFn = Callable[[Dict[str, Any], str, int], subprocess.CompletedProcess]
SCRIPT_IDS_REQUIRING_MONGOSH = {
    "mongodb.collect.mongos.get_shard_map",
    "mongodb.collect.replicaset.rs_status",
}
SCRIPT_ID_MONGOS_SHARD_MAP = "mongodb.collect.mongos.get_shard_map"
SCRIPT_ID_REPLICASET_STATUS = "mongodb.collect.replicaset.rs_status"


def shell_candidates(shell_name: str) -> List[str]:
    candidates = [shell_name or "mongosh"]
    if candidates[0] == "mongosh":
        candidates.append("mongo")
    unique = []
    seen = set()
    for item in candidates:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


def build_required_capabilities(script_id: str) -> Dict[str, Any]:
    requires_mongosh = script_id in SCRIPT_IDS_REQUIRING_MONGOSH
    payload: Dict[str, Any] = {
        "ssh": True,
        "kubectl": True,
        "kubectl_exec": True,
        "pod_tools": [{"name": "mongosh", "required": requires_mongosh, "execution": "pod_internal"}],
    }
    if script_id == SCRIPT_ID_MONGOS_SHARD_MAP:
        payload["target_pod"] = {"kind": "mongos", "required": True}
    elif script_id == SCRIPT_ID_REPLICASET_STATUS:
        payload["target_pods"] = {"kind": "mongod", "required": True}
    return payload


def pod_name(item: Dict[str, Any]) -> str:
    return str((((item.get("metadata") or {}).get("name")) or ""))


def pod_phase(item: Dict[str, Any]) -> str:
    return str((((item.get("status") or {}).get("phase")) or ""))


def pod_label_text(item: Dict[str, Any]) -> str:
    labels = (((item.get("metadata") or {}).get("labels")) or {})
    return " ".join("%s=%s" % (str(key).lower(), str(value).lower()) for key, value in labels.items())


def mongos_pod_score(item: Dict[str, Any]) -> int:
    name = pod_name(item).lower()
    label_text = pod_label_text(item)
    score = 0
    if pod_phase(item) == "Running":
        score += 10
    if "mongos" in name:
        score += 20
    if "mongos" in label_text:
        score += 20
    return score


def replicaset_pod_score(item: Dict[str, Any]) -> int:
    name = pod_name(item).lower()
    label_text = pod_label_text(item)
    score = 0
    if pod_phase(item) == "Running":
        score += 5
    if "configsvr" in name or "shard" in name:
        score += 20
    if "mongos" in name or "operator" in name:
        score -= 50
    if "component=configsvr" in label_text or "component=shard" in label_text or "component=shardsvr" in label_text:
        score += 20
    return score


def remote_kubectl_get_pods(
    access: Dict[str, Any],
    namespace: str,
    *,
    run_ssh_fn: RunSshFn,
) -> Tuple[subprocess.CompletedProcess, List[Dict[str, Any]], str]:
    proc = run_ssh_fn(access, "kubectl get pods -n %s -o json" % shlex.quote(namespace), 30)
    if proc.returncode != 0:
        return proc, [], proc.stderr.strip() or proc.stdout.strip() or "kubectl get pods failed"
    try:
        payload = json.loads(proc.stdout or "{}")
    except ValueError as exc:
        return proc, [], "failed to parse kubectl get pods output: %s" % exc
    items = payload.get("items") or []
    return proc, [item for item in items if isinstance(item, dict)], ""


def resolve_mongos_target_pod(pods: List[Dict[str, Any]], target_ref: str) -> str:
    if target_ref:
        for item in pods:
            if pod_name(item) == target_ref and mongos_pod_score(item) >= 20:
                return target_ref
    candidates = sorted(pods, key=mongos_pod_score, reverse=True)
    for item in candidates:
        if mongos_pod_score(item) >= 20:
            return pod_name(item)
    return ""


def resolve_replicaset_target_pods(pods: List[Dict[str, Any]], target_refs: List[str]) -> List[str]:
    if target_refs:
        target_set = set(target_refs)
        filtered = []
        for item in sorted(pods, key=replicaset_pod_score, reverse=True):
            name = pod_name(item)
            if name in target_set and replicaset_pod_score(item) >= 20:
                filtered.append(name)
        if filtered:
            return filtered
    candidates = sorted(pods, key=replicaset_pod_score, reverse=True)
    resolved = []
    for item in candidates:
        if replicaset_pod_score(item) < 20:
            continue
        name = pod_name(item)
        if name and name not in resolved:
            resolved.append(name)
    return resolved


def classify_pod_exec_error(stderr: str, default_code: str) -> str:
    text = stderr.lower()
    if "not found" in text and ("pod" in text or "pods" in text):
        return "target_pod_not_found"
    if "unable to upgrade connection" in text or "container not found" in text or "forbidden" in text:
        return "kubectl_exec_unavailable"
    return default_code


def pod_tool_probe_script(candidates: List[str]) -> str:
    checks = ["command -v %s >/dev/null 2>&1" % shlex.quote(item) for item in candidates if item]
    if not checks:
        checks = ["command -v mongosh >/dev/null 2>&1", "command -v mongo >/dev/null 2>&1"]
    return " || ".join(checks)


def probe_pod_tool(
    access: Dict[str, Any],
    namespace: str,
    pod: str,
    candidates: List[str],
    *,
    run_ssh_fn: RunSshFn,
) -> Tuple[bool, str, str]:
    proc = run_ssh_fn(
        access,
        "kubectl exec -n %s %s -- sh -lc %s" % (shlex.quote(namespace), shlex.quote(pod), shlex.quote(pod_tool_probe_script(candidates))),
        30,
    )
    if proc.returncode == 0:
        return True, "", "resolved pod tool %s in pod/%s" % ("/".join(candidates), pod)
    code = classify_pod_exec_error(proc.stderr, "pod_tool_missing")
    detail = proc.stderr.strip() or proc.stdout.strip() or "required pod tool %s was not found in pod/%s" % ("/".join(candidates), pod)
    return False, code, detail


def probe_pod_container_shell(
    access: Dict[str, Any],
    namespace: str,
    pod_item: Dict[str, Any],
    mongo_exec: Dict[str, Any],
    *,
    run_ssh_fn: RunSshFn,
) -> Tuple[str, str, str]:
    pod_ref = mcr.pod_name(pod_item)
    pod_targets = mongo_exec.get("pod_targets") or {}
    if isinstance(pod_targets, dict):
        existing = pod_targets.get(pod_ref) or {}
        if isinstance(existing, dict) and existing.get("shell"):
            return str(existing.get("container") or ""), str(existing["shell"]), ""

    candidates = [str(item) for item in (mongo_exec.get("shell_candidates") or list(mcr.DEFAULT_SHELL_CANDIDATES)) if item]
    container_candidates = mcr.container_names_for_pod(
        pod_item,
        [str(item) for item in (mongo_exec.get("container_name_candidates") or []) if item],
    )
    probe = mcr.shell_probe_command(candidates)
    last_detail = ""
    for container in container_candidates:
        proc = run_ssh_fn(
            access,
            "kubectl exec -n %s %s -c %s -- bash -c %s"
            % (shlex.quote(namespace), shlex.quote(pod_ref), shlex.quote(container), shlex.quote(probe)),
            30,
        )
        if proc.returncode == 0:
            shell = (proc.stdout or "").strip().splitlines()[-1].strip()
            if shell:
                mcr.merge_pod_exec_target(mongo_exec, pod_ref, container, shell)
                return container, shell, ""
        last_detail = proc.stderr.strip() or proc.stdout.strip() or last_detail
    if not last_detail:
        last_detail = "mongo shell not found in pod/%s containers %s" % (pod_ref, ", ".join(container_candidates))
    return "", "", last_detail


def record_pod_tool_probe_summary(
    checks: List[Dict[str, str]],
    warnings: List[str],
    capabilities: Dict[str, Any],
    pod_refs: List[str],
    mongo_exec: Dict[str, Any],
    label: str,
) -> None:
    available, total, any_ok = mcr.summarize_pod_tool_probe(pod_refs, mongo_exec)
    if any_ok:
        capabilities["mongosh_in_pod_available"] = True
        if available == total:
            checks.append(
                capability_result(
                    "pod_tool.mongosh",
                    "success",
                    "resolved mongo shell in %s/%s %s pods" % (available, total, label),
                )
            )
        else:
            detail = "resolved mongo shell in %s/%s %s pods" % (available, total, label)
            checks.append(capability_result("pod_tool.mongosh", "partial", detail, "pod_tool_missing"))
            warnings.append(detail)
    else:
        detail = "mongo shell not resolved in any of %s %s pod(s); script will emit structured blocked/partial output" % (total, label)
        checks.append(capability_result("pod_tool.mongosh", "partial", detail, "pod_tool_missing"))
        warnings.append(detail)


def validate_script_capabilities(
    access: Dict[str, Any],
    namespace: str,
    script_id: str,
    context: Dict[str, Any],
    inherited_checks: List[Dict[str, str]],
    *,
    run_ssh_fn: RunSshFn,
) -> Tuple[bool, Dict[str, Any], List[Dict[str, str]], Dict[str, str], List[str]]:
    checks = list(inherited_checks)
    warnings: List[str] = []
    error = error_payload()
    targets = default_targets(namespace)
    if isinstance(context.get("targets"), dict):
        targets.update(context.get("targets") or {})
    targets["namespace"] = namespace or str(targets.get("namespace") or "")
    context["targets"] = targets
    capabilities = context.setdefault("capabilities", {})
    capabilities["mongosh_in_pod_available"] = False

    if script_id not in SCRIPT_IDS_REQUIRING_MONGOSH:
        checks.append(capability_result("pod_tool.mongosh", "partial", "not required by this script"))
        return True, context, checks, error, warnings
    if not namespace:
        detail = "namespace is empty for script target resolution"
        error = error_payload("target_pod_not_found", detail)
        checks.append(capability_result("target_pod.discovery", "blocked", detail, "target_pod_not_found"))
        return False, context, checks, error, warnings

    pods_proc, pods, pods_error = remote_kubectl_get_pods(access, namespace, run_ssh_fn=run_ssh_fn)
    if pods_proc.returncode != 0:
        error = classify_remote_error(pods_error, "target_pod_not_found")
        checks.append(capability_result("target_pod.discovery", "blocked", pods_error, error["code"]))
        return False, context, checks, error, warnings
    if pods_error:
        error = error_payload("target_pod_not_found", pods_error)
        checks.append(capability_result("target_pod.discovery", "blocked", pods_error, "target_pod_not_found"))
        return False, context, checks, error, warnings

    mongos_query = context.get("mongos_query") or {}
    replicaset_query = context.get("replicaset_query") or {}
    collection = mcr.resolve_mongodb_collection_targets(pods, mongos_query=mongos_query, replicaset_query=replicaset_query)
    mongo_exec = collection["mongo_exec"]
    context["mongo_exec"] = mongo_exec
    pod_by_name = collection["pod_by_name"]

    if script_id == SCRIPT_ID_MONGOS_SHARD_MAP:
        mongos_pod_refs = list(collection["mongos_pod_refs"])
        if not mongos_pod_refs:
            detail = "no Running mongos pods could be resolved from current namespace"
            error = error_payload("target_pod_not_found", detail)
            checks.append(capability_result("target_pod.mongos", "blocked", detail, "target_pod_not_found"))
            return False, context, checks, error, warnings
        targets["mongos_pod_refs"] = mongos_pod_refs
        targets["mongos_pod_ref"] = collection["mongos_pod_ref"]
        checks.append(capability_result("target_pod.mongos", "success", "resolved %s Running mongos pod(s)" % len(mongos_pod_refs)))
        for pod_ref in mongos_pod_refs:
            pod_item = pod_by_name.get(pod_ref)
            if pod_item:
                probe_pod_container_shell(access, namespace, pod_item, mongo_exec, run_ssh_fn=run_ssh_fn)
        record_pod_tool_probe_summary(checks, warnings, capabilities, mongos_pod_refs, mongo_exec, "mongos")
        return True, context, checks, error, warnings

    mongod_pod_refs = list(collection["mongod_pod_refs"])
    if not mongod_pod_refs:
        detail = "no Running mongod pods could be resolved from current namespace"
        error = error_payload("target_pod_not_found", detail)
        checks.append(capability_result("target_pod.replicaset", "blocked", detail, "target_pod_not_found"))
        return False, context, checks, error, warnings
    targets["mongod_pod_refs"] = mongod_pod_refs
    targets["pod_refs"] = mongod_pod_refs
    checks.append(capability_result("target_pod.replicaset", "success", "resolved %s Running mongod pod(s)" % len(mongod_pod_refs)))
    for pod_ref in mongod_pod_refs:
        pod_item = pod_by_name.get(pod_ref)
        if pod_item:
            probe_pod_container_shell(access, namespace, pod_item, mongo_exec, run_ssh_fn=run_ssh_fn)
    record_pod_tool_probe_summary(checks, warnings, capabilities, mongod_pod_refs, mongo_exec, "mongod")
    return True, context, checks, error, warnings


def validate_executor_capabilities(
    access: Dict[str, Any],
    *,
    run_ssh_fn: RunSshFn,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> Tuple[bool, List[Dict[str, str]], Dict[str, str]]:
    from execution.remote.executor_preflight import validate_executor_capabilities as validate_preflight

    return validate_preflight(access, run_ssh_fn=run_ssh_fn, which_fn=which_fn)
