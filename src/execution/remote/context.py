"""Remote execution context helpers."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List

from execution.remote.access import run_ssh
from execution.remote import mongodb_collection_runtime as mcr
from execution.remote.runtime_support import write_json, load_config

RunSshFn = Callable[[Dict[str, Any], str, int], subprocess.CompletedProcess]


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


def choose_namespace(access: Dict[str, Any], preferred: List[str], run_ssh_fn: RunSshFn = run_ssh) -> str:
    ns_list = " ".join(shlex.quote(item) for item in preferred)
    proc = run_ssh_fn(
        access,
        "for ns in %s; do kubectl get namespace \"$ns\" -o name >/dev/null 2>&1 && echo \"$ns\" && exit 0; done; echo default" % ns_list,
    )
    if proc.returncode != 0:
        return "default"
    return (proc.stdout.strip() or "default").splitlines()[-1]


def collect_inventory(access: Dict[str, Any], local_dir: Path, run_ssh_fn: RunSshFn = run_ssh) -> subprocess.CompletedProcess:
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
    proc = run_ssh_fn(access, remote, timeout=90)
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
    access: Dict[str, Any] | None = None,
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
        "cluster_id": "remote-run",
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
                "current": [
                    "%s/mongodb.collect.logs.current/artifacts" % run_root,
                    "%s/kubernetes.collect.logs.current/artifacts" % run_root,
                ],
                "previous": [
                    "%s/mongodb.collect.logs.previous/artifacts" % run_root,
                    "%s/kubernetes.collect.logs.previous/artifacts" % run_root,
                ],
            },
            "script_output_files": {
                upstream: "%s/%s/output.yaml" % (run_root, upstream)
                for upstream in script_ids
                if upstream != "mongodb.normalize.signals.bundle"
            },
        },
    }
