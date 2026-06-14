"""MongoDB in-Pod collection target resolution for plugin / remote-executor runtime."""

from __future__ import annotations

import shlex
from typing import Any, Dict, List, Optional, Tuple

MONGO_CONTAINER_NAME_CANDIDATES = ("mongod", "mongo", "mongodb", "mongos")
DEFAULT_SHELL_CANDIDATES = ("mongosh", "mongo")


def pod_name(pod: Dict[str, Any]) -> str:
    return str((((pod.get("metadata") or {}).get("name")) or ""))


def pod_phase(pod: Dict[str, Any]) -> str:
    return str((((pod.get("status") or {}).get("phase")) or ""))


def pod_label_text(pod: Dict[str, Any]) -> str:
    labels = (((pod.get("metadata") or {}).get("labels")) or {})
    return " ".join("%s=%s" % (str(key).lower(), str(value).lower()) for key, value in labels.items())


def pod_is_running(pod: Dict[str, Any]) -> bool:
    return pod_phase(pod) == "Running"


def pod_is_ready(pod: Dict[str, Any]) -> bool:
    for item in ((pod.get("status") or {}).get("conditions") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "") == "Ready" and str(item.get("status") or "") == "True":
            return True
    return False


def operational_sort_key(pod: Dict[str, Any]) -> Tuple[int, str]:
    return (0 if pod_is_ready(pod) else 1, pod_name(pod))


def is_mongos_pod(pod: Dict[str, Any]) -> bool:
    name = pod_name(pod).lower()
    label_text = pod_label_text(pod)
    if "operator" in name:
        return False
    if "mongos" in name:
        return True
    return "component=mongos" in label_text


def is_mongod_pod(pod: Dict[str, Any]) -> bool:
    name = pod_name(pod).lower()
    label_text = pod_label_text(pod)
    if "mongos" in name or "operator" in name:
        return False
    if "configsvr" in name or "shard" in name:
        return True
    return any(
        token in label_text
        for token in ("component=configsvr", "component=shard", "component=shardsvr")
    )


def resolve_running_mongos_pods(pods: List[Dict[str, Any]]) -> List[str]:
    candidates = [pod for pod in pods if is_mongos_pod(pod) and pod_is_running(pod)]
    candidates.sort(key=operational_sort_key)
    result: List[str] = []
    for pod in candidates:
        name = pod_name(pod)
        if name and name not in result:
            result.append(name)
    return result


def resolve_running_mongod_pods(pods: List[Dict[str, Any]]) -> List[str]:
    candidates = [pod for pod in pods if is_mongod_pod(pod) and pod_is_running(pod)]
    candidates.sort(key=operational_sort_key)
    result: List[str] = []
    for pod in candidates:
        name = pod_name(pod)
        if name and name not in result:
            result.append(name)
    return result


def pod_by_name(pods: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for pod in pods:
        name = pod_name(pod)
        if name:
            mapping[name] = pod
    return mapping


def container_names_for_pod(
    pod: Dict[str, Any],
    extra_candidates: Optional[List[str]] = None,
) -> List[str]:
    """Return only container names declared on the Pod spec (first container first)."""
    spec = pod.get("spec") or {}
    containers = spec.get("containers") or []
    names = [
        str(item.get("name") or "")
        for item in containers
        if isinstance(item, dict) and item.get("name")
    ]
    if not names:
        return []

    ordered: List[str] = []
    seen = set()

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    add(names[0])
    for candidate in list(extra_candidates or []) + list(MONGO_CONTAINER_NAME_CANDIDATES):
        if candidate in names:
            add(candidate)
    for name in names:
        add(name)
    return ordered


def default_mongo_exec_config(
    mongos_query: Optional[Dict[str, Any]] = None,
    replicaset_query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    shell = "mongosh"
    for query in (mongos_query or {}, replicaset_query or {}):
        if query.get("shell"):
            shell = str(query.get("shell"))
            break
    shell_candidates = [shell]
    if shell == "mongosh":
        shell_candidates.append("mongo")
    return {
        "container_name_candidates": list(MONGO_CONTAINER_NAME_CANDIDATES),
        "shell_candidates": shell_candidates,
        "pod_targets": {},
    }


def shell_probe_command(shell_candidates: List[str]) -> str:
    checks = [
        "(command -v %s >/dev/null 2>&1 && command -v %s)" % (shlex.quote(item), shlex.quote(item))
        for item in shell_candidates
        if item
    ]
    if not checks:
        checks = [
            "(command -v mongosh >/dev/null 2>&1 && command -v mongosh)",
            "(command -v mongo >/dev/null 2>&1 && command -v mongo)",
        ]
    return " || ".join(checks)


def resolve_mongodb_collection_targets(
    pods: List[Dict[str, Any]],
    *,
    mongos_query: Optional[Dict[str, Any]] = None,
    replicaset_query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    mongos_pod_refs = resolve_running_mongos_pods(pods)
    mongod_pod_refs = resolve_running_mongod_pods(pods)
    mongo_exec = default_mongo_exec_config(mongos_query, replicaset_query)
    return {
        "mongos_pod_refs": mongos_pod_refs,
        "mongod_pod_refs": mongod_pod_refs,
        "mongos_pod_ref": mongos_pod_refs[0] if mongos_pod_refs else "",
        "pod_refs": mongod_pod_refs,
        "mongo_exec": mongo_exec,
        "pod_by_name": pod_by_name(pods),
    }


def merge_pod_exec_target(
    mongo_exec: Dict[str, Any],
    pod_ref: str,
    container: str,
    shell: str,
) -> None:
    pod_targets = mongo_exec.setdefault("pod_targets", {})
    if not isinstance(pod_targets, dict):
        mongo_exec["pod_targets"] = {}
        pod_targets = mongo_exec["pod_targets"]
    pod_targets[pod_ref] = {"container": container, "shell": shell}


def summarize_pod_tool_probe(
    pod_refs: List[str],
    mongo_exec: Dict[str, Any],
) -> Tuple[int, int, bool]:
    pod_targets = mongo_exec.get("pod_targets") or {}
    if not isinstance(pod_targets, dict):
        pod_targets = {}
    available = sum(1 for pod in pod_refs if pod in pod_targets and pod_targets[pod].get("shell"))
    return available, len(pod_refs), available > 0

