"""Phase 3 incident reconstruction from remote run outputs."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict

from shared.workspace import load_yaml, now_iso, write_yaml
from .remote_run import (
    build_input_from_remote_run,
    copy_remote_run_support_files,
    first_context,
    load_remote_executor_run_result,
    merge_remote_executor_run_result,
    merge_remote_script_outputs,
)
from .report_gaps import drop_closed_evidence_gaps, normalize_collection_report_gaps


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
