"""MongoDB target builders for Phase 2 inventory."""

from __future__ import annotations

from typing import Any, Dict, List


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
