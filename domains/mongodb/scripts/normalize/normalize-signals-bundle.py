#!/usr/bin/env python3

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_data(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        if yaml is not None:
            data = yaml.safe_load(fh) or {}
        else:
            data = json.load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("file must contain an object: %s" % path)
    return data


def write_data(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if yaml is not None:
            yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)
        else:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")


def parse_args(argv: List[str]) -> Tuple[str, str, str]:
    context_file = ""
    output_file = ""
    artifact_dir = ""
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--context-file":
            context_file = argv[index + 1]
            index += 2
        elif arg == "--output-file":
            output_file = argv[index + 1]
            index += 2
        elif arg == "--artifact-dir":
            artifact_dir = argv[index + 1]
            index += 2
        elif arg in ("-h", "--help"):
            print("Usage: normalize-signals-bundle.py --context-file <path> --output-file <path> --artifact-dir <path>")
            raise SystemExit(0)
        else:
            raise ValueError("unknown argument: %s" % arg)
    if not context_file or not output_file or not artifact_dir:
        raise ValueError("missing required arguments")
    return context_file, output_file, artifact_dir


def make_action_id(script_id: str) -> str:
    return script_id.replace(".", "-")


def detail(outputs: Dict[str, Dict[str, Any]], script_id: str, key: str) -> Any:
    data = outputs.get(script_id) or {}
    return (((data.get("structured_record_patch") or {}).get("details") or {}).get(key))


def collect_outputs(paths: Dict[str, str]) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    outputs: Dict[str, Dict[str, Any]] = {}
    gaps: List[Dict[str, Any]] = []
    for script_id, path in paths.items():
        if not path or not os.path.exists(path):
            gaps.append(
                {
                    "gap": "script output missing: %s" % script_id,
                    "related_stage": "signal_governance",
                    "why_important": "signals bundle depends on standard script outputs",
                }
            )
            continue
        try:
            outputs[script_id] = load_data(path)
        except Exception as exc:
            gaps.append(
                {
                    "gap": "script output unreadable: %s" % script_id,
                    "related_stage": "signal_governance",
                    "why_important": str(exc),
                }
            )
    return outputs, gaps


def inventory_signals(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    pods = detail(outputs, "mongodb.collect.pods.state", "pods") or []
    statefulsets = detail(outputs, "mongodb.collect.statefulsets.yaml", "statefulsets") or []
    services = detail(outputs, "mongodb.collect.services.yaml", "services") or []
    nodes = detail(outputs, "mongodb.collect.nodes.state", "nodes") or []
    return {
        "pods": {
            "count": len(pods),
            "by_status_hint": dict(Counter(str(item.get("status_hint") or "unknown") for item in pods)),
            "not_healthy": [
                {
                    "pod_ref": item.get("name"),
                    "phase": item.get("phase"),
                    "ready": item.get("ready"),
                    "restart_count": item.get("restart_count"),
                    "last_terminations": item.get("last_terminations") or [],
                    "container_status": item.get("container_status"),
                    "status_hint": item.get("status_hint"),
                    "node_selector": item.get("node_selector") or {},
                    "conditions": item.get("conditions") or [],
                }
                for item in pods
                if item.get("status_hint") != "healthy"
            ],
        },
        "statefulsets": {
            "count": len(statefulsets),
            "by_status_hint": dict(Counter(str(item.get("status_hint") or "unknown") for item in statefulsets)),
            "not_healthy": [
                {
                    "statefulset_ref": item.get("name"),
                    "replicas": item.get("replicas"),
                    "ready_replicas": item.get("ready_replicas"),
                    "current_replicas": item.get("current_replicas"),
                    "updated_replicas": item.get("updated_replicas"),
                    "available_replicas": item.get("available_replicas"),
                    "status_hint": item.get("status_hint"),
                }
                for item in statefulsets
                if item.get("status_hint") != "healthy"
            ],
        },
        "services": {
            "count": len(services),
            "types": dict(Counter(str(item.get("type") or "unknown") for item in services)),
        },
        "nodes": {
            "count": len(nodes),
            "by_status_hint": dict(Counter(str(item.get("status_hint") or "unknown") for item in nodes)),
            "not_healthy": [
                {
                    "node_ref": item.get("name"),
                    "internal_ips": item.get("internal_ips"),
                    "status_hint": item.get("status_hint"),
                    "conditions": item.get("conditions"),
                }
                for item in nodes
                if item.get("status_hint") != "healthy"
            ],
        },
    }


def event_signals(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    events = detail(outputs, "mongodb.collect.events.yaml", "events") or []
    warning_events = [item for item in events if item.get("type") == "Warning"]
    return {
        "count": len(events),
        "warning_count": len(warning_events),
        "by_reason": dict(Counter(str(item.get("reason") or "unknown") for item in events)),
        "warnings": [
            {
                "object_ref": "%s/%s" % (((item.get("involved_object") or {}).get("kind") or "Object").lower(), (item.get("involved_object") or {}).get("name")),
                "reason": item.get("reason"),
                "message": item.get("message"),
                "count": item.get("count"),
                "last_timestamp": item.get("last_timestamp"),
            }
            for item in warning_events
        ],
    }


def scheduling_condition(pod: Dict[str, Any]) -> Dict[str, Any]:
    for condition in pod.get("conditions") or []:
        if condition.get("type") == "PodScheduled":
            return condition
    return {}


def is_selector_mismatch(message: str) -> bool:
    lowered = message.lower()
    return "node affinity/selector" in lowered or "node selector" in lowered or "didn't match pod" in lowered


def is_volume_binding_failure(message: str) -> bool:
    lowered = message.lower()
    return "persistentvolumeclaim" in lowered or "volume binding" in lowered or "unbound immediate persistentvolumeclaims" in lowered


def is_resource_shortage(message: str) -> bool:
    lowered = message.lower()
    return "insufficient cpu" in lowered or "insufficient memory" in lowered or "insufficient ephemeral-storage" in lowered


def abnormal_signals_from_inventory(inventory: Dict[str, Any], events: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    signals: List[Dict[str, Any]] = []
    links: List[Dict[str, Any]] = []
    timeline: List[str] = []
    seen = set()

    def add(signal_id: str, severity: str, object_ref: str, detail_text: str) -> None:
        key = (signal_id, object_ref)
        if key in seen:
            return
        seen.add(key)
        signals.append(
            {
                "signal_id": signal_id,
                "severity": severity,
                "object_ref": object_ref,
                "detail": detail_text,
            }
        )
        links.append({"object_ref": object_ref, "signal_refs": [signal_id]})
        timeline.append("%s observed on %s" % (signal_id, object_ref))

    for pod in ((inventory.get("pods") or {}).get("not_healthy") or []):
        pod_ref = "pod/%s" % pod.get("pod_ref")
        phase = str(pod.get("phase") or "")
        ready = pod.get("ready")
        container_status = str(pod.get("container_status") or "")
        last_terminations = pod.get("last_terminations") or []
        termination_text = ""
        if last_terminations:
            sample = last_terminations[0]
            termination_text = " last_termination=%s exit_code=%s message=%s" % (
                sample.get("reason") or "unknown",
                sample.get("exit_code"),
                str(sample.get("message") or "")[:200],
            )
        condition = scheduling_condition(pod)
        reason = str(condition.get("reason") or "")
        message = str(condition.get("message") or "")
        node_selector = pod.get("node_selector") or {}
        if phase == "Pending" and reason == "Unschedulable":
            add(
                "pod-unschedulable",
                "high",
                pod_ref,
                "Pod is Pending/Unschedulable; scheduler_message=%s" % message,
            )
        if phase == "Pending" and reason == "Unschedulable" and is_selector_mismatch(message):
            add(
                "pod-node-selector-mismatch",
                "high",
                pod_ref,
                "Pod is Pending/Unschedulable because node selector or affinity does not match available nodes; node_selector=%s; scheduler_message=%s"
                % (node_selector, message),
            )
        elif phase == "Pending" and reason == "Unschedulable" and is_volume_binding_failure(message):
            add(
                "pod-volume-binding-failed",
                "high",
                pod_ref,
                "Pod is Pending/Unschedulable because volume binding or PVC resolution failed; scheduler_message=%s" % message,
            )
        elif phase == "Pending" and reason == "Unschedulable" and is_resource_shortage(message):
            add(
                "pod-resource-insufficient",
                "high",
                pod_ref,
                "Pod is Pending/Unschedulable because available nodes do not have enough requested resources; scheduler_message=%s" % message,
            )
        elif container_status in ("ImagePullBackOff", "ErrImagePull"):
            add(
                "pod-image-pull-failed",
                "high",
                pod_ref,
                "Pod container image pull failed; container_status=%s phase=%s ready=%s" % (container_status, phase, ready),
            )
        elif container_status == "restarting":
            add(
                "pod-crashloop",
                "high",
                pod_ref,
                "Pod container is restarting; restart_count=%s phase=%s ready=%s%s" % (pod.get("restart_count"), phase, ready, termination_text),
            )
        elif phase != "Running" or ready is False:
            add(
                "pod-not-ready",
                "high",
                pod_ref,
                "Pod phase=%s ready=%s status_hint=%s" % (phase, ready, pod.get("status_hint")),
            )

    for event in events.get("warnings") or []:
        object_ref = str(event.get("object_ref") or "")
        reason = str(event.get("reason") or "")
        message = str(event.get("message") or "")
        if not object_ref.startswith("pod/"):
            continue
        if reason == "FailedScheduling":
            add("pod-unschedulable", "high", object_ref, "Scheduler warning event: %s" % message)
            if is_selector_mismatch(message):
                add("pod-node-selector-mismatch", "high", object_ref, "Scheduler warning event indicates node selector or affinity mismatch: %s" % message)
            elif is_volume_binding_failure(message):
                add("pod-volume-binding-failed", "high", object_ref, "Scheduler warning event indicates PVC or volume binding failure: %s" % message)
            elif is_resource_shortage(message):
                add("pod-resource-insufficient", "high", object_ref, "Scheduler warning event indicates insufficient node resources: %s" % message)
        elif reason in ("Failed", "FailedMount") and is_volume_binding_failure(message):
            add("pod-volume-binding-failed", "high", object_ref, "Kubernetes warning event indicates PVC or volume failure: %s" % message)
        elif reason in ("Failed", "ErrImagePull", "ImagePullBackOff"):
            add("pod-image-pull-failed", "high", object_ref, "Kubernetes warning event indicates image pull failure: %s" % message)
        elif reason == "BackOff" and "restart" in message.lower():
            add("pod-crashloop", "high", object_ref, "Kubernetes warning event indicates container restart backoff: %s" % message)
        elif reason == "Unhealthy":
            add("pod-not-ready", "high", object_ref, "Kubernetes warning event indicates probe or readiness failure: %s" % message)

    for sts in ((inventory.get("statefulsets") or {}).get("not_healthy") or []):
        add(
            "statefulset-replicas-not-ready",
            "high",
            "statefulset/%s" % sts.get("statefulset_ref"),
            "StatefulSet ready_replicas=%s desired_replicas=%s current_replicas=%s updated_replicas=%s"
            % (sts.get("ready_replicas"), sts.get("replicas"), sts.get("current_replicas"), sts.get("updated_replicas")),
        )

    return signals, links, timeline


def topology_signals(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    shard_maps = detail(outputs, "mongodb.collect.mongos.get_shard_map", "shard_maps") or []
    shard_map = detail(outputs, "mongodb.collect.mongos.get_shard_map", "shard_map") or {}
    if not shard_map and shard_maps:
        shard_map = shard_maps[0]
    replica_members = detail(outputs, "mongodb.collect.replicaset.rs_status", "replica_members") or []
    replica_sets: Dict[str, Dict[str, Any]] = {}
    for item in replica_members:
        rs_id = str(item.get("replica_set_id") or "unknown")
        replica_sets.setdefault(rs_id, {"members": [], "roles": Counter()})
        self_member = item.get("self_member") or {}
        role = str(self_member.get("state_str") or "unknown")
        replica_sets[rs_id]["roles"][role] += 1
        replica_sets[rs_id]["members"].append(
            {
                "source_pod_ref": item.get("source_pod_ref"),
                "state_str": role,
                "health": self_member.get("health"),
                "sync_source_host": self_member.get("sync_source_host"),
            }
        )
    normalized_sets: Dict[str, Any] = {}
    for rs_id, value in replica_sets.items():
        normalized_sets[rs_id] = {
            "roles": dict(value["roles"]),
            "members": value["members"],
        }
    return {
        "shard_map": {
            "source_pod_ref": shard_map.get("source_pod_ref"),
            "config_server_ref": shard_map.get("config_server_ref"),
            "shard_count": len(shard_map.get("shards") or []),
            "shards": shard_map.get("shards") or [],
            "mongos_collected_count": len(shard_maps) if isinstance(shard_maps, list) else (1 if shard_map else 0),
        },
        "replica_sets": normalized_sets,
    }


def log_signals(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    processed = detail(outputs, "mongodb.normalize.logs.highlights", "processed_logs") or {}
    highlights = processed.get("highlights") or []
    return {
        "highlight_count": len(highlights),
        "by_category": dict(Counter(str(item.get("category") or "unknown") for item in highlights)),
        "samples": highlights[:50],
        "source_log_file_count": processed.get("source_log_file_count", 0),
    }


def output_statuses(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, str]:
    return {script_id: str(data.get("status") or "unknown") for script_id, data in outputs.items()}


def main() -> int:
    context_file, output_file, artifact_dir = parse_args(sys.argv[1:])
    started_at = now_iso()
    context = load_data(context_file)
    script_id = str(context.get("script_id") or "mongodb.normalize.signals.bundle")
    inputs = context.get("inputs") or {}
    output_files = inputs.get("script_output_files") or {}
    if not isinstance(output_files, dict):
        output_files = {}

    os.makedirs(artifact_dir, exist_ok=True)
    processed_dir = os.path.join(artifact_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    outputs, evidence_gaps = collect_outputs({str(k): str(v) for k, v in output_files.items()})
    finished_at = now_iso()
    bundle = {
        "incident_id": context.get("incident_id"),
        "middleware": context.get("middleware", "mongodb"),
        "generated_at": finished_at,
        "script_statuses": output_statuses(outputs),
        "inventory": inventory_signals(outputs),
        "topology": topology_signals(outputs),
        "events": event_signals(outputs),
        "logs": log_signals(outputs),
        "evidence_gaps": evidence_gaps,
    }
    abnormal_signals, object_signal_links, timeline_summary = abnormal_signals_from_inventory(bundle["inventory"], bundle["events"])
    if abnormal_signals:
        bundle["signal_overview"] = {
            "status": "abnormal",
            "abnormal_signal_count": len(abnormal_signals),
        }
        bundle["abnormal_signals"] = abnormal_signals
        bundle["object_signal_links"] = object_signal_links
        bundle["timeline_summary"] = timeline_summary

    processed_relpath = os.path.join("processed", "signal-bundle.json")
    with open(os.path.join(artifact_dir, processed_relpath), "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2, sort_keys=False)
        fh.write("\n")

    status = "blocked" if not outputs else ("partial" if evidence_gaps else "success")
    summary = "built signal bundle from %d script output(s)" % len(outputs)
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": [
            {
                "path": processed_relpath,
                "kind": "signal_bundle",
                "description": "normalized signal bundle for diagnosis",
            }
        ],
        "structured_record_patch": {},
        "signal_bundle_patch": bundle,
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "normalize signals bundle",
                    "target": "script_outputs",
                    "method": "merge standard script output patches",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [
                {
                    "item": "signal_bundle",
                    "source": "%d script output(s)" % len(outputs),
                    "note": "inventory, topology and log signals normalized",
                }
            ] if outputs else [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": [],
        "evidence_gaps": evidence_gaps,
    }
    write_data(output_file, payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
