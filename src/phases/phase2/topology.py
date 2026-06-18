"""Topology hint builders for Phase 2 inventory."""

from __future__ import annotations

from typing import Any, Dict, List

from .targets import append_unique


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
