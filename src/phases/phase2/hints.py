"""Inventory hint builders for Phase 2."""

from __future__ import annotations

from typing import Any, Dict, List

from .objects import object_name, object_namespace


def container_specs_for_auth(kind: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if kind == "Pod":
        spec = obj.get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    if kind == "StatefulSet":
        spec = ((obj.get("spec") or {}).get("template") or {}).get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    return []


def auth_secret_ref_score(env_name: str, key: str, roles: List[str], kind: str) -> int:
    score = 0
    text = ("%s %s" % (env_name, key)).lower()
    if "root" in text:
        score += 30
    if "password" in text:
        score += 20
    if "mongos" in roles or "configsvr" in roles or "shard" in roles or "replicaset" in roles:
        score += 10
    if kind == "StatefulSet":
        score += 5
    return score


def mongodb_auth_secret_refs(kind: str, obj: Dict[str, Any], roles: List[str]) -> List[Dict[str, Any]]:
    namespace = object_namespace(obj)
    source_name = object_name(obj)
    candidates = []
    for container in container_specs_for_auth(kind, obj):
        container_name = str(container.get("name") or "")
        for env in container.get("env") or []:
            if not isinstance(env, dict):
                continue
            secret_key_ref = (((env.get("valueFrom") or {}).get("secretKeyRef")) or {})
            secret_name = str(secret_key_ref.get("name") or "")
            secret_key = str(secret_key_ref.get("key") or "")
            if not secret_name or not secret_key:
                continue
            env_name = str(env.get("name") or "")
            candidates.append(
                {
                    "namespace": namespace,
                    "name": secret_name,
                    "key": secret_key,
                    "env_name": env_name,
                    "source_kind": kind,
                    "source_name": source_name,
                    "source_container": container_name,
                    "score": auth_secret_ref_score(env_name, secret_key, roles, kind),
                }
            )
    return candidates


def append_auth_secret_ref_candidate(target: List[Dict[str, Any]], candidate: Dict[str, Any]) -> None:
    key = (str(candidate.get("namespace") or ""), str(candidate.get("name") or ""), str(candidate.get("key") or ""))
    for index, existing in enumerate(target):
        existing_key = (str(existing.get("namespace") or ""), str(existing.get("name") or ""), str(existing.get("key") or ""))
        if existing_key == key:
            if int(candidate.get("score") or 0) > int(existing.get("score") or 0):
                target[index] = candidate
            return
    target.append(candidate)


def build_auth_hints(selected_namespace: str, auth_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    scoped = [item for item in auth_candidates if str(item.get("namespace") or "") == selected_namespace]
    scoped.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("name") or ""), str(item.get("key") or "")))
    selected_secret_ref = {}
    if scoped:
        selected_secret_ref = {"namespace": str(scoped[0].get("namespace") or ""), "name": str(scoped[0].get("name") or ""), "key": str(scoped[0].get("key") or "")}
    return {"secret_ref_candidates": scoped, "selected_secret_ref": selected_secret_ref}


def append_unique(target: List[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def inventory_scope_objects(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected_namespace = str(inventory.get("selected_namespace") or "")
    objects = [item for item in inventory.get("objects") or [] if isinstance(item, dict)]
    if not selected_namespace:
        return objects
    return [item for item in objects if str(item.get("namespace") or "") == selected_namespace]


def build_mongodb_targets(namespace: str, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    targets: Dict[str, Any] = {
        "namespace": namespace,
        "statefulset_refs": [],
        "service_refs": [],
        "pod_refs": [],
        "node_refs": [],
        "mongos_pod_ref": "",
    }
    if not namespace:
        return targets
    for item in objects:
        name = str(item.get("name") or "")
        if not name:
            continue
        kind = item.get("kind")
        if kind == "StatefulSet":
            append_unique(targets["statefulset_refs"], name)
        elif kind == "Service":
            append_unique(targets["service_refs"], name)
        elif kind == "Pod":
            append_unique(targets["pod_refs"], name)
            node_name = str(item.get("node_name") or "")
            append_unique(targets["node_refs"], node_name)
            if not targets["mongos_pod_ref"] and "mongos" in (item.get("mongodb_role_hints") or []):
                targets["mongos_pod_ref"] = name
    for key in ("statefulset_refs", "service_refs", "pod_refs", "node_refs"):
        targets[key] = sorted(targets[key])
    return targets


def build_topology_hints(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    role_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}
    for item in objects:
        kind = str(item.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        for role in item.get("mongodb_role_hints") or ["unknown"]:
            role_counts[str(role)] = role_counts.get(str(role), 0) + 1
    if role_counts.get("mongos") or (role_counts.get("configsvr") and role_counts.get("shard")):
        topology_type = "sharded_cluster"
    elif role_counts.get("replicaset"):
        topology_type = "replica_set"
    else:
        topology_type = "unknown"
    return {"candidate_topology_type": topology_type, "role_counts": dict(sorted(role_counts.items())), "kind_counts": dict(sorted(kind_counts.items()))}


def deployment_architecture_candidates(objects: List[Dict[str, Any]]) -> List[str]:
    candidates: List[str] = []
    for item in objects:
        for hint in item.get("deployment_architecture_hints") or []:
            append_unique(candidates, str(hint))
    return sorted(candidates)


def related_event(event: Dict[str, Any], names: List[str]) -> bool:
    involved = event.get("involvedObject") or event.get("regarding") or {}
    return str(involved.get("name") or "") in names
