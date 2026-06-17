"""Phase 5 review helpers."""

from __future__ import annotations

import sys

from shared.analysis_common import flatten_strings
from shared.workspace import (
    adapter_output,
    load_incident_meta,
    load_yaml,
    now_iso,
    path_from_arg,
    read_current_incident,
    resolve_path,
    update_incident_meta,
    write_blocked_output,
    write_yaml,
)
from .review_scoring import (
    LEVEL_VALUE,
    append_reason,
    apply_process_findings_to_score,
    build_review_block,
    conclusion_level,
    downgrade_level,
    has_critical_gap,
    has_next_actions,
    insufficient_hypotheses,
    level_from_confidence,
    overall_level,
    review_process_findings,
    review_regression_risks,
    review_score_from_analysis,
    review_suggestions,
    score_item,
    supported_hypotheses,
)


def run_review(args) -> int:
    output_root = path_from_arg(args.output_root)
    if args.incident_dir:
        incident_dir = resolve_path(args.incident_dir)
    else:
        try:
            incident_dir = read_current_incident(output_root)
        except (FileNotFoundError, ValueError) as exc:
            return write_blocked_output(
                "review",
                "none",
                "mongodb",
                output_root,
                "current incident is not available for review",
                [
                    {
                        "code": "missing_current_incident",
                        "message": str(exc),
                        "required_user_action": "run /midstack:analyse first or provide an explicit incident directory",
                    }
                ],
                ["run /midstack:analyse or provide an incident directory"],
                output_filename="review-adapter-output.yaml",
            )
    meta = load_incident_meta(incident_dir)
    meta_status = str(meta.get("status") or "")
    if meta_status and meta_status not in ("analysed", "reviewed", "closed"):
        return write_blocked_output(
            "review",
            str(meta.get("incident_id") or incident_dir.name),
            str(meta.get("middleware") or "mongodb"),
            incident_dir,
            "incident is not ready for review",
            [
                {
                    "code": "incident_status_not_reviewable",
                    "message": "incident status must be analysed, reviewed, or closed before review; current status is %s" % meta_status,
                    "required_user_action": "run /midstack:analyse successfully before review",
                }
            ],
            ["run /midstack:analyse successfully before review"],
            output_filename="review-adapter-output.yaml",
        )
    analysis_file = incident_dir / "analysis.yaml"
    if not analysis_file.exists():
        print("ERROR: missing analysis.yaml: %s" % analysis_file, file=sys.stderr)
        return 1
    analysis = load_yaml(analysis_file)
    analysis["review"] = build_review_block(analysis)
    analysis["updated_at"] = now_iso()
    write_yaml(analysis_file, analysis)
    update_incident_meta(incident_dir, {"status": "reviewed", "current_command": "review"})
    input_data = load_yaml(incident_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    output = adapter_output("review", incident_id, middleware, "completed", "local review completed", incident_dir)
    output["record_refs"].append({"name": "analysis.review", "path": str(analysis_file), "description": "local review result in analysis.yaml review block"})
    review_output_file = incident_dir / "review-adapter-output.yaml"
    write_yaml(review_output_file, output)
    print(str(review_output_file))
    return 0
