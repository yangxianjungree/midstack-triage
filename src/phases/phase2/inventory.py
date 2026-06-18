"""Phase 2 inventory helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from .auth import (
    append_auth_secret_ref_candidate,
    build_auth_hints,
    mongodb_auth_secret_refs,
)
from .hints import (
    build_mongodb_targets,
    build_topology_hints,
    deployment_architecture_candidates,
    inventory_scope_objects,
    related_event,
)
from .objects import (
    compact_k8s_object,
    deployment_architecture_hints,
    mongodb_role_hints,
    object_matches_mongodb,
    object_name,
)
from .kubectl import run_remote_kubectl_json as _run_remote_kubectl_json


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    return _run_remote_kubectl_json(access, resource, namespace, namespaced)


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
