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
                    "status_hint": item.get("status_hint"),
                }
                for item in pods
                if item.get("status_hint") != "healthy"
            ],
        },
        "statefulsets": {
            "count": len(statefulsets),
            "by_status_hint": dict(Counter(str(item.get("status_hint") or "unknown") for item in statefulsets)),
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


def topology_signals(outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    shard_map = detail(outputs, "mongodb.collect.mongos.get_shard_map", "shard_map") or {}
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
        "logs": log_signals(outputs),
        "evidence_gaps": evidence_gaps,
    }

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
