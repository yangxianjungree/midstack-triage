"""Phase 5 analysis finalization helpers."""

from __future__ import annotations

from pathlib import Path

from shared.analysis_runtime import (
    AGENT_REASONING_TASK_FILENAME,
    ANALYSIS_RULE_DRAFT_FILENAME,
    analysis_matches_rule_draft,
    analysis_next_action_texts,
    analysis_summary_text,
    apply_analysis_guardrails,
    write_report,
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
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    output = adapter_output("analyse", incident_id, middleware, "completed", analysis_summary_text(analysis), incident_dir)
    output["user_message"] = output["summary"]
    add_record_ref_if_exists(output, incident_dir, "analysis", "analysis.yaml", "finalized analysis result")
    add_record_ref_if_exists(output, incident_dir, "analysis_rule_draft", ANALYSIS_RULE_DRAFT_FILENAME, "rules fallback draft before Agent reasoning refinement")
    add_record_ref_if_exists(output, incident_dir, "agent_reasoning_task", AGENT_REASONING_TASK_FILENAME, "phase-4/5 Agent reasoning task and output contract")
    add_record_ref_if_exists(output, incident_dir, "report", "report.md", "finalized human-readable report")
    add_record_ref_if_exists(output, incident_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
    output["next_actions"] = analysis_next_action_texts(analysis)
    if analysis_matches_rule_draft(analysis, incident_dir):
        output["warnings"].append("analysis.yaml still matches the rules draft; no additional Agent reasoning was detected.")

    update_incident_meta(incident_dir, {"status": "analysed", "current_command": "analyse"})
    write_current_incident(output_root, incident_dir)
    write_yaml(incident_dir / "adapter-output.yaml", output)
    print(str(incident_dir))
    return 0
