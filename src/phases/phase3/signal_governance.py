"""Phase 3 signal grouping and correlation helpers."""

from __future__ import annotations

from typing import Any, Dict, List

from shared.workspace import load_yaml, now_iso, write_yaml


ORCHESTRATION_SIGNAL_IDS = {
    "pod-unschedulable",
    "pod-node-selector-mismatch",
    "pod-volume-binding-failed",
    "pod-image-pull-failed",
    "statefulset-replicas-not-ready",
}

SIGNAL_CATEGORY_BY_ID = {
    "node-memory-pressure": "resource_pressure",
    "node-disk-pressure": "resource_pressure",
    "node-resource-pressure": "resource_pressure",
    "pod-resource-insufficient": "resource_pressure",
    "pod-resource-pressure": "resource_pressure",
    "pod-unschedulable": "runtime_failure",
    "pod-node-selector-mismatch": "runtime_failure",
    "pod-volume-binding-failed": "runtime_failure",
    "pod-image-pull-failed": "runtime_failure",
    "pod-crashloop": "runtime_failure",
    "pod-not-ready": "runtime_failure",
    "statefulset-replicas-not-ready": "runtime_failure",
    "dns-resolution-failed": "network_dns",
    "dns-control-plane-unhealthy": "network_dns",
    "flannel-vxlan-down": "network_overlay",
    "flannel-route-install-failed": "network_overlay",
    "kube-dns-backend-on-overlay-partition": "network_overlay",
    "pod-subnet-isolated": "network_overlay",
    "replica-member-recovering": "replica_health",
    "replica-member-unhealthy": "replica_health",
    "replication-lag-high": "replica_health",
    "stale-read-risk": "replica_health",
    "service-endpoints-not-ready": "service_connectivity",
    "mongos-pod-not-ready": "service_connectivity",
    "connection-refused": "service_connectivity",
    "connection-timeout": "service_connectivity",
    "authentication-failed": "service_connectivity",
    "latency-spike": "service_performance",
    "slow-operation": "service_performance",
    "shard-imbalance": "service_distribution",
    "chunk-imbalance": "service_distribution",
    "hotspot-key": "service_distribution",
}


def signal_layer(signal: Dict[str, Any]) -> str:
    object_ref = str(signal.get("object_ref") or "")
    signal_id = str(signal.get("signal_id") or "")
    if object_ref.startswith("node/"):
        return "node"
    if object_ref.startswith("statefulset/") or signal_id in ORCHESTRATION_SIGNAL_IDS:
        return "orchestration"
    if object_ref.startswith("pod/"):
        return "pod"
    if object_ref.startswith("endpoint/"):
        return "network"
    if object_ref.startswith("service/"):
        return "service"
    if object_ref.startswith("replicaset/") or signal_id.startswith("replica-") or signal_id.startswith("replication-"):
        return "service"
    if signal_id.startswith("flannel-") or signal_id.startswith("dns-") or signal_id.startswith("pod-subnet-"):
        return "network"
    return "unknown"


def signal_category(signal_id: str) -> str:
    return SIGNAL_CATEGORY_BY_ID.get(signal_id, "unknown")


def _group_key(signal: Dict[str, Any]) -> tuple[str, str, str]:
    signal_id = str(signal.get("signal_id") or "")
    return (
        signal_layer(signal),
        signal_category(signal_id),
        str(signal.get("object_ref") or "unknown"),
    )


def build_signal_groups(signal_bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    groups: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for signal in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(signal, dict):
            continue
        key = _group_key(signal)
        group = groups.setdefault(
            key,
            {
                "layer": key[0],
                "category": key[1],
                "object_ref": key[2],
                "signals": [],
                "severity": str(signal.get("severity") or ""),
            },
        )
        signal_id = str(signal.get("signal_id") or "")
        if signal_id and signal_id not in group["signals"]:
            group["signals"].append(signal_id)
        if str(signal.get("severity") or "") == "critical":
            group["severity"] = "critical"
    return sorted(groups.values(), key=lambda item: (item["layer"], item["category"], item["object_ref"]))


def _pod_refs_by_name(structured_record: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    refs: Dict[str, Dict[str, str]] = {}
    for pod in ((structured_record.get("details") or {}).get("pods") or []):
        if not isinstance(pod, dict):
            continue
        name = str(pod.get("name") or pod.get("pod_ref") or "")
        if not name:
            continue
        refs[name] = {
            "pod_ref": "pod/%s" % name,
            "node_ref": "node/%s" % pod.get("node_ref") if pod.get("node_ref") else "",
        }
    return refs


def build_correlations(structured_record: Dict[str, Any]) -> List[Dict[str, str]]:
    correlations: List[Dict[str, str]] = []
    pods = _pod_refs_by_name(structured_record)
    for pod in pods.values():
        if pod.get("node_ref"):
            correlations.append(
                {
                    "type": "co_location",
                    "from": pod["pod_ref"],
                    "to": pod["node_ref"],
                    "basis": "structured_record.details.pods.node_ref",
                }
            )

    for member in ((structured_record.get("details") or {}).get("replica_members") or []):
        if not isinstance(member, dict):
            continue
        replica_set_id = str(member.get("replica_set_id") or "")
        source_pod = str(member.get("source_pod_ref") or "")
        if not replica_set_id or not source_pod:
            continue
        pod_ref = source_pod if source_pod.startswith("pod/") else "pod/%s" % source_pod
        correlations.append(
            {
                "type": "service_pod_source",
                "from": "replicaset/%s" % replica_set_id,
                "to": pod_ref,
                "basis": "structured_record.details.replica_members.source_pod_ref",
            }
        )
    return correlations


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(float(numerator) / float(denominator), 3)


def _pods_by_ref(structured_record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    pods: Dict[str, Dict[str, Any]] = {}
    for pod in ((structured_record.get("details") or {}).get("pods") or []):
        if not isinstance(pod, dict):
            continue
        name = str(pod.get("name") or pod.get("pod_ref") or "")
        if name:
            pods["pod/%s" % name] = pod
    return pods


def _resource_metrics(structured_record: Dict[str, Any]) -> Dict[str, Any]:
    return ((structured_record.get("details") or {}).get("resource_metrics") or {})


def _node_metrics_by_ref(structured_record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    nodes: Dict[str, Dict[str, Any]] = {}
    for node in _resource_metrics(structured_record).get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_ref = str(node.get("node_ref") or "")
        if node_ref:
            nodes["node/%s" % node_ref] = node
    return nodes


def _pod_metrics_by_ref(structured_record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    pods: Dict[str, Dict[str, Any]] = {}
    for pod in _resource_metrics(structured_record).get("pods") or []:
        if not isinstance(pod, dict):
            continue
        pod_ref = str(pod.get("pod_ref") or "")
        if pod_ref:
            pods["pod/%s" % pod_ref] = pod
    return pods


def _pod_resource_pressure_context(
    object_ref: str,
    pod_metrics: Dict[str, Dict[str, Any]],
    pod_records: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    usage = pod_metrics.get(object_ref) or {}
    pod = pod_records.get(object_ref) or {}
    profile = pod.get("resource_profile") or {}
    requests = profile.get("requests") or {}
    limits = profile.get("limits") or {}
    usage_cpu = int(usage.get("cpu_millicores") or 0)
    usage_memory = int(usage.get("memory_mi") or 0)
    request_cpu = int(requests.get("cpu_millicores") or 0)
    request_memory = int(requests.get("memory_mi") or 0)
    limit_cpu = int(limits.get("cpu_millicores") or 0)
    limit_memory = int(limits.get("memory_mi") or 0)
    return {
        "usage": {
            "cpu_millicores": usage_cpu,
            "memory_mi": usage_memory,
        },
        "requests": {
            "cpu_millicores": request_cpu,
            "memory_mi": request_memory,
        },
        "limits": {
            "cpu_millicores": limit_cpu,
            "memory_mi": limit_memory,
        },
        "usage_to_request": {
            "cpu_ratio": _ratio(usage_cpu, request_cpu),
            "memory_ratio": _ratio(usage_memory, request_memory),
        },
        "usage_to_limit": {
            "cpu_ratio": _ratio(usage_cpu, limit_cpu),
            "memory_ratio": _ratio(usage_memory, limit_memory),
        },
        "node_ref": "node/%s" % pod.get("node_ref") if pod.get("node_ref") else "",
    }


def build_signal_contexts(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    contexts: List[Dict[str, Any]] = []
    node_metrics = _node_metrics_by_ref(structured_record)
    pod_metrics = _pod_metrics_by_ref(structured_record)
    pod_records = _pods_by_ref(structured_record)
    for signal in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(signal, dict):
            continue
        signal_id = str(signal.get("signal_id") or "")
        object_ref = str(signal.get("object_ref") or "")
        if signal_id == "node-resource-pressure" and object_ref in node_metrics:
            contexts.append(
                {
                    "object_ref": object_ref,
                    "signal_id": signal_id,
                    "resource_pressure": node_metrics[object_ref],
                }
            )
        elif signal_id == "pod-resource-pressure" and object_ref in pod_metrics:
            contexts.append(
                {
                    "object_ref": object_ref,
                    "signal_id": signal_id,
                    "resource_pressure": _pod_resource_pressure_context(object_ref, pod_metrics, pod_records),
                }
            )
    return contexts


def build_signal_governance(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "signal_groups": build_signal_groups(signal_bundle),
        "correlations": build_correlations(structured_record),
        "signal_contexts": build_signal_contexts(structured_record, signal_bundle),
    }


def write_signal_governance(output_dir) -> Dict[str, Any]:
    structured_record = load_yaml(output_dir / "structured_record.yaml")
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml")
    governance = build_signal_governance(structured_record, signal_bundle)
    signal_bundle["signal_groups"] = governance["signal_groups"]
    signal_bundle["correlations"] = governance["correlations"]
    signal_bundle["signal_contexts"] = governance["signal_contexts"]
    signal_bundle["updated_at"] = now_iso()
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    return governance
