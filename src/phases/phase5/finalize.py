"""Phase 5 analysis finalization helpers."""

from __future__ import annotations

from pathlib import Path

from shared.analysis_runtime import (
    AGENT_REASONING_TASK_FILENAME,
    analysis_matches_rules_fallback,
    analysis_next_action_texts,
    analysis_summary_text,
    apply_analysis_guardrails,
    find_analysis_rules_fallback_file,
    write_report,
)
from shared.reasoning_history import (
    REASONING_MANIFEST_FILENAME,
    analysis_content_hash,
    current_head_analysis_hash,
    current_head_segment_id,
    current_head_segment_path,
    write_reasoning_segment,
)
from shared.workspace import (
    adapter_output,
    add_record_ref_if_exists,
    load_yaml,
    now_iso,
    path_from_arg,
    read_current_incident,
    resolve_path,
    update_incident_meta,
    write_blocked_output,
    write_current_incident,
    write_yaml,
)


def _table_value(value) -> str:
    text = str(value or "").strip()
    return text if text else "-"


def _first_next_action(analysis) -> str:
    actions = analysis_next_action_texts(analysis)
    return actions[0] if actions else "No next action recorded"


def _first_completed_verification(analysis) -> str:
    for item in analysis.get("verification_requests") or []:
        if not isinstance(item, dict) or item.get("status") != "completed":
            continue
        request_id = str(item.get("request_id") or "verification").strip()
        result = str(item.get("result") or item.get("output_ref") or "").strip()
        if result:
            return "`%s` %s" % (request_id, result)
        return "`%s` completed" % request_id
    return ""


def completed_user_message(incident_dir: Path, input_data, analysis) -> str:
    conclusion = analysis.get("conclusion_summary") or {}
    rows = [
        "| Field | Value |",
        "| --- | --- |",
        "| Status | `completed` |",
        "| Incident | `%s` |" % _table_value(input_data.get("incident_id") or incident_dir.name),
        "| Middleware | `%s` |" % _table_value(input_data.get("middleware") or "mongodb"),
        "| Conclusion | %s |" % _table_value(conclusion.get("statement")),
        "| Confidence | `%s` |" % _table_value(conclusion.get("confidence")),
        "| Supported level | `%s` |" % _table_value(conclusion.get("deepest_supported_level")),
        "| Primary cause | `%s` |" % _table_value(conclusion.get("primary_cause_category")),
    ]
    verification = _first_completed_verification(analysis)
    if verification:
        rows.append("| Verification | %s |" % verification)
    rows.extend(
        [
            "| Report | `%s` |" % (incident_dir / "report.md"),
            "| Analysis | `%s` |" % (incident_dir / "analysis.yaml"),
            "| Next | `%s` |" % _first_next_action(analysis),
        ]
    )
    return "\n".join(rows)


def build_finalize_adapter_output(incident_dir: Path, input_data, analysis):
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    output = adapter_output("analyse", incident_id, middleware, "completed", analysis_summary_text(analysis), incident_dir)
    output["user_message"] = completed_user_message(incident_dir, input_data, analysis)
    add_record_ref_if_exists(output, incident_dir, "analysis", "analysis.yaml", "finalized analysis result")
    rules_fallback_file = find_analysis_rules_fallback_file(incident_dir)
    if rules_fallback_file is not None:
        output["record_refs"].append(
            {
                "name": "analysis_rules_fallback",
                "path": str(rules_fallback_file),
                "description": "rules fallback analysis before Agent reasoning refinement",
            }
        )
    add_record_ref_if_exists(output, incident_dir, "agent_reasoning_task", AGENT_REASONING_TASK_FILENAME, "phase-4/5 Agent reasoning task and output contract")
    add_record_ref_if_exists(output, incident_dir, "reasoning_board", "reasoning-board.yaml", "Phase 4 multitrack reasoning board")
    add_record_ref_if_exists(output, incident_dir, "analysis_multitrack", "analysis.multitrack.yaml", "Phase 4 multitrack reasoning draft")
    add_record_ref_if_exists(output, incident_dir, "deep_analysis", "deep-analysis.yaml", "materialized Phase 4 deep analysis results")
    add_record_ref_if_exists(output, incident_dir, "reasoning_manifest", REASONING_MANIFEST_FILENAME, "append-only reasoning history manifest")
    current_segment = current_head_segment_path(incident_dir)
    if current_segment is not None:
        output["record_refs"].append(
            {
                "name": "reasoning_current_segment",
                "path": str(current_segment),
                "description": "current append-only reasoning segment",
            }
        )
    add_record_ref_if_exists(output, incident_dir, "report", "report.md", "finalized human-readable report")
    add_record_ref_if_exists(output, incident_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
    output["next_actions"] = analysis_next_action_texts(analysis)
    if analysis_matches_rules_fallback(analysis, incident_dir):
        output["warnings"].append("analysis.yaml still matches the rules fallback analysis; no additional Agent reasoning was detected.")
    return output


def finalize_analysis(args, normalize_collection_report_gaps) -> int:
    output_root = path_from_arg(args.output_root)
    if args.incident_dir:
        incident_dir = resolve_path(args.incident_dir)
    else:
        try:
            incident_dir = read_current_incident(output_root)
        except (FileNotFoundError, ValueError) as exc:
            return write_blocked_output(
                "analyse",
                "none",
                "mongodb",
                output_root,
                "current incident is not available for finalize",
                [
                    {
                        "code": "missing_current_incident",
                        "message": str(exc),
                        "required_user_action": "run /midstack:analyse first or provide an explicit incident directory",
                    }
                ],
                ["run /midstack:analyse first or provide an incident directory"],
            )
    if not incident_dir.exists():
        return write_blocked_output(
            "analyse",
            incident_dir.name,
            "mongodb",
            incident_dir.parent,
            "incident directory does not exist",
            [
                {
                    "code": "incident_dir_not_found",
                    "message": "incident dir does not exist: %s" % incident_dir,
                    "required_user_action": "provide an existing incident directory",
                }
            ],
            ["provide an existing incident directory"],
        )

    input_file = incident_dir / "input.yaml"
    analysis_file = incident_dir / "analysis.yaml"
    report_file = incident_dir / "report.md"
    if not input_file.exists() or not analysis_file.exists() or not report_file.exists():
        missing = [str(path.name) for path in (input_file, analysis_file, report_file) if not path.exists()]
        return write_blocked_output(
            "analyse",
            incident_dir.name,
            "mongodb",
            incident_dir,
            "analysis finalization is blocked",
            [
                {
                    "code": "missing_finalize_inputs",
                    "message": "missing required finalize input(s): %s" % ", ".join(missing),
                    "required_user_action": "complete analysis.yaml and report.md generation before finalize",
                }
            ],
            ["complete the missing analysis artifacts and rerun finalize"],
        )

    input_data = load_yaml(input_file)
    analysis = load_yaml(analysis_file)
    collection_report = load_yaml(incident_dir / "collection_report.yaml") if (incident_dir / "collection_report.yaml").exists() else {}
    signal_bundle = load_yaml(incident_dir / "signal_bundle.yaml") if (incident_dir / "signal_bundle.yaml").exists() else {}
    if collection_report:
        normalize_collection_report_gaps(collection_report)
        write_yaml(incident_dir / "collection_report.yaml", collection_report)
    if apply_analysis_guardrails(analysis, collection_report, signal_bundle):
        analysis["updated_at"] = now_iso()
        write_yaml(analysis_file, analysis)
    write_report(incident_dir, input_data, analysis)
    if current_head_analysis_hash(incident_dir) != analysis_content_hash(analysis):
        previous_segment_id = current_head_segment_id(incident_dir)
        dependencies = [previous_segment_id] if previous_segment_id else []
        write_reasoning_segment(
            incident_dir,
            "agent_refinement",
            analysis,
            summary="Agent or human refinement finalized the current analysis",
            depends_on=dependencies,
            supersedes=dependencies,
            output_refs={"analysis": "analysis.yaml", "report": "report.md"},
        )
    output = build_finalize_adapter_output(incident_dir, input_data, analysis)

    update_incident_meta(incident_dir, {"status": "analysed", "current_command": "analyse"})
    write_current_incident(output_root, incident_dir)
    write_yaml(incident_dir / "adapter-output.yaml", output)
    print(str(incident_dir))
    return 0
