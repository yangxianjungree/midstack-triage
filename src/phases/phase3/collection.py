"""Phase 3 collection helpers."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from shared.scenario_router import infer_scenario
from shared.workspace import load_yaml, now_iso, write_yaml
from . import remote_collection as _remote_collection
from .remote_collection import merge_remote_run_outputs, run_remote_collection
from .remote_run import (
    build_input_from_remote_run,
    copy_remote_run_support_files,
    first_context,
    load_remote_executor_run_result,
    merge_remote_executor_run_result,
    merge_remote_script_outputs,
    remote_executor_next_actions,
    remote_executor_required_user_action,
    script_run_dirs,
)
from .recollection import (
    DIRECTED_RECOLLECTION_CAP,
    collection_report_mentions_log_sink_gap,
    crashloop_logs_are_shallow,
    current_logs_are_short,
    details_has_items,
    directed_recollection_script_ids,
    evidence_mentions_dns_issue,
    filter_recollection_scripts_by_skill_pool,
    has_file_backed_log_sink,
    has_file_tail_logs,
    has_log_sink_record,
    incident_evidence_text,
    select_directed_recollection_script_ids,
    should_run_dns_recollection,
    should_run_log_file_tail_recollection,
    should_run_log_node_file_tail_recollection,
    should_run_log_sink_recollection,
    should_run_network_overlay_recollection,
    should_run_pod_describe_recollection,
    SCRIPT_DNS_COREDNS,
    SCRIPT_LOG_FILE_TAIL,
    SCRIPT_LOG_NODE_FILE_TAIL,
    SCRIPT_LOG_SINK_DISCOVER,
    SCRIPT_NETWORK_OVERLAY,
    SCRIPT_PODS_DESCRIBE,
    signal_bundle_has,
    signal_bundle_text,
    signal_object_pods,
    text_has_direct_error_terms,
)
from .report_gaps import (
    drop_closed_evidence_gaps,
    infer_gap_type,
    normalize_collection_report_gaps,
    record_recollection_skill_pool_miss,
)
from .skill_runtime import (
    enrich_skill_runtime_context,
    resolve_skill_runtime,
    write_skill_runtime_context,
)

subprocess = _remote_collection.subprocess


def build_incident_from_remote_run(remote_run_dir: Path, output_dir: Path, args, preserve_existing_input: bool = False) -> None:
    if not remote_run_dir.exists():
        raise FileNotFoundError("remote run dir does not exist: %s" % remote_run_dir)
    context = first_context(remote_run_dir)
    run_result = load_remote_executor_run_result(remote_run_dir)
    input_file = output_dir / "input.yaml"
    if preserve_existing_input and input_file.exists():
        input_data = load_yaml(input_file)
    else:
        input_data = build_input_from_remote_run(remote_run_dir, args)
    generated_at = now_iso()
    structured_record: Dict[str, Any] = {
        "summary": {
            "middleware": input_data["middleware"],
            "topology_type": str(context.get("topology_type") or ""),
            "deployment_architecture": str(context.get("deployment_architecture") or ""),
            "namespace": input_data["namespace"],
            "cluster_id": input_data["cluster_id"],
        },
        "details": {},
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    signal_bundle: Dict[str, Any] = {
        "incident_id": input_data["incident_id"],
        "middleware": input_data["middleware"],
        "signal_overview": {"status": "unknown", "abnormal_signal_count": 0},
        "abnormal_signals": [],
        "object_signal_links": [],
        "timeline_summary": [],
        "processed_log_highlights": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    collection_report: Dict[str, Any] = {
        "collection_actions": [],
        "successful_items": [],
        "failed_items": [],
        "blank_items": [],
        "evidence_gaps": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    copy_remote_run_support_files(remote_run_dir, output_dir)

    script_outputs_dir = output_dir / "script_outputs"
    if script_outputs_dir.exists():
        shutil.rmtree(script_outputs_dir)
    item_dirs = merge_remote_script_outputs(remote_run_dir, output_dir, structured_record, signal_bundle, collection_report)
    merge_remote_executor_run_result(collection_report, run_result, bool(item_dirs))
    drop_closed_evidence_gaps(structured_record, collection_report)
    normalize_collection_report_gaps(collection_report)

    if not preserve_existing_input or not input_file.exists():
        write_yaml(input_file, input_data)
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def apply_scenario_routing_if_needed(output_dir: Path, args) -> Dict[str, Any]:
    input_file = output_dir / "input.yaml"
    signal_bundle_file = output_dir / "signal_bundle.yaml"
    if not input_file.exists() or not signal_bundle_file.exists():
        return load_yaml(input_file) if input_file.exists() else {}

    input_data = load_yaml(input_file)
    existing_scenario = str(input_data.get("scenario") or "unknown")
    if existing_scenario not in ("", "unknown", "baseline"):
        return input_data

    structured_record_file = output_dir / "structured_record.yaml"
    structured_record = load_yaml(structured_record_file) if structured_record_file.exists() else {}
    signal_bundle = load_yaml(signal_bundle_file)
    routing = infer_scenario(
        signal_bundle,
        structured_record=structured_record,
        customer_clue=str(input_data.get("customer_clue") or getattr(args, "customer_clue", "") or ""),
        middleware=str(input_data.get("middleware") or "mongodb"),
    )
    input_data["scenario"] = routing["scenario"]
    input_data["scenario_inference"] = routing["scenario_inference"]
    input_data["updated_at"] = now_iso()
    write_yaml(input_file, input_data)
    args.scenario = routing["scenario"]
    return input_data


def run_directed_recollection_if_needed(args, output_dir: Path, skill_pool: Optional[set[str]] = None) -> bool:
    if not args.remote_config:
        return False
    script_ids = directed_recollection_script_ids(output_dir, skill_pool=skill_pool)
    if not script_ids:
        return False
    trace_dir = output_dir / "directed-recollection"
    remote_run_dir = run_remote_collection(args, trace_dir, script_ids)
    merge_remote_run_outputs(remote_run_dir, output_dir)
    return True
