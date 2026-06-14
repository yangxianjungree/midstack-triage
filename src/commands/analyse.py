"""Analyse command runtime."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from midstack_runtime import (
    adapter_output,
    add_record_ref_if_exists,
    copy_if_exists,
    load_incident_meta,
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
from midstack_runtime.analysis import (
    ANALYSIS_RULE_DRAFT_FILENAME,
    apply_analysis_guardrails,
    write_agent_reasoning_task,
    write_report,
)


ANALYSABLE_STATUSES = ("ready", "analysed")


def run(
    args,
    *,
    root: Path,
    run_remote_smoke,
    load_remote_executor_run_result,
    build_incident_from_remote_run,
    apply_scenario_routing_if_needed,
    enrich_skill_runtime_context,
    run_directed_recollection_if_needed,
    remote_executor_required_user_action,
    remote_executor_next_actions,
    normalize_collection_report_gaps,
    run_phase4_analysis,
) -> int:
    output_root = path_from_arg(args.output_root)
    incident_dir = None
    incident_mode = False
    previous_incident_status = ""
    remote_run_result: Dict[str, Any] = {}
    if not (args.incident_dir or args.remote_config or args.remote_run_dir or args.input_dir):
        try:
            args.incident_dir = str(read_current_incident(output_root))
        except (FileNotFoundError, ValueError) as exc:
            return write_blocked_output(
                "analyse",
                "none",
                "mongodb",
                output_root,
                "current incident is not available",
                [
                    {
                        "code": "missing_current_incident",
                        "message": str(exc),
                        "required_user_action": "run /midstack:start first or provide an explicit incident directory",
                    }
                ],
                ["run /midstack:start with remote access information"],
            )
    if args.incident_dir:
        incident_mode = True
        incident_dir = resolve_path(args.incident_dir)
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
                        "required_user_action": "provide an existing incident directory or run /midstack:start again",
                    }
                ],
                ["provide an existing incident directory"],
            )
        output_dir = path_from_arg(args.output_dir) if args.output_dir else incident_dir
        meta = load_incident_meta(incident_dir)
        status = str(meta.get("status") or "")
        previous_incident_status = status
        if status not in ANALYSABLE_STATUSES:
            incident_id = str(meta.get("incident_id") or incident_dir.name)
            middleware = str(meta.get("middleware") or "mongodb")
            message = "incident status must be ready or analysed before analyse; current status is %s" % (status or "missing")
            return write_blocked_output(
                "analyse",
                incident_id,
                middleware,
                incident_dir,
                "incident is not ready for analyse",
                [
                    {
                        "code": "incident_status_not_ready",
                        "message": message,
                        "required_user_action": "finish /midstack:start successfully or choose another incident",
                    }
                ],
                ["fix the blocked start conditions or choose a ready incident"],
            )
        input_data = load_yaml(incident_dir / "input.yaml")
        args.incident_input = input_data
        args.incident_id_override = str(input_data.get("incident_id") or incident_dir.name)
        args.remote_config = str(incident_dir / "remote-config.yaml")
        object_inventory_file = incident_dir / "object-inventory.yaml"
        if object_inventory_file.exists():
            args.object_inventory = str(object_inventory_file)
        args.remote_namespace = args.remote_namespace or str(input_data.get("namespace") or "")
        args.customer_clue = args.customer_clue or str(input_data.get("customer_clue") or "")
        args.scenario = args.scenario or str(input_data.get("scenario") or "unknown")
        if not Path(args.remote_config).exists():
            return write_blocked_output(
                "analyse",
                str(input_data.get("incident_id") or incident_dir.name),
                str(input_data.get("middleware") or "mongodb"),
                incident_dir,
                "incident remote config is missing",
                [
                    {
                        "code": "missing_remote_config",
                        "message": "missing incident remote-config.yaml: %s" % args.remote_config,
                        "required_user_action": "rerun /midstack:start with remote access information",
                    }
                ],
                ["rerun /midstack:start with remote access information"],
            )
    else:
        if not args.output_dir:
            print("ERROR: --output-dir is required unless --incident-dir is used", file=sys.stderr)
            return 1
        output_dir = path_from_arg(args.output_dir)
    try:
        if incident_mode and incident_dir is not None:
            update_incident_meta(incident_dir, {"status": "analysing", "current_command": "analyse"})
        if args.remote_config:
            remote_run_dir = run_remote_smoke(args, output_dir)
            remote_run_result = load_remote_executor_run_result(remote_run_dir)
            build_incident_from_remote_run(remote_run_dir, output_dir, args, preserve_existing_input=incident_mode)
        elif args.remote_run_dir:
            remote_run_dir = resolve_path(args.remote_run_dir)
            remote_run_result = load_remote_executor_run_result(remote_run_dir)
            build_incident_from_remote_run(remote_run_dir, output_dir, args)
        else:
            input_dir = resolve_path(args.input_dir)
            for filename in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml", "expected_analysis.yaml"):
                copy_if_exists(input_dir, output_dir, filename)
    except Exception as exc:
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output_dir.mkdir(parents=True, exist_ok=True)
        incident_id = output_dir.name
        output = adapter_output("analyse", incident_id, "mongodb", "failed", "local analyse failed", output_dir)
        output["warnings"].append(str(exc))
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    input_data = load_yaml(output_dir / "input.yaml")
    if (output_dir / "signal_bundle.yaml").exists():
        input_data = apply_scenario_routing_if_needed(output_dir, args)
    skill_runtime: Dict[str, Any] = {}
    if (output_dir / "signal_bundle.yaml").exists():
        skill_runtime = enrich_skill_runtime_context(output_dir, input_data)
        input_data = load_yaml(output_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or output_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    skill_pool = skill_runtime.get("skill_pool") or set()
    if remote_run_result:
        run_status = str(remote_run_result.get("status") or "")
        run_error = remote_run_result.get("error") or {}
        error_code = str(run_error.get("code") or "")
        error_message = str(run_error.get("message") or "remote executor did not complete successfully")
        if run_status == "blocked":
            if incident_mode and incident_dir is not None and previous_incident_status:
                update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
            output = adapter_output("analyse", incident_id, middleware, "blocked", "remote signal collection is blocked", output_dir)
            output["blocking_items"] = [
                {
                    "code": error_code or "remote_executor_blocked",
                    "message": error_message,
                    "required_user_action": remote_executor_required_user_action(error_code),
                }
            ]
            output["next_actions"] = remote_executor_next_actions(error_code)
            add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
            add_record_ref_if_exists(output, output_dir, "remote_executor_run", "remote-executor-run.yaml", "remote executor batch result")
            write_yaml(output_dir / "adapter-output.yaml", output)
            print(str(output_dir))
            return 0
        if run_status == "failed":
            if incident_mode and incident_dir is not None and previous_incident_status:
                update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
            output = adapter_output("analyse", incident_id, middleware, "failed", "remote signal collection failed", output_dir)
            output["warnings"].append(error_message)
            output["next_actions"] = remote_executor_next_actions(error_code)
            add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
            add_record_ref_if_exists(output, output_dir, "remote_executor_run", "remote-executor-run.yaml", "remote executor batch result")
            write_yaml(output_dir / "adapter-output.yaml", output)
            print("ERROR: %s" % error_message, file=sys.stderr)
            return 1
        try:
            run_directed_recollection_if_needed(args, output_dir, skill_pool=skill_pool or None)
            if skill_runtime:
                enrich_skill_runtime_context(output_dir, input_data)
                input_data = load_yaml(output_dir / "input.yaml")
        except Exception as exc:
            collection_report = load_yaml(output_dir / "collection_report.yaml")
            collection_report.setdefault("evidence_gaps", []).append(
                {
                    "gap": "directed recollection failed: %s" % exc,
                    "gap_type": "critical_gap",
                    "related_stage": "directed_recollection",
                    "why_important": "The first directed recollection loop could not close a critical evidence gap.",
                    "recommended_action": "inspect directed-recollection logs and rerun the read-only playbook manually",
                }
            )
            collection_report["updated_at"] = now_iso()
            write_yaml(output_dir / "collection_report.yaml", collection_report)

    analysis_file = output_dir / "analysis.yaml"
    analyse_script = root / "tools" / "analyse" / ("%s-analyse.py" % middleware)
    if not analyse_script.exists():
        summary = "no analyse runner available for middleware %s" % middleware
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output = adapter_output("analyse", incident_id, middleware, "failed", summary, output_dir)
        output["blocking_items"] = [
            {
                "code": "unsupported_middleware_analyse",
                "message": summary,
                "required_user_action": "use a supported middleware or add tools/analyse/%s-analyse.py" % middleware,
            }
        ]
        output["next_actions"] = ["use a supported middleware such as mongodb or pulsar"]
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % summary, file=sys.stderr)
        return 1

    try:
        phase4_result = run_phase4_analysis(output_dir)
        print("Phase 4 reasoning completed: %d rounds" % phase4_result["total_rounds"], file=sys.stderr)
    except Exception as exc:
        print("Phase 4 warning: %s (falling back to legacy analyse)" % exc, file=sys.stderr)
    proc = subprocess.run(
        [
            sys.executable,
            str(analyse_script),
            "--input-dir",
            str(output_dir),
            "--output-file",
            str(analysis_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    status = "completed" if proc.returncode == 0 else "failed"
    output = adapter_output("analyse", incident_id, middleware, status, "local analyse %s" % status, output_dir)
    output["record_refs"].append({"name": "analysis", "path": str(analysis_file), "description": "generated analysis result"})
    if proc.returncode != 0:
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output["warnings"].append(proc.stderr.strip())
    else:
        analysis = load_yaml(analysis_file)
        collection_report = load_yaml(output_dir / "collection_report.yaml") if (output_dir / "collection_report.yaml").exists() else {}
        signal_bundle = load_yaml(output_dir / "signal_bundle.yaml") if (output_dir / "signal_bundle.yaml").exists() else {}
        if collection_report:
            normalize_collection_report_gaps(collection_report)
            write_yaml(output_dir / "collection_report.yaml", collection_report)
        if apply_analysis_guardrails(analysis, collection_report, signal_bundle):
            analysis["updated_at"] = now_iso()
            write_yaml(analysis_file, analysis)
        rule_draft_file = output_dir / ANALYSIS_RULE_DRAFT_FILENAME
        write_yaml(rule_draft_file, analysis)
        report_file = write_report(output_dir, input_data, analysis)
        task_file = write_agent_reasoning_task(
            output_dir,
            input_data,
            analysis_file,
            rule_draft_file,
            report_file,
            matched_skills=skill_runtime.get("skills") if skill_runtime else None,
        )
        output["record_refs"].append(
            {
                "name": "analysis_rule_draft",
                "path": str(rule_draft_file),
                "description": "rules fallback draft before Agent reasoning refinement",
            }
        )
        output["record_refs"].append(
            {
                "name": "agent_reasoning_task",
                "path": str(task_file),
                "description": "phase-4/5 Agent reasoning task and output contract",
            }
        )
        output["record_refs"].append({"name": "report", "path": str(report_file), "description": "generated human-readable report"})
        output["warnings"].append("analysis.yaml is currently a rules-based fallback draft; Agent reasoning should refine analysis.yaml and report.md.")
        output["next_actions"] = [
            "read agent-reasoning-task.md and update analysis.yaml with Agent-led multi-hypothesis reasoning, gap classification, and conclusion ceiling",
            "refresh report.md so it matches the final analysis.yaml conclusion",
        ]
        if incident_mode and incident_dir is not None:
            update_incident_meta(incident_dir, {"status": "analysed", "current_command": "analyse"})
            write_current_incident(output_root, incident_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(analysis_file))
    return proc.returncode
