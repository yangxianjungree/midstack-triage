"""Phase 2 inventory helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from execution.remote.access import run_env_check


MONGODB_DISCOVERY_HINTS = ("mongo", "mongodb", "mongos", "mongod", "configsvr", "shard", "psmdb", "percona")


def object_namespace(obj: Dict[str, Any]) -> str:
    metadata = obj.get("metadata") or {}
    return str(metadata.get("namespace") or "")


def object_name(obj: Dict[str, Any]) -> str:
    metadata = obj.get("metadata") or {}
    return str(metadata.get("name") or "")


def condition_summary(status: Dict[str, Any]) -> List[Dict[str, str]]:
    summary = []
    for condition in status.get("conditions") or []:
        summary.append(
            {
                "type": str(condition.get("type") or ""),
                "status": str(condition.get("status") or ""),
                "reason": str(condition.get("reason") or ""),
                "message": str(condition.get("message") or ""),
            }
        )
    return summary


def compact_k8s_object(kind: str, obj: Dict[str, Any]) -> Dict[str, Any]:
    metadata = obj.get("metadata") or {}
    spec = obj.get("spec") or {}
    status = obj.get("status") or {}
    record: Dict[str, Any] = {
        "kind": kind,
        "namespace": object_namespace(obj),
        "name": object_name(obj),
        "labels": metadata.get("labels") or {},
    }
    if kind == "Pod":
        record.update({"phase": status.get("phase"), "node_name": spec.get("nodeName"), "restart_policy": spec.get("restartPolicy")})
    elif kind == "StatefulSet":
        record.update(
            {
                "replicas": spec.get("replicas"),
                "ready_replicas": status.get("readyReplicas"),
                "current_replicas": status.get("currentReplicas"),
                "updated_replicas": status.get("updatedReplicas"),
            }
        )
    elif kind == "Service":
        ports = []
        for port in spec.get("ports") or []:
            ports.append(
                {
                    "name": port.get("name"),
                    "port": port.get("port"),
                    "target_port": port.get("targetPort"),
                    "node_port": port.get("nodePort"),
                    "protocol": port.get("protocol"),
                }
            )
        record.update({"type": spec.get("type"), "ports": ports})
    elif kind == "Node":
        record.update({"conditions": condition_summary(status), "capacity": status.get("capacity") or {}, "allocatable": status.get("allocatable") or {}})
    elif kind == "Event":
        involved = obj.get("involvedObject") or obj.get("regarding") or {}
        series = obj.get("series") or {}
        record.update(
            {
                "type": obj.get("type") or obj.get("deprecatedType") or "",
                "reason": obj.get("reason") or "",
                "message": obj.get("message") or obj.get("note") or "",
                "involved_object": {
                    "kind": involved.get("kind") or "",
                    "namespace": involved.get("namespace") or "",
                    "name": involved.get("name") or "",
                },
                "first_timestamp": obj.get("firstTimestamp") or obj.get("deprecatedFirstTimestamp") or obj.get("eventTime") or "",
                "last_timestamp": obj.get("lastTimestamp") or obj.get("deprecatedLastTimestamp") or series.get("lastObservedTime") or obj.get("eventTime") or "",
            }
        )
    return record


def mongodb_role_hints(obj: Dict[str, Any]) -> List[str]:
    text = json.dumps(obj, ensure_ascii=False).lower()
    roles = []
    for role, hints in (("mongos", ("mongos",)), ("configsvr", ("configsvr", "config-server", "configserver")), ("shard", ("shard",)), ("replicaset", ("replicaset", "replica-set", "rs.")), ("operator", ("operator", "psmdb-operator"))):
        if any(hint in text for hint in hints):
            roles.append(role)
    return roles or ["unknown"]


def deployment_architecture_hints(obj: Dict[str, Any]) -> List[str]:
    text = json.dumps(obj, ensure_ascii=False).lower()
    hints = []
    if "bitnami" in text:
        hints.append("bitnami")
    if "percona.com" in text or "psmdb" in text or "psmdb-operator" in text:
        hints.append("operator_crd")
    return hints


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


def object_matches_mongodb(obj: Dict[str, Any]) -> bool:
    text = json.dumps(obj, ensure_ascii=False).lower()
    name = object_name(obj).lower()
    data_plane_hints = ("mongos", "mongod", "configsvr", "shard", "replica", "rs", "data")
    if "operator" in name and not any(hint in text for hint in data_plane_hints):
        return False
    return any(hint in text for hint in MONGODB_DISCOVERY_HINTS)


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    if namespaced:
        scope = "-n %s" % namespace if namespace else "-A"
    else:
        scope = ""
    result = run_env_check(access, "kubectl get %s %s -o json" % (resource, scope))
    if result["status"] != "passed":
        return {"status": "failed", "resource": resource, "error": result}
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "failed", "resource": resource, "error": {"message": str(exc), "stdout": result.get("stdout", "")[:1000]}}
    return {"status": "passed", "resource": resource, "payload": payload}


def discover_mongodb_inventory(access: Dict[str, Any], namespace: str) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {
        "status": "running",
        "middleware": "mongodb",
        "requested_namespace": namespace,
        "selected_namespace": namespace,
        "namespace_source": "user" if namespace else "",
        "candidate_namespaces": [],
        "objects": [],
        "targets": {
            "namespace": namespace,
            "statefulset_refs": [],
            "service_refs": [],
            "pod_refs": [],
            "node_refs": [],
            "mongos_pod_ref": "",
        },
        "deployment_architecture_candidates": [],
        "topology_hints": {},
        "auth_hints": {"secret_ref_candidates": [], "selected_secret_ref": {}},
        "related_nodes": [],
        "related_events": [],
        "errors": [],
    }
    resources = [("Pod", "pods"), ("StatefulSet", "statefulsets"), ("Service", "services")]
    candidates = set()
    auth_candidates: List[Dict[str, Any]] = []
    for kind, resource in resources:
        result = run_remote_kubectl_json(access, resource, namespace)
        if result["status"] != "passed":
            inventory["errors"].append({"resource": resource, "error": result.get("error")})
            continue
        for obj in (result.get("payload") or {}).get("items") or []:
            if not object_matches_mongodb(obj):
                continue
            roles = mongodb_role_hints(obj)
            record = compact_k8s_object(kind, obj)
            record["mongodb_role_hints"] = roles
            record["deployment_architecture_hints"] = deployment_architecture_hints(obj)
            inventory["objects"].append(record)
            for candidate in mongodb_auth_secret_refs(kind, obj, roles):
                append_auth_secret_ref_candidate(auth_candidates, candidate)
            if record.get("namespace"):
                candidates.add(str(record["namespace"]))

    inventory["candidate_namespaces"] = sorted(candidates)
    if namespace:
        inventory["status"] = "passed"
        inventory["selected_namespace"] = namespace
        inventory["namespace_source"] = "user"
    elif len(candidates) == 1:
        inventory["status"] = "passed"
        inventory["selected_namespace"] = next(iter(candidates))
        inventory["namespace_source"] = "auto_discovered"
    elif len(candidates) > 1:
        inventory["status"] = "ambiguous"
        inventory["namespace_source"] = "ambiguous"
    else:
        inventory["status"] = "not_found"
        inventory["namespace_source"] = "not_found"

    scope_objects = inventory_scope_objects(inventory)
    selected_namespace = str(inventory.get("selected_namespace") or "")
    inventory["targets"] = build_mongodb_targets(selected_namespace, scope_objects)
    inventory["deployment_architecture_candidates"] = deployment_architecture_candidates(scope_objects)
    inventory["topology_hints"] = build_topology_hints(scope_objects)
    inventory["auth_hints"] = build_auth_hints(selected_namespace, auth_candidates)

    node_names = inventory["targets"].get("node_refs") or []
    if selected_namespace and node_names:
        node_result = run_remote_kubectl_json(access, "nodes", "", namespaced=False)
        if node_result["status"] != "passed":
            inventory["errors"].append({"resource": "nodes", "error": node_result.get("error")})
        else:
            for obj in (node_result.get("payload") or {}).get("items") or []:
                if object_name(obj) in node_names:
                    inventory["related_nodes"].append(compact_k8s_object("Node", obj))

    object_names = sorted(str(item.get("name") or "") for item in scope_objects if item.get("name"))
    if selected_namespace and object_names:
        event_result = run_remote_kubectl_json(access, "events", selected_namespace)
        if event_result["status"] != "passed":
            inventory["errors"].append({"resource": "events", "error": event_result.get("error")})
        else:
            for obj in (event_result.get("payload") or {}).get("items") or []:
                if related_event(obj, object_names):
                    inventory["related_events"].append(compact_k8s_object("Event", obj))
    return inventory
