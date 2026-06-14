#!/usr/bin/env python3

import argparse
import json
import os
import posixpath
import signal
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[4]

from shared import mongodb_collection_runtime as mcr
DEFAULT_LOCAL_OUTPUT = ROOT / ".local" / "remote-runs"
DEFAULT_REMOTE_ROOT = "/tmp/midstack-triage"
DEFAULT_RUNTIME_MAP = ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml"
DEFAULT_MANIFEST = ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml"
DEFAULT_PLUGIN_NAME = "midstack-triage"
REMOTE_COMMAND_TIMEOUT_EXIT = 124


SSH_OPTIONS = [
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "ServerAliveInterval=5",
    "-o",
    "ServerAliveCountMax=2",
    "-o",
    "PreferredAuthentications=password,keyboard-interactive",
    "-o",
    "PubkeyAuthentication=no",
    "-o",
    "NumberOfPasswordPrompts=1",
]

BLOCKED_ERROR_CODES = {
    "missing_sshpass",
    "ssh_auth_failed",
    "ssh_unreachable",
    "kubectl_missing",
    "k8s_context_unavailable",
    "kubectl_exec_unavailable",
    "target_pod_not_found",
    "pod_tool_missing",
}
SCRIPT_IDS_REQUIRING_MONGOSH = {
    "mongodb.collect.mongos.get_shard_map",
    "mongodb.collect.replicaset.rs_status",
}
SCRIPT_ID_MONGOS_SHARD_MAP = "mongodb.collect.mongos.get_shard_map"
SCRIPT_ID_REPLICASET_STATUS = "mongodb.collect.replicaset.rs_status"
SCRIPT_OUTPUT_REQUIRED_FIELDS = (
    "script_id",
    "status",
    "summary",
    "started_at",
    "finished_at",
    "artifacts",
    "structured_record_patch",
    "signal_bundle_patch",
    "collection_report_patch",
    "warnings",
    "evidence_gaps",
)
SCRIPT_OUTPUT_ALLOWED_STATUSES = {"success", "partial", "blocked"}


def now_id() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def try_load_yaml(path: Path) -> Dict[str, Any]:
    try:
        data = load_config(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_script_entries(manifest_path: Path, runtime_map_path: Path, selected_script_ids: List[str] = None) -> List[Dict[str, Any]]:
    manifest = load_config(manifest_path)
    runtime_map = load_config(runtime_map_path)
    manifest_root = manifest_path.parent
    source_by_id = {}
    selected = set(selected_script_ids or [])
    for item in manifest.get("scripts") or []:
        if isinstance(item, dict) and item.get("default_packaged") is True:
            source_by_id[str(item.get("script_id") or "")] = item

    entries = []
    for item in runtime_map.get("scripts") or []:
        if not isinstance(item, dict):
            continue
        script_id = str(item.get("script_id") or "")
        manifest_item = source_by_id.get(script_id)
        if not manifest_item:
            raise RuntimeError("runtime map script is missing from default_packaged manifest: %s" % script_id)
        if selected:
            if script_id not in selected:
                continue
        elif manifest_item.get("mvp") is not True:
            continue
        source = str(manifest_item.get("source") or "")
        entry = {
            "script_id": script_id,
            "source_path": manifest_root / source,
            "runtime_path": str(item.get("runtime_path") or ""),
            "runtime": str(item.get("runtime") or manifest_item.get("runtime") or ""),
            "readonly": bool(item.get("readonly")),
        }
        if not entry["source_path"].exists():
            raise RuntimeError("script source does not exist for %s: %s" % (script_id, entry["source_path"]))
        entries.append(entry)
    if not entries:
        if selected:
            raise RuntimeError("selected script ids are not runtime-map-backed default_packaged scripts: %s" % sorted(selected))
        raise RuntimeError("runtime map contains no MVP scripts: %s" % runtime_map_path)
    return entries


def remote_path(remote_root: str, runtime_path: str) -> str:
    return "%s/%s" % (remote_root.rstrip("/"), runtime_path.lstrip("/"))


def default_targets(namespace: str) -> Dict[str, Any]:
    return {
        "namespace": namespace,
        "statefulset_refs": [],
        "service_refs": [],
        "pod_refs": [],
        "mongos_pod_refs": [],
        "mongod_pod_refs": [],
        "node_refs": [],
        "mongos_pod_ref": "",
    }


def default_context_profile(namespace: str) -> Dict[str, Any]:
    return {
        "deployment_architecture": "unknown",
        "topology_type": "sharded_cluster",
        "targets": default_targets(namespace),
        "auth_secret_ref": {},
    }


def context_profile_from_inventory(inventory_path: str, namespace: str) -> Dict[str, Any]:
    profile = default_context_profile(namespace)
    if not inventory_path:
        return profile
    path = Path(inventory_path)
    if not path.exists():
        return profile
    inventory = load_config(path)
    candidates = inventory.get("deployment_architecture_candidates") or []
    if candidates:
        profile["deployment_architecture"] = str(candidates[0])
    topology = inventory.get("topology_hints") or {}
    if topology.get("candidate_topology_type"):
        profile["topology_type"] = str(topology["candidate_topology_type"])
    targets = inventory.get("targets")
    if isinstance(targets, dict):
        merged_targets = default_targets(namespace)
        merged_targets.update(targets)
        merged_targets["namespace"] = namespace or str(merged_targets.get("namespace") or "")
        profile["targets"] = merged_targets
    auth_hints = inventory.get("auth_hints") or {}
    selected_secret_ref = auth_hints.get("selected_secret_ref") or {}
    if isinstance(selected_secret_ref, dict) and selected_secret_ref.get("name") and selected_secret_ref.get("key"):
        profile["auth_secret_ref"] = {
            "namespace": str(selected_secret_ref.get("namespace") or namespace),
            "name": str(selected_secret_ref.get("name") or ""),
            "key": str(selected_secret_ref.get("key") or ""),
        }
    return profile


def error_payload(code: str = "", message: str = "") -> Dict[str, str]:
    return {"code": code, "message": message}


def status_from_error_code(code: str) -> str:
    return "blocked" if code in BLOCKED_ERROR_CODES else "failed"


def capability_result(name: str, status: str, detail: str, error_code: str = "") -> Dict[str, str]:
    item = {"name": name, "status": status, "detail": detail}
    if error_code:
        item["error_code"] = error_code
    return item


def classify_ssh_error(stderr: str) -> str:
    text = stderr.lower()
    if "permission denied" in text or "authentication failed" in text:
        return "ssh_auth_failed"
    if "timed out" in text or "no route to host" in text or "connection refused" in text or "could not resolve hostname" in text:
        return "ssh_unreachable"
    return "ssh_unreachable"


def classify_kubectl_error(stderr: str) -> str:
    text = stderr.lower()
    if "command not found" in text and "kubectl" in text:
        return "kubectl_missing"
    if "the connection to the server" in text or "no configuration has been provided" in text or "context deadline exceeded" in text:
        return "k8s_context_unavailable"
    return "k8s_context_unavailable"


def classify_remote_error(detail: str, default_code: str) -> Dict[str, str]:
    message = detail.strip() or default_code
    lowered = message.lower()
    if any(token in lowered for token in ("permission denied", "authentication failed")):
        return error_payload("ssh_auth_failed", message)
    if any(token in lowered for token in ("timed out", "no route to host", "connection refused", "could not resolve hostname", "lost connection")):
        return error_payload("ssh_unreachable", message)
    if "kubectl" in lowered or "the connection to the server" in lowered or "no configuration has been provided" in lowered:
        return error_payload(classify_kubectl_error(message), message)
    return error_payload(default_code, message)


def validate_script_output_contract(output_path: Path, expected_script_id: str) -> Tuple[bool, Dict[str, Any], str]:
    try:
        data = load_config(output_path)
    except Exception as exc:
        return False, {}, "output.yaml is not valid YAML: %s" % exc
    if not isinstance(data, dict) or not data:
        return False, {}, "output.yaml must contain a YAML object"

    missing = [field for field in SCRIPT_OUTPUT_REQUIRED_FIELDS if field not in data]
    if missing:
        return False, data, "output.yaml is missing required fields: %s" % ", ".join(missing)

    actual_script_id = str(data.get("script_id") or "")
    if actual_script_id != expected_script_id:
        return False, data, "output.yaml script_id mismatch: expected %s, got %s" % (expected_script_id, actual_script_id or "missing")

    status = str(data.get("status") or "")
    if status not in SCRIPT_OUTPUT_ALLOWED_STATUSES:
        return False, data, "output.yaml status must be one of %s, got %s" % (sorted(SCRIPT_OUTPUT_ALLOWED_STATUSES), status or "missing")

    if not isinstance(data.get("artifacts"), list):
        return False, data, "output.yaml artifacts must be a list"
    if not isinstance(data.get("warnings"), list):
        return False, data, "output.yaml warnings must be a list"
    if not isinstance(data.get("evidence_gaps"), list):
        return False, data, "output.yaml evidence_gaps must be a list"
    for patch_key in ("structured_record_patch", "signal_bundle_patch", "collection_report_patch"):
        if not isinstance(data.get(patch_key), dict):
            return False, data, "output.yaml %s must be an object" % patch_key
    for item in data.get("artifacts") or []:
        if not isinstance(item, dict):
            return False, data, "output.yaml artifacts entries must be objects"
        artifact_path = str(item.get("path") or "")
        if not artifact_path:
            return False, data, "output.yaml artifacts entries must include path"
        if artifact_path.startswith("/") or any(part == ".." for part in artifact_path.split("/")):
            return False, data, "output.yaml artifact paths must stay relative to artifact-dir: %s" % artifact_path
    return True, data, ""


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


def remote_kubectl_get_pods(access: Dict[str, Any], namespace: str) -> Tuple[subprocess.CompletedProcess, List[Dict[str, Any]], str]:
    proc = run_ssh(access, "kubectl get pods -n %s -o json" % shlex.quote(namespace), timeout=30)
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


def probe_pod_tool(access: Dict[str, Any], namespace: str, pod: str, candidates: List[str]) -> Tuple[bool, str, str]:
    proc = run_ssh(
        access,
        "kubectl exec -n %s %s -- sh -lc %s" % (shlex.quote(namespace), shlex.quote(pod), shlex.quote(pod_tool_probe_script(candidates))),
        timeout=30,
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
) -> Tuple[str, str, str]:
    pod_ref = mcr.pod_name(pod_item)
    pod_targets = mongo_exec.get("pod_targets") or {}
    if isinstance(pod_targets, dict):
        existing = pod_targets.get(pod_ref) or {}
        if isinstance(existing, dict) and existing.get("shell"):
            return str(existing.get("container") or ""), str(existing["shell"]), ""

    shell_candidates = [str(item) for item in (mongo_exec.get("shell_candidates") or list(mcr.DEFAULT_SHELL_CANDIDATES)) if item]
    container_candidates = mcr.container_names_for_pod(
        pod_item,
        [str(item) for item in (mongo_exec.get("container_name_candidates") or []) if item],
    )
    probe = mcr.shell_probe_command(shell_candidates)
    last_detail = ""
    for container in container_candidates:
        proc = run_ssh(
            access,
            "kubectl exec -n %s %s -c %s -- bash -c %s"
            % (shlex.quote(namespace), shlex.quote(pod_ref), shlex.quote(container), shlex.quote(probe)),
            timeout=30,
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

    pods_proc, pods, pods_error = remote_kubectl_get_pods(access, namespace)
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
                probe_pod_container_shell(access, namespace, pod_item, mongo_exec)
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
            probe_pod_container_shell(access, namespace, pod_item, mongo_exec)
    record_pod_tool_probe_summary(checks, warnings, capabilities, mongod_pod_refs, mongo_exec, "mongod")
    return True, context, checks, error, warnings


def validate_executor_capabilities(access: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]], Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    if not shutil.which("sshpass"):
        return False, [capability_result("sshpass", "blocked", "sshpass is not installed locally", "missing_sshpass")], {"code": "missing_sshpass", "message": "sshpass is not installed locally"}

    ssh_proc = run_ssh(access, "echo ok", timeout=20)
    if ssh_proc.returncode != 0:
        code = classify_ssh_error(ssh_proc.stderr)
        checks.append(capability_result("ssh", "blocked", ssh_proc.stderr.strip() or "ssh check failed", code))
        return False, checks, {"code": code, "message": ssh_proc.stderr.strip() or "ssh check failed"}
    checks.append(capability_result("ssh", "success", "ssh echo ok succeeded"))

    kubectl_proc = run_ssh(access, "kubectl version --client=true >/dev/null", timeout=20)
    if kubectl_proc.returncode != 0:
        code = classify_kubectl_error(kubectl_proc.stderr)
        checks.append(capability_result("kubectl", "blocked", kubectl_proc.stderr.strip() or "kubectl client check failed", code))
        return False, checks, {"code": code, "message": kubectl_proc.stderr.strip() or "kubectl client check failed"}
    checks.append(capability_result("kubectl", "success", "kubectl client is available"))

    cluster_proc = run_ssh(access, "kubectl get nodes -o name >/dev/null", timeout=20)
    if cluster_proc.returncode != 0:
        code = classify_kubectl_error(cluster_proc.stderr)
        checks.append(capability_result("k8s_context", "blocked", cluster_proc.stderr.strip() or "kubectl cluster access check failed", code))
        return False, checks, {"code": code, "message": cluster_proc.stderr.strip() or "kubectl cluster access check failed"}
    checks.append(capability_result("k8s_context", "success", "kubectl can access the cluster"))

    exec_proc = run_ssh(access, "kubectl auth can-i create pods/exec -A", timeout=20)
    if exec_proc.returncode != 0:
        checks.append(capability_result("kubectl_exec", "blocked", exec_proc.stderr.strip() or "kubectl exec capability check failed", "kubectl_exec_unavailable"))
        return False, checks, {"code": "kubectl_exec_unavailable", "message": exec_proc.stderr.strip() or "kubectl exec capability check failed"}
    if exec_proc.stdout.strip().lower() not in ("yes", "true"):
        checks.append(capability_result("kubectl_exec", "blocked", exec_proc.stdout.strip() or "kubectl exec is not permitted", "kubectl_exec_unavailable"))
        return False, checks, {"code": "kubectl_exec_unavailable", "message": exec_proc.stdout.strip() or "kubectl exec is not permitted"}
    checks.append(capability_result("kubectl_exec", "success", "kubectl exec capability is available"))
    return True, checks, {"code": "", "message": ""}


def ssh_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target = "%s@%s" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "ssh",
        *SSH_OPTIONS,
        "-p",
        str(access.get("port", 22)),
        target,
    ]
    return base, env


def scp_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str], str]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target_prefix = "%s@%s:" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "scp",
        "-O",
        *SSH_OPTIONS,
        "-P",
        str(access.get("port", 22)),
    ]
    return base, env, target_prefix


def run_process(command: List[str], env: Dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        message = "command timed out after %ss: %s" % (timeout, " ".join(command[:4]))
        return subprocess.CompletedProcess(command, REMOTE_COMMAND_TIMEOUT_EXIT, stdout or "", ((stderr or "") + "\n" + message).strip())


def run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> subprocess.CompletedProcess:
    base, env = ssh_base(access)
    return run_process(base + ["bash -lc %s" % shlex.quote(remote_script)], env, timeout)


def scp_to(access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
    base, env, target_prefix = scp_base(access)
    proc = run_process(base + [str(local_path), target_prefix + remote_path], env, 60)
    if proc.returncode != 0:
        raise RuntimeError("scp_to failed for %s: %s" % (local_path, proc.stderr.strip()))


def scp_from(access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
    base, env, target_prefix = scp_base(access)
    cmd = base[:]
    if recursive:
        cmd.append("-r")
    proc = run_process(cmd + [target_prefix + remote_path, str(local_path)], env, 60)
    if proc.returncode != 0:
        raise RuntimeError("scp_from failed for %s: %s" % (remote_path, proc.stderr.strip()))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def choose_namespace(access: Dict[str, Any], preferred: List[str]) -> str:
    ns_list = " ".join(shlex.quote(item) for item in preferred)
    proc = run_ssh(
        access,
        "for ns in %s; do kubectl get namespace \"$ns\" -o name >/dev/null 2>&1 && echo \"$ns\" && exit 0; done; echo default" % ns_list,
    )
    if proc.returncode != 0:
        return "default"
    return (proc.stdout.strip() or "default").splitlines()[-1]


def collect_inventory(access: Dict[str, Any], local_dir: Path) -> subprocess.CompletedProcess:
    remote = r"""
set -o pipefail
echo "## kubectl client"
kubectl version --client=true --short 2>/dev/null || kubectl version --client=true
echo "## nodes"
kubectl get nodes -o wide
echo "## namespaces"
kubectl get namespaces
echo "## statefulsets"
kubectl get statefulsets -A
echo "## services"
kubectl get services -A | head -n 200
echo "## pods"
kubectl get pods -A -o wide | head -n 200
"""
    proc = run_ssh(access, remote, timeout=90)
    (local_dir / "inventory.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (local_dir / "inventory.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    return proc


def build_context(
    incident_id: str,
    script_id: str,
    namespace: str,
    local_artifact_root: Path,
    remote_root: str,
    script_ids: List[str],
    context_profile: Dict[str, Any],
    access: Dict[str, Any] = None,
) -> Dict[str, Any]:
    run_root = "%s/runs/%s" % (remote_root, incident_id)
    auth_secret_ref = context_profile.get("auth_secret_ref") or {}
    mongos_query = {
        "shell": "mongosh",
        "database": "admin",
        "command": "getShardMap",
        "username": "root",
        "password_file_env": "MONGODB_ROOT_PASSWORD_FILE",
        "auth_database": "admin",
    }
    replicaset_query = {
        "shell": "mongosh",
        "username": "root",
        "password_file_env": "MONGODB_ROOT_PASSWORD_FILE",
        "auth_database": "admin",
    }
    if isinstance(auth_secret_ref, dict) and auth_secret_ref.get("name") and auth_secret_ref.get("key"):
        mongos_query["secret_ref"] = auth_secret_ref
        replicaset_query["secret_ref"] = auth_secret_ref
    mongo_exec = mcr.default_mongo_exec_config(mongos_query, replicaset_query)
    return {
        "incident_id": incident_id,
        "middleware": "mongodb",
        "script_id": script_id,
        "namespace": namespace,
        "cluster_id": "remote-smoke",
        "artifact_root": str(local_artifact_root),
        "deployment_architecture": context_profile.get("deployment_architecture") or "unknown",
        "topology_type": context_profile.get("topology_type") or "unknown",
        "access": dict(access or {}),
        "targets": context_profile.get("targets") or default_targets(namespace),
        "capabilities": {
            "kubectl_available": True,
            "kubectl_exec_available": True,
            "mongosh_in_pod_available": False,
        },
        "pod_query": {"mode": "by_namespace_scan"},
        "statefulset_query": {"include_yaml": True},
        "service_query": {"include_nodeport": True, "include_yaml": True},
        "node_query": {"resolve_from_pods": True},
        "mongos_query": mongos_query,
        "replicaset_query": replicaset_query,
        "mongo_exec": mongo_exec,
        "logs_query": {"tail_lines": 1000},
        "normalize_query": {"per_file_highlight_limit": 50, "total_highlight_limit": 500},
        "inputs": {
            "log_artifact_dirs": {
                "current": "%s/mongodb.collect.logs.current/artifacts" % run_root,
                "previous": "%s/mongodb.collect.logs.previous/artifacts" % run_root,
            },
            "script_output_files": {
                upstream: "%s/%s/output.yaml" % (run_root, upstream)
                for upstream in script_ids
                if upstream != "mongodb.normalize.signals.bundle"
            },
        },
    }


def text_tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def build_remote_workspace(remote_root: str, incident_id: str, script_id: str, runtime_path: str) -> Dict[str, str]:
    run_root = "%s/runs/%s/%s" % (remote_root.rstrip("/"), incident_id, script_id)
    script_path = remote_path(remote_root, runtime_path)
    return {
        "plugin_root": remote_root.rstrip("/"),
        "script_root": "%s/assets/scripts" % remote_root.rstrip("/"),
        "run_root": run_root,
        "script_path": script_path,
        "context_file": "%s/context.yaml" % run_root,
        "output_file": "%s/output.yaml" % run_root,
        "artifact_dir": "%s/artifacts" % run_root,
    }


def build_executor_request(
    access: Dict[str, Any],
    incident_id: str,
    entry: Dict[str, Any],
    remote_workspace: Dict[str, str],
    plugin_name: str,
) -> Dict[str, Any]:
    script_id = str(entry["script_id"])
    return {
        "executor_id": "remote-executor-%s-%s" % (incident_id, script_id),
        "incident_id": incident_id,
        "script_id": script_id,
        "middleware": "mongodb",
        "plugin_name": plugin_name,
        "access": access,
        "script": {
            "runtime_path": entry["runtime_path"],
            "runtime": entry["runtime"],
            "readonly": entry["readonly"],
            "arguments": {
                "context_file": "context.yaml",
                "output_file": "output.yaml",
                "artifact_dir": "artifacts",
            },
        },
        "remote_workspace": remote_workspace,
        "required_capabilities": build_required_capabilities(script_id),
        "execution": {
            "timeout_seconds": 120,
            "retrieve_output_file": True,
            "retrieve_artifact_dir": True,
        },
    }


def build_executor_result(
    request: Dict[str, Any],
    status: str,
    started_at: str,
    capability_checks: List[Dict[str, str]],
    process: Dict[str, Any],
    retrieved_files: Dict[str, str],
    error: Dict[str, str],
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        "executor_id": request["executor_id"],
        "incident_id": request["incident_id"],
        "script_id": request["script_id"],
        "plugin_name": request["plugin_name"],
        "status": status,
        "selected_ip": str((request.get("access") or {}).get("primary_ip") or ""),
        "started_at": started_at,
        "finished_at": now_iso(),
        "capability_checks": capability_checks,
        "remote_paths": request["remote_workspace"],
        "retrieved_files": retrieved_files,
        "process": process,
        "error": error,
        "warnings": warnings,
    }


def build_script_result_summary(result: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, str]:
    error = result.get("error") or {}
    summary = {
        "script_id": str(result.get("script_id") or ""),
        "status": str(result.get("status") or ""),
        "error_code": str(error.get("code") or ""),
        "error_message": str(error.get("message") or ""),
    }
    if output:
        summary["output_status"] = str(output.get("status") or "")
        summary["output_summary"] = str(output.get("summary") or "")
    return summary


def build_run_result(
    incident_id: str,
    plugin_name: str,
    selected_ip: str,
    namespace: str,
    started_at: str,
    capability_checks: List[Dict[str, str]],
    script_results: List[Dict[str, str]],
    error: Dict[str, str],
    warnings: List[str],
    status: str,
) -> Dict[str, Any]:
    return {
        "incident_id": incident_id,
        "plugin_name": plugin_name,
        "status": status,
        "selected_ip": selected_ip,
        "namespace": namespace,
        "started_at": started_at,
        "finished_at": now_iso(),
        "capability_checks": capability_checks,
        "script_results": script_results,
        "error": error,
        "warnings": warnings,
    }


def aggregate_run_status(script_results: List[Dict[str, str]]) -> str:
    if not script_results:
        return "failed"
    statuses = [str(item.get("status") or "") for item in script_results]
    if statuses and all(item == "success" for item in statuses):
        return "success"
    return "partial"


def print_run_pointer(incident_id: str, namespace: str, local_dir: Path) -> None:
    print("incident_id=%s" % incident_id)
    print("selected_namespace=%s" % namespace)
    print("local_dir=%s" % local_dir)


def print_script_results(local_dir: Path, script_ids: List[str]) -> None:
    for script_id in script_ids:
        script_dir = local_dir / script_id
        result = try_load_yaml(script_dir / "remote-executor-result.yaml") if (script_dir / "remote-executor-result.yaml").exists() else {}
        output = try_load_yaml(script_dir / "output.yaml") if (script_dir / "output.yaml").exists() else {}
        exit_code = (script_dir / "exit_code.txt").read_text(encoding="utf-8") if (script_dir / "exit_code.txt").exists() else "missing"
        executor_status = str(result.get("status") or "missing")
        if output:
            print(
                "%s: executor=%s exit=%s output_status=%s summary=%s"
                % (script_id, executor_status, exit_code, output.get("status"), output.get("summary"))
            )
        elif result:
            error = result.get("error") or {}
            print(
                "%s: executor=%s exit=%s error=%s"
                % (script_id, executor_status, exit_code, (error.get("message") or "")[:200])
            )
        else:
            print("%s: executor=missing exit=%s" % (script_id, exit_code))


def finalize_run(
    local_dir: Path,
    incident_id: str,
    plugin_name: str,
    selected_ip: str,
    namespace: str,
    started_at: str,
    capability_checks: List[Dict[str, str]],
    script_results: List[Dict[str, str]],
    error: Dict[str, str],
    warnings: List[str],
    status: str,
    return_code: int,
    script_ids: List[str],
) -> int:
    write_yaml(
        local_dir / "remote-executor-run.yaml",
        build_run_result(incident_id, plugin_name, selected_ip, namespace, started_at, capability_checks, script_results, error, warnings, status),
    )
    print_run_pointer(incident_id, namespace, local_dir)
    if script_results:
        print_script_results(local_dir, script_ids)
    return return_code


def run_script(
    access: Dict[str, Any],
    incident_id: str,
    entry: Dict[str, Any],
    namespace: str,
    local_dir: Path,
    remote_root: str,
    script_ids: List[str],
    context_profile: Dict[str, Any],
    plugin_name: str,
    capability_checks: List[Dict[str, str]],
) -> Dict[str, Any]:
    script_id = str(entry["script_id"])
    remote_workspace = build_remote_workspace(remote_root, incident_id, script_id, str(entry["runtime_path"]))
    remote_context = remote_workspace["context_file"]
    remote_output = remote_workspace["output_file"]
    remote_artifacts = remote_workspace["artifact_dir"]
    local_script_dir = local_dir / script_id
    local_script_dir.mkdir(parents=True, exist_ok=True)
    request = build_executor_request(access, incident_id, entry, remote_workspace, plugin_name)
    write_yaml(local_script_dir / "remote-executor-request.yaml", request)
    started_at = now_iso()
    process = {"exit_code": -1, "stdout_tail": "", "stderr_tail": ""}
    retrieved_files: Dict[str, str] = {}
    warnings: List[str] = []
    error = error_payload()
    status = "failed"
    output_valid = False
    script_capability_checks = list(capability_checks)

    try:
        context = build_context(incident_id, script_id, namespace, local_script_dir / "artifacts", remote_root, script_ids, context_profile, access)
        capabilities_ok, context, script_capability_checks, capability_error, capability_warnings = validate_script_capabilities(
            access, namespace, script_id, context, capability_checks
        )
        warnings.extend(capability_warnings)
        if not capabilities_ok:
            error = capability_error
            status = status_from_error_code(error["code"])
        context_path = local_script_dir / "context.yaml"
        write_json(context_path, context)
        if not capabilities_ok:
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)

        mkdir_proc = run_ssh(access, "mkdir -p %s %s" % (shlex.quote(remote_workspace["run_root"]), shlex.quote(remote_artifacts)))
        if mkdir_proc.returncode != 0:
            process = {"exit_code": mkdir_proc.returncode, "stdout_tail": text_tail(mkdir_proc.stdout), "stderr_tail": text_tail(mkdir_proc.stderr)}
            error = classify_remote_error(mkdir_proc.stderr or mkdir_proc.stdout, "remote_workspace_unavailable")
            status = status_from_error_code(error["code"])
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)
        try:
            scp_to(access, context_path, remote_context)
        except RuntimeError as exc:
            error = classify_remote_error(str(exc), "remote_workspace_unavailable")
            status = status_from_error_code(error["code"])
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)

        runner = "python3" if str(entry["runtime"]) == "python" else "bash"
        command = (
            "%s %s --context-file %s --output-file %s --artifact-dir %s"
            % (runner, shlex.quote(remote_workspace["script_path"]), shlex.quote(remote_context), shlex.quote(remote_output), shlex.quote(remote_artifacts))
        )
        proc = run_ssh(access, command, timeout=120)
        process = {"exit_code": proc.returncode, "stdout_tail": text_tail(proc.stdout), "stderr_tail": text_tail(proc.stderr)}
        (local_script_dir / "remote.stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (local_script_dir / "remote.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        (local_script_dir / "exit_code.txt").write_text(str(proc.returncode), encoding="utf-8")

        output_retrieved = False
        try:
            scp_from(access, remote_output, local_script_dir / "output.yaml")
            output_retrieved = True
            retrieved_files["output_file"] = str(local_script_dir / "output.yaml")
            output_valid, _, contract_error = validate_script_output_contract(local_script_dir / "output.yaml", script_id)
            if not output_valid:
                error = error_payload("script_contract_failed", contract_error)
        except RuntimeError as exc:
            error = error_payload("output_retrieval_failed", str(exc))

        artifact_dest = local_script_dir / "artifacts"
        if artifact_dest.exists():
            shutil.rmtree(artifact_dest)
        try:
            scp_from(access, remote_artifacts, artifact_dest, recursive=True)
            retrieved_files["artifact_dir"] = str(artifact_dest)
        except RuntimeError as exc:
            warnings.append(str(exc))
            (local_script_dir / "artifact_retrieval_error.txt").write_text(str(exc), encoding="utf-8")

        if proc.returncode == 0 and output_valid:
            status = "partial" if warnings else "success"
            error = error_payload()
        elif proc.returncode == 0:
            status = "failed"
            if not error["code"]:
                error = error_payload("script_contract_failed", "script did not produce a valid retrievable output.yaml")
        else:
            status = "failed"
            if output_valid:
                error = error_payload(
                    "script_contract_failed",
                    "script returned non-zero exit code %s after writing output.yaml" % proc.returncode,
                )
            elif not error["code"]:
                error = error_payload("script_runtime_failed", proc.stderr.strip() or "script exited with code %s" % proc.returncode)
    finally:
        result = build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)
        write_yaml(local_script_dir / "remote-executor-result.yaml", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MongoDB MVP scripts against a remote Kubernetes environment.")
    parser.add_argument("--config", required=True, help="Path to ignored local environment config YAML.")
    parser.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT), help="Local directory for smoke test results.")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT, help="Remote plugin root under /tmp.")
    parser.add_argument("--plugin-name", default=DEFAULT_PLUGIN_NAME, help="Plugin name used for remote executor workspace layout.")
    parser.add_argument("--runtime-map", default=str(DEFAULT_RUNTIME_MAP), help="Runtime map used to resolve packaged script paths.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest used to resolve source script paths.")
    parser.add_argument("--script-id", action="append", default=[], help="Run only the selected script id. May be repeated.")
    parser.add_argument("--namespace", default="", help="Explicit namespace. If omitted, a known MongoDB namespace is selected.")
    parser.add_argument("--namespace-candidates", default="mongo,psmdb-test,mongodb,default", help="Comma-separated namespace candidates.")
    parser.add_argument("--inventory-file", default="", help="Optional object-inventory.yaml from /start for topology and target hints.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    started_at = now_iso()
    incident_id = "mongodb-remote-smoke-%s" % now_id()
    local_dir = Path(args.output_dir) / incident_id
    local_dir.mkdir(parents=True, exist_ok=True)
    namespace = str(args.namespace or "")
    plugin_name = str(args.plugin_name or DEFAULT_PLUGIN_NAME)
    selected_ip = ""
    capability_checks: List[Dict[str, str]] = []
    script_results: List[Dict[str, str]] = []
    warnings: List[str] = []
    script_ids: List[str] = []
    error = error_payload()
    remote_root = args.remote_root.rstrip("/")
    try:
        cfg = load_config(Path(args.config))
        access = cfg["access"]
        selected_ip = str(access.get("primary_ip") or "")
        script_entries = load_script_entries(Path(args.manifest), Path(args.runtime_map), [str(item) for item in (args.script_id or []) if item])
        script_ids = [str(item["script_id"]) for item in script_entries]
        capabilities_ok, capability_checks, capability_error = validate_executor_capabilities(access)
        write_yaml(local_dir / "capability-checks.yaml", {"checks": capability_checks, "error": capability_error})
        if not capabilities_ok:
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                capability_error,
                warnings,
                "blocked",
                2,
                script_ids,
            )

        remote_script_roots = sorted({posixpath.dirname(remote_path(remote_root, str(item["runtime_path"]))) for item in script_entries})
        prep = run_ssh(access, "mkdir -p %s" % " ".join(shlex.quote(item) for item in remote_script_roots))
        if prep.returncode != 0:
            error = classify_remote_error(prep.stderr or prep.stdout, "remote_workspace_unavailable")
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                error,
                warnings,
                status_from_error_code(error["code"]),
                2 if status_from_error_code(error["code"]) == "blocked" else 1,
                script_ids,
            )

        for entry in script_entries:
            try:
                scp_to(access, Path(entry["source_path"]), remote_path(remote_root, str(entry["runtime_path"])))
            except RuntimeError as exc:
                error = classify_remote_error(str(exc), "script_stage_failed")
                return finalize_run(
                    local_dir,
                    incident_id,
                    plugin_name,
                    selected_ip,
                    namespace,
                    started_at,
                    capability_checks,
                    script_results,
                    error,
                    warnings,
                    status_from_error_code(error["code"]),
                    2 if status_from_error_code(error["code"]) == "blocked" else 1,
                    script_ids,
                )

        remote_shell_paths = [remote_path(remote_root, str(item["runtime_path"])) for item in script_entries if str(item["runtime"]) == "shell"]
        if remote_shell_paths:
            chmod = run_ssh(access, "chmod +x %s" % " ".join(shlex.quote(item) for item in remote_shell_paths))
            if chmod.returncode != 0:
                error = classify_remote_error(chmod.stderr or chmod.stdout, "script_stage_failed")
                return finalize_run(
                    local_dir,
                    incident_id,
                    plugin_name,
                    selected_ip,
                    namespace,
                    started_at,
                    capability_checks,
                    script_results,
                    error,
                    warnings,
                    status_from_error_code(error["code"]),
                    2 if status_from_error_code(error["code"]) == "blocked" else 1,
                    script_ids,
                )

        if not namespace:
            namespace = choose_namespace(access, [item.strip() for item in args.namespace_candidates.split(",") if item.strip()])
        (local_dir / "selected_namespace.txt").write_text(namespace, encoding="utf-8")
        inventory_proc = collect_inventory(access, local_dir)
        if inventory_proc.returncode != 0:
            error = classify_remote_error(inventory_proc.stderr or inventory_proc.stdout, "inventory_collection_failed")
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                error,
                warnings,
                status_from_error_code(error["code"]),
                2 if status_from_error_code(error["code"]) == "blocked" else 1,
                script_ids,
            )

        context_profile = context_profile_from_inventory(args.inventory_file, namespace)
        write_yaml(local_dir / "context-profile.yaml", context_profile)

        for entry in script_entries:
            result = run_script(access, incident_id, entry, namespace, local_dir, remote_root, script_ids, context_profile, plugin_name, capability_checks)
            output = try_load_yaml(local_dir / str(entry["script_id"]) / "output.yaml")
            script_results.append(build_script_result_summary(result, output))

        return finalize_run(
            local_dir,
            incident_id,
            plugin_name,
            selected_ip,
            namespace,
            started_at,
            capability_checks,
            script_results,
            error,
            warnings,
            aggregate_run_status(script_results),
            0,
            script_ids,
        )
    except Exception as exc:
        error = error_payload("remote_executor_failed", str(exc))
        return finalize_run(
            local_dir,
            incident_id,
            plugin_name,
            selected_ip,
            namespace,
            started_at,
            capability_checks,
            script_results,
            error,
            warnings,
            "failed",
            1,
            script_ids,
        )


if __name__ == "__main__":
    raise SystemExit(main())
