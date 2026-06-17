"""Kubernetes object normalization helpers for Phase 2 inventory."""

from __future__ import annotations

import json
from typing import Any, Dict, List


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


def object_matches_mongodb(obj: Dict[str, Any]) -> bool:
    text = json.dumps(obj, ensure_ascii=False).lower()
    name = object_name(obj).lower()
    data_plane_hints = ("mongos", "mongod", "configsvr", "shard", "replica", "rs", "data")
    if "operator" in name and not any(hint in text for hint in data_plane_hints):
        return False
    return any(hint in text for hint in MONGODB_DISCOVERY_HINTS)
