"""Analyse command runtime."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

from execution.modes import resolve_execution_mode
from phases.phase4.deep_analysis import deep_analysis_summary, materialize_deep_analysis
from phases.phase4.agent_conclusion_gate import apply_agent_conclusion_override, evaluate_agent_conclusion_gate
from phases.phase4.rules import generate_rule_analysis, supported_middlewares
from shared.workspace import (
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
from shared.analysis_runtime import (
    apply_analysis_guardrails,
    write_analysis_rules_fallback,
    write_agent_reasoning_task,
    write_report,
)
from shared.reasoning_history import (
    REASONING_MANIFEST_FILENAME,
    write_reasoning_segment,
)


ANALYSABLE_STATUSES = ("ready", "analysed")
COLLECTED_INPUT_FILES = (
    "input.yaml",
    "structured_record.yaml",
    "signal_bundle.yaml",
    "collection_report.yaml",
)
ANALYSE_SCOPE_FULL = "full"
ANALYSE_SCOPE_COLLECT = "collect"
ANALYSE_SCOPE_REASON = "reason"


def _missing_collected_input_files(incident_dir: Path) -> list[str]:
    return [filename for filename in COLLECTED_INPUT_FILES if not (incident_dir / filename).exists()]


def _copy_collected_input_files(source_dir: Path, output_dir: Path, *, preserve_existing_input: bool = False) -> None:
    filenames = COLLECTED_INPUT_FILES + ("expected_analysis.yaml",)
    if preserve_existing_input:
        filenames = tuple(filename for filename in filenames if filename != "input.yaml")
    for filename in filenames:
        copy_if_exists(source_dir, output_dir, filename)


def _restore_incident_status(incident_mode: bool, incident_dir: Path | None, previous_incident_status: str) -> None:
    if incident_mode and incident_dir is not None and previous_incident_status:
        update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})


def _write_remote_executor_blocked_output(
    output_dir: Path,
    incident_id: str,
    middleware: str,
    error_code: str,
    error_message: str,
    remote_executor_required_user_action,
    remote_executor_next_actions,
) -> int:
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


def _write_remote_executor_failed_output(
    output_dir: Path,
    incident_id: str,
    middleware: str,
    error_code: str,
    error_message: str,
    remote_executor_next_actions,
) -> int:
    output = adapter_output("analyse", incident_id, middleware, "failed", "remote signal collection failed", output_dir)
    output["warnings"].append(error_message)
    output["next_actions"] = remote_executor_next_actions(error_code)
    add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
    add_record_ref_if_exists(output, output_dir, "remote_executor_run", "remote-executor-run.yaml", "remote executor batch result")
    write_yaml(output_dir / "adapter-output.yaml", output)
    print("ERROR: %s" % error_message, file=sys.stderr)
    return 1


def _write_missing_local_config_output(incident_dir: Path, input_data: Dict[str, Any]) -> int:
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    return write_blocked_output(
        "analyse",
        incident_id,
        middleware,
        incident_dir,
        "incident local config is missing",
        [
            {
                "code": "missing_local_config",
                "message": "missing incident local-config.yaml: %s" % (incident_dir / "local-config.yaml"),
                "required_user_action": "rerun /midstack:start --environment-mode local so Phase 2 can validate local kubectl access",
            }
        ],
        ["rerun /midstack:start --environment-mode local with a working local kubectl context"],
    )


def _execution_mode_name_from_incident(input_data: Dict[str, Any]) -> str:
    return str(input_data.get("execution_mode") or input_data.get("environment_mode") or "remote").strip().lower()


def _execution_mode_name_from_input_source(args) -> str:
    if getattr(args, "remote_config", ""):
        return "remote"
    if getattr(args, "input_dir", "") or getattr(args, "remote_run_dir", ""):
        return "offline"
    return "remote"


def _write_unsupported_execution_mode_output(output_root: Path, mode_name: str) -> int:
    return write_blocked_output(
        "analyse",
        "none",
        "mongodb",
        output_root,
        "unsupported execution mode",
        [
            {
                "code": "unsupported_execution_mode",
                "message": "unsupported execution mode: %s" % mode_name,
                "required_user_action": "rerun /midstack:start so execution_mode is recorded as remote, local, or offline",
            }
        ],
        ["rerun /midstack:start or fix the incident input.yaml execution_mode"],
    )


def _analyse_scope(args) -> str:
    value = str(getattr(args, "scope", ANALYSE_SCOPE_FULL) or ANALYSE_SCOPE_FULL).strip().lower()
    return value or ANALYSE_SCOPE_FULL


def _write_reason_scope_missing_artifacts_output(output_dir: Path, input_data: Dict[str, Any], missing_files: list[str]) -> int:
    incident_id = str(input_data.get("incident_id") or output_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    return write_blocked_output(
        "analyse",
        incident_id,
        middleware,
        output_dir,
        "reason scope needs existing collected artifacts",
        [
            {
                "code": "reason_scope_artifacts_missing",
                "message": "missing required collected artifact files: %s" % ", ".join(missing_files),
                "required_user_action": "run /midstack:analyse once without --scope reason, or provide an incident/output directory containing collected artifacts",
            }
        ],
        ["run /midstack:analyse without --scope reason to collect evidence first"],
    )


def _ensure_reason_scope_artifacts(args, output_dir: Path, input_data: Dict[str, Any], *, incident_mode: bool) -> list[str]:
    if getattr(args, "input_dir", ""):
        _copy_collected_input_files(resolve_path(args.input_dir), output_dir)
    missing_files = _missing_collected_input_files(output_dir)
    artifact_source = str(input_data.get("artifact_source") or "")
    if incident_mode and missing_files and artifact_source:
        _copy_collected_input_files(resolve_path(artifact_source), output_dir, preserve_existing_input=True)
        missing_files = _missing_collected_input_files(output_dir)
    return missing_files


def _write_collect_scope_output(
    output_root: Path,
    incident_dir: Path | None,
    incident_mode: bool,
    output_dir: Path,
    incident_id: str,
    middleware: str,
) -> int:
    output = adapter_output("analyse", incident_id, middleware, "completed", "collect scope analyse completed", output_dir)
    add_record_ref_if_exists(output, output_dir, "input", "input.yaml", "incident input context")
    add_record_ref_if_exists(output, output_dir, "structured_record", "structured_record.yaml", "phase-3 structured evidence")
    add_record_ref_if_exists(output, output_dir, "signal_bundle", "signal_bundle.yaml", "phase-3 governed signal bundle")
    add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "phase-3 collection summary")
    add_record_ref_if_exists(output, output_dir, "collection_plan", "collection_plan.yaml", "phase-3 script layer and cost plan")
    output["warnings"].append("collect scope stops after Phase 3; analysis.yaml and report.md are intentionally not generated.")
    existing_reasoning_outputs = [filename for filename in ("analysis.yaml", "report.md") if (output_dir / filename).exists()]
    reasoning_outputs = {}
    if existing_reasoning_outputs:
        reasoning_outputs = {
            "status": "stale",
            "analysis": "analysis.yaml" if (output_dir / "analysis.yaml").exists() else "",
            "report": "report.md" if (output_dir / "report.md").exists() else "",
            "required_user_action": "run /midstack:analyse --scope reason to refresh reasoning outputs",
        }
        output["reasoning_outputs"] = reasoning_outputs
        output["warnings"].append("existing analysis.yaml/report.md are stale after collect scope")
    output["next_actions"] = ["run /midstack:analyse --scope reason to generate reasoning outputs from the collected artifacts"]
    if incident_mode and incident_dir is not None:
        updates = {"status": "ready", "current_command": "analyse"}
        if reasoning_outputs:
            updates["reasoning_outputs"] = reasoning_outputs
        update_incident_meta(incident_dir, updates)
        write_current_incident(output_root, incident_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(output_dir))
    return 0


def _prepare_analysis_inputs(
    args,
    output_dir: Path,
    incident_mode: bool,
    run_remote_collection,
    run_local_collection,
    load_remote_executor_run_result,
    build_incident_from_remote_run,
) -> Dict[str, Any]:
    if args.remote_config:
        remote_run_dir = run_remote_collection(args, output_dir)
        remote_run_result = load_remote_executor_run_result(remote_run_dir)
        build_incident_from_remote_run(remote_run_dir, output_dir, args, preserve_existing_input=incident_mode)
        return remote_run_result
    if getattr(args, "local_config", ""):
        remote_run_dir = run_local_collection(args, output_dir)
        remote_run_result = load_remote_executor_run_result(remote_run_dir)
        build_incident_from_remote_run(remote_run_dir, output_dir, args, preserve_existing_input=incident_mode)
        return remote_run_result
    if args.remote_run_dir:
        remote_run_dir = resolve_path(args.remote_run_dir)
        remote_run_result = load_remote_executor_run_result(remote_run_dir)
        build_incident_from_remote_run(remote_run_dir, output_dir, args)
        return remote_run_result
    if not args.input_dir:
        return {}
    input_dir = resolve_path(args.input_dir)
    _copy_collected_input_files(input_dir, output_dir)
    return {}


def _prepare_phase3_context(
    args,
    output_dir: Path,
    input_data: Dict[str, Any],
    remote_run_result: Dict[str, Any],
    apply_scenario_routing_if_needed,
    enrich_skill_runtime_context,
    write_collection_plan,
    write_collection_coverage,
    write_signal_governance,
    run_directed_recollection_if_needed,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    if (output_dir / "signal_bundle.yaml").exists():
        input_data = apply_scenario_routing_if_needed(output_dir, args)
        write_collection_plan(output_dir, str(input_data.get("middleware") or "mongodb"))
        write_collection_coverage(output_dir)
        write_signal_governance(output_dir)
    skill_runtime: Dict[str, Any] = {}
    if (output_dir / "signal_bundle.yaml").exists():
        skill_runtime = enrich_skill_runtime_context(output_dir, input_data)
        input_data = load_yaml(output_dir / "input.yaml")
    skill_pool = skill_runtime.get("skill_pool") or set()
    if remote_run_result:
        try:
            run_directed_recollection_if_needed(args, output_dir, skill_pool=skill_pool or None)
            if skill_runtime:
                write_collection_plan(output_dir, str(input_data.get("middleware") or "mongodb"))
                write_collection_coverage(output_dir)
                write_signal_governance(output_dir)
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
    return input_data, skill_runtime


def _record_verification_recollection_gap(output_dir: Path, exc: Exception) -> None:
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    collection_report.setdefault("evidence_gaps", []).append(
        {
            "gap": "verification recollection failed: %s" % exc,
            "gap_type": "critical_gap",
            "related_stage": "verification_recollection",
            "why_important": "A first-class read-only verification request could not be collected automatically.",
            "recommended_action": "inspect directed-recollection logs and rerun the read-only playbook manually",
        }
    )
    collection_report["updated_at"] = now_iso()
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def _auto_allowed_verification_requests(analysis: Dict[str, Any]) -> list[Dict[str, Any]]:
    requests: list[Dict[str, Any]] = []
    for item in analysis.get("verification_requests") or []:
        if not isinstance(item, dict):
            continue
        asset = item.get("asset") or {}
        if not isinstance(asset, dict):
            continue
        if (
            item.get("asset_tier") == "first_class"
            and item.get("execution_policy") == "auto_allowed"
            and item.get("risk_level") == "read-only"
            and asset.get("type") == "script"
            and asset.get("id")
        ):
            requests.append(item)
    return requests


def _verification_execution_audit(output_dir: Path, requests: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    audit: list[Dict[str, Any]] = []
    for item in requests:
        asset = item.get("asset") or {}
        script_id = str(asset.get("id") or "")
        if not script_id:
            continue
        output_file = output_dir / "script_outputs" / script_id / "output.yaml"
        script_output = load_yaml(output_file) if output_file.exists() else {}
        audit.append(
            {
                "request_id": str(item.get("request_id") or ""),
                "hypothesis_id": str(item.get("hypothesis_id") or ""),
                "asset": {"type": "script", "id": script_id},
                "execution_policy": str(item.get("execution_policy") or ""),
                "risk_level": str(item.get("risk_level") or ""),
                "status": str(script_output.get("status") or "not_collected"),
                "summary": str(script_output.get("summary") or ""),
                "output_ref": "script_outputs/%s/output.yaml" % script_id if output_file.exists() else "",
            }
        )
    return audit


def _run_auto_allowed_verification_recollection(
    args,
    output_dir: Path,
    middleware: str,
    analysis_file: Path,
    run_directed_recollection_if_needed,
) -> list[Dict[str, Any]]:
    initial_analysis = load_yaml(analysis_file) if analysis_file.exists() else {}
    requests = _auto_allowed_verification_requests(initial_analysis)
    if not requests:
        return []
    try:
        recollected = run_directed_recollection_if_needed(args, output_dir)
    except Exception as exc:
        _record_verification_recollection_gap(output_dir, exc)
        return _verification_execution_audit(output_dir, requests)
    if not recollected:
        return _verification_execution_audit(output_dir, requests)
    audit = _verification_execution_audit(output_dir, requests)
    analysis = generate_rule_analysis(middleware, output_dir)
    write_yaml(analysis_file, analysis)
    return audit


def _agent_reasoning_summary(phase4_result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(phase4_result, dict) or not phase4_result.get("hypotheses"):
        return {}
    hypotheses = []
    for item in phase4_result.get("hypotheses") or []:
        if not isinstance(item, dict):
            continue
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        hypotheses.append(
            {
                "id": str(item.get("id") or ""),
                "statement": str(item.get("final_text") or ""),
                "status": str(status.get("status") or ""),
                "confidence": status.get("confidence", 0),
                "evidence_refs": _agent_hypothesis_evidence_refs(item),
                "conclusion_candidate": _agent_hypothesis_conclusion_candidate(item),
            }
        )
    if not hypotheses:
        return {}
    return {
        "artifact": "analysis.multitrack.yaml",
        "role": "auxiliary_draft",
        "runtime": phase4_result.get("agent_runtime") or {},
        "total_rounds": phase4_result.get("total_rounds", 0),
        "hypotheses": hypotheses,
        "boundary": "Agent draft is recorded for the main analyse path but does not override rules fallback conclusion_summary.",
    }


def _agent_hypothesis_evidence_refs(hypothesis: Dict[str, Any]) -> list[str]:
    refs: list[str] = []
    private_context = hypothesis.get("private_context") if isinstance(hypothesis.get("private_context"), dict) else {}
    for version in private_context.get("hypothesis_evolution") or []:
        if not isinstance(version, dict):
            continue
        for value in version.get("evidence") or []:
            source = str(value or "").strip()
            if source:
                refs.append(source)
    causal_chain = private_context.get("causal_chain") if isinstance(private_context.get("causal_chain"), dict) else {}
    for node in causal_chain.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        for value in node.get("evidence") or []:
            source = str(value or "").strip()
            if source:
                refs.append(source)
    return refs


def _agent_hypothesis_conclusion_candidate(hypothesis: Dict[str, Any]) -> Dict[str, Any]:
    private_context = hypothesis.get("private_context") if isinstance(hypothesis.get("private_context"), dict) else {}
    for version in reversed(private_context.get("hypothesis_evolution") or []):
        if not isinstance(version, dict):
            continue
        candidate = version.get("conclusion_candidate")
        if isinstance(candidate, dict) and candidate:
            return dict(candidate)
    return {}


def _write_deep_analysis(output_dir: Path, analysis: Dict[str, Any], signal_bundle: Dict[str, Any]) -> Dict[str, Any]:
    structured_record = load_yaml(output_dir / "structured_record.yaml") if (output_dir / "structured_record.yaml").exists() else {}
    deep_analysis = materialize_deep_analysis(analysis, structured_record, signal_bundle)
    write_yaml(output_dir / "deep-analysis.yaml", deep_analysis)
    return deep_analysis


def _write_completed_analysis_output(
    args,
    output_root: Path,
    incident_dir: Path | None,
    incident_mode: bool,
    previous_incident_status: str,
    output_dir: Path,
    incident_id: str,
    middleware: str,
    input_data: Dict[str, Any],
    skill_runtime: Dict[str, Any],
    analysis_file: Path,
    normalize_collection_report_gaps,
    run_phase4_analysis,
    run_directed_recollection_if_needed,
) -> int:
    scope = _analyse_scope(args)
    phase4_result: Dict[str, Any] = {}
    try:
        phase4_result = run_phase4_analysis(output_dir)
        print("Phase 4 reasoning completed: %d rounds" % phase4_result["total_rounds"], file=sys.stderr)
    except Exception as exc:
        print("Phase 4 warning: %s (falling back to rules analysis)" % exc, file=sys.stderr)
    try:
        analysis = generate_rule_analysis(middleware, output_dir)
        write_yaml(analysis_file, analysis)
    except Exception as exc:
        _restore_incident_status(incident_mode, incident_dir, previous_incident_status)
        output = adapter_output("analyse", incident_id, middleware, "failed", "local analyse failed", output_dir)
        output["warnings"].append(str(exc))
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    executed_validations = []
    if scope != ANALYSE_SCOPE_REASON:
        executed_validations = _run_auto_allowed_verification_recollection(
            args=args,
            output_dir=output_dir,
            middleware=middleware,
            analysis_file=analysis_file,
            run_directed_recollection_if_needed=run_directed_recollection_if_needed,
        )

    summary = "reason scope analyse completed" if scope == ANALYSE_SCOPE_REASON else "local analyse completed"
    output = adapter_output("analyse", incident_id, middleware, "completed", summary, output_dir)
    output["record_refs"].append({"name": "analysis", "path": str(analysis_file), "description": "generated analysis result"})
    add_record_ref_if_exists(output, output_dir, "collection_plan", "collection_plan.yaml", "phase-3 script layer and cost plan")
    add_record_ref_if_exists(
        output,
        output_dir,
        "analysis_multitrack",
        "analysis.multitrack.yaml",
        "multitrack reasoning draft; production analysis.yaml is generated by rules fallback",
    )
    analysis = load_yaml(analysis_file)
    collection_report = load_yaml(output_dir / "collection_report.yaml") if (output_dir / "collection_report.yaml").exists() else {}
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml") if (output_dir / "signal_bundle.yaml").exists() else {}
    if collection_report:
        normalize_collection_report_gaps(collection_report)
        write_yaml(output_dir / "collection_report.yaml", collection_report)
    if apply_analysis_guardrails(analysis, collection_report, signal_bundle):
        analysis["updated_at"] = now_iso()
        write_yaml(analysis_file, analysis)
    rules_fallback_file = write_analysis_rules_fallback(output_dir, analysis)
    agent_reasoning = _agent_reasoning_summary(phase4_result)
    if agent_reasoning:
        analysis["agent_reasoning"] = agent_reasoning
        analysis["agent_conclusion_gate"] = evaluate_agent_conclusion_gate(analysis)
        apply_agent_conclusion_override(analysis)
        analysis["updated_at"] = now_iso()
        write_yaml(analysis_file, analysis)
    deep_analysis = _write_deep_analysis(output_dir, analysis, signal_bundle)
    if deep_analysis.get("results"):
        analysis["deep_analysis_results"] = deep_analysis_summary(deep_analysis)
        if agent_reasoning:
            analysis["agent_conclusion_gate"] = evaluate_agent_conclusion_gate(analysis)
            apply_agent_conclusion_override(analysis)
        analysis["updated_at"] = now_iso()
        write_yaml(analysis_file, analysis)
    report_file = write_report(output_dir, input_data, analysis)
    task_file = write_agent_reasoning_task(
        output_dir,
        input_data,
        analysis_file,
        rules_fallback_file,
        report_file,
        matched_skills=skill_runtime.get("skills") if skill_runtime else None,
    )
    rules_reasoning_segment_file = write_reasoning_segment(
        output_dir,
        "rules_fallback",
        load_yaml(rules_fallback_file),
        summary="rules fallback seeded the first analysis",
        executed_validations=executed_validations,
        output_refs={
            "analysis": "analysis.yaml",
            "report": "report.md",
            "rules_fallback": rules_fallback_file.name,
            "agent_reasoning_task": task_file.name,
        },
    )
    reasoning_segment_file = rules_reasoning_segment_file
    if agent_reasoning:
        reasoning_segment_file = write_reasoning_segment(
            output_dir,
            "agent_multitrack",
            analysis,
            summary="agent multitrack draft recorded in production analysis view",
            depends_on=[rules_reasoning_segment_file.stem],
            output_refs={
                "analysis": "analysis.yaml",
                "report": "report.md",
                "rules_fallback": rules_fallback_file.name,
                "agent_reasoning_task": task_file.name,
                "analysis_multitrack": "analysis.multitrack.yaml",
            },
        )
    if deep_analysis.get("results"):
        reasoning_segment_file = write_reasoning_segment(
            output_dir,
            "deep_analysis",
            analysis,
            summary="deep analysis requests materialized from current incident evidence",
            depends_on=[reasoning_segment_file.stem],
            output_refs={
                "analysis": "analysis.yaml",
                "report": "report.md",
                "rules_fallback": rules_fallback_file.name,
                "agent_reasoning_task": task_file.name,
                "analysis_multitrack": "analysis.multitrack.yaml",
                "deep_analysis": "deep-analysis.yaml",
            },
        )
    gate = analysis.get("agent_conclusion_gate") if isinstance(analysis.get("agent_conclusion_gate"), dict) else {}
    if gate.get("override_applied") is True:
        reasoning_segment_file = write_reasoning_segment(
            output_dir,
            "agent_conclusion_override",
            analysis,
            summary="eligible agent conclusion candidate applied to production analysis view",
            depends_on=[reasoning_segment_file.stem],
            output_refs={
                "analysis": "analysis.yaml",
                "report": "report.md",
                "rules_fallback": rules_fallback_file.name,
                "agent_reasoning_task": task_file.name,
                "analysis_multitrack": "analysis.multitrack.yaml",
            },
        )
    output["record_refs"].append(
        {
            "name": "analysis_rules_fallback",
            "path": str(rules_fallback_file),
            "description": "rules fallback analysis before Agent reasoning refinement",
        }
    )
    output["record_refs"].append(
        {
            "name": "agent_reasoning_task",
            "path": str(task_file),
            "description": "phase-4/5 Agent reasoning task and output contract",
        }
    )
    add_record_ref_if_exists(output, output_dir, "deep_analysis", "deep-analysis.yaml", "materialized Phase 4 deep analysis results")
    add_record_ref_if_exists(output, output_dir, "reasoning_manifest", REASONING_MANIFEST_FILENAME, "append-only reasoning history manifest")
    output["record_refs"].append(
        {
            "name": "reasoning_current_segment",
            "path": str(reasoning_segment_file),
            "description": "current append-only reasoning segment",
        }
    )
    output["record_refs"].append({"name": "report", "path": str(report_file), "description": "generated human-readable report"})
    agent_runtime = phase4_result.get("agent_runtime") if isinstance(phase4_result, dict) else {}
    if agent_runtime:
        selected_agent = str(agent_runtime.get("selected_type") or "")
        fallback_reason = str(agent_runtime.get("fallback_reason") or "")
        if fallback_reason:
            output["warnings"].append("Phase 4 agent runtime selected %s: %s" % (selected_agent, fallback_reason))
        else:
            output["warnings"].append("Phase 4 agent runtime selected %s for multitrack reasoning." % selected_agent)
    gate = analysis.get("agent_conclusion_gate") if isinstance(analysis.get("agent_conclusion_gate"), dict) else {}
    if gate.get("override_applied") is True:
        output["warnings"].append("analysis.yaml conclusion_summary was updated from an eligible agent_conclusion_gate candidate.")
    else:
        output["warnings"].append("analysis.yaml conclusion_summary is guarded by rules fallback; agent_reasoning records Phase 4 multitrack draft for the main analyse path.")
    output["next_actions"] = [
        "review report.md and analysis.yaml for guarded conclusion, verification requests, and agent_reasoning draft",
        "use first-class read-only verification requests to close remaining critical evidence gaps",
    ]
    if incident_mode and incident_dir is not None:
        update_incident_meta(incident_dir, {"status": "analysed", "current_command": "analyse"})
        write_current_incident(output_root, incident_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(analysis_file))
    return 0


def run(
    args,
    *,
    run_remote_collection,
    run_local_collection,
    load_remote_executor_run_result,
    build_incident_from_remote_run,
    apply_scenario_routing_if_needed,
    enrich_skill_runtime_context,
    write_collection_plan,
    write_collection_coverage,
    write_signal_governance,
    run_directed_recollection_if_needed,
    remote_executor_required_user_action,
    remote_executor_next_actions,
    normalize_collection_report_gaps,
    run_phase4_analysis,
) -> int:
    output_root = path_from_arg(args.output_root)
    scope = _analyse_scope(args)
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
        mode_name = _execution_mode_name_from_incident(input_data)
        try:
            execution_mode = resolve_execution_mode(mode_name)
        except ValueError:
            return _write_unsupported_execution_mode_output(incident_dir, mode_name)
        args.execution_mode = execution_mode.name
        args.incident_input = input_data
        args.incident_id_override = str(input_data.get("incident_id") or incident_dir.name)
        object_inventory_file = incident_dir / "object-inventory.yaml"
        if object_inventory_file.exists():
            args.object_inventory = str(object_inventory_file)
        args.remote_namespace = args.remote_namespace or str(input_data.get("namespace") or "")
        args.customer_clue = args.customer_clue or str(input_data.get("customer_clue") or "")
        args.scenario = args.scenario or str(input_data.get("scenario") or "unknown")
        if scope == ANALYSE_SCOPE_REASON:
            missing_files = _ensure_reason_scope_artifacts(args, output_dir, input_data, incident_mode=incident_mode)
            if missing_files:
                return _write_reason_scope_missing_artifacts_output(output_dir, input_data, missing_files)
            args.remote_config = ""
            args.local_config = ""
        elif execution_mode.name == "offline":
            missing_files = _missing_collected_input_files(incident_dir)
            artifact_source = str(input_data.get("artifact_source") or "")
            if missing_files and artifact_source:
                _copy_collected_input_files(resolve_path(artifact_source), incident_dir, preserve_existing_input=True)
                input_data = load_yaml(incident_dir / "input.yaml")
                args.incident_input = input_data
                missing_files = _missing_collected_input_files(incident_dir)
            if missing_files:
                return write_blocked_output(
                    "analyse",
                    str(input_data.get("incident_id") or incident_dir.name),
                    str(input_data.get("middleware") or "mongodb"),
                    incident_dir,
                    "offline analyse needs existing collected artifacts",
                    [
                        {
                            "code": "offline_artifacts_missing",
                            "message": "missing required incident files: %s" % ", ".join(missing_files),
                            "required_user_action": "run remote analyse first or provide --input-dir/--remote-run-dir",
                        }
                    ],
                    ["run /midstack:analyse from a remote incident or provide existing artifacts"],
                )
            args.remote_config = ""
            args.local_config = ""
        elif execution_mode.name == "local":
            args.remote_config = ""
            args.local_config = str(incident_dir / "local-config.yaml")
            if not Path(args.local_config).exists():
                return _write_missing_local_config_output(incident_dir, input_data)
        else:
            args.remote_config = str(incident_dir / "remote-config.yaml")
            args.local_config = ""
        if scope != ANALYSE_SCOPE_REASON and execution_mode.name == "remote" and not Path(args.remote_config).exists():
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
        mode_name = _execution_mode_name_from_input_source(args)
        try:
            execution_mode = resolve_execution_mode(mode_name)
        except ValueError:
            return _write_unsupported_execution_mode_output(output_root, mode_name)
        args.execution_mode = execution_mode.name
        if not args.output_dir:
            print("ERROR: --output-dir is required unless --incident-dir is used", file=sys.stderr)
            return 1
        output_dir = path_from_arg(args.output_dir)
        if scope == ANALYSE_SCOPE_REASON:
            missing_files = _ensure_reason_scope_artifacts(args, output_dir, {}, incident_mode=incident_mode)
            input_data = load_yaml(output_dir / "input.yaml") if (output_dir / "input.yaml").exists() else {}
            if missing_files:
                return _write_reason_scope_missing_artifacts_output(output_dir, input_data, missing_files)
            args.remote_config = ""
            args.local_config = ""
    try:
        if incident_mode and incident_dir is not None:
            update_incident_meta(incident_dir, {"status": "analysing", "current_command": "analyse"})
        if scope != ANALYSE_SCOPE_REASON:
            remote_run_result = _prepare_analysis_inputs(
                args,
                output_dir,
                incident_mode,
                run_remote_collection,
                run_local_collection,
                load_remote_executor_run_result,
                build_incident_from_remote_run,
            )
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
    incident_id = str(input_data.get("incident_id") or output_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    if remote_run_result:
        run_status = str(remote_run_result.get("status") or "")
        run_error = remote_run_result.get("error") or {}
        error_code = str(run_error.get("code") or "")
        error_message = str(run_error.get("message") or "remote executor did not complete successfully")
        if run_status == "blocked":
            _restore_incident_status(incident_mode, incident_dir, previous_incident_status)
            return _write_remote_executor_blocked_output(
                output_dir,
                incident_id,
                middleware,
                error_code,
                error_message,
                remote_executor_required_user_action,
                remote_executor_next_actions,
            )
        if run_status == "failed":
            _restore_incident_status(incident_mode, incident_dir, previous_incident_status)
            return _write_remote_executor_failed_output(
                output_dir,
                incident_id,
                middleware,
                error_code,
                error_message,
                remote_executor_next_actions,
            )
    if scope == ANALYSE_SCOPE_REASON:
        skill_runtime = {}
    else:
        input_data, skill_runtime = _prepare_phase3_context(
            args,
            output_dir,
            input_data,
            remote_run_result,
            apply_scenario_routing_if_needed,
            enrich_skill_runtime_context,
            write_collection_plan,
            write_collection_coverage,
            write_signal_governance,
            run_directed_recollection_if_needed,
        )

    if scope == ANALYSE_SCOPE_COLLECT:
        return _write_collect_scope_output(
            output_root,
            incident_dir,
            incident_mode,
            output_dir,
            incident_id,
            middleware,
        )

    analysis_file = output_dir / "analysis.yaml"
    supported = supported_middlewares()
    if middleware not in supported:
        summary = "no analyse runner available for middleware %s" % middleware
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output = adapter_output("analyse", incident_id, middleware, "failed", summary, output_dir)
        output["blocking_items"] = [
            {
                "code": "unsupported_middleware_analyse",
                "message": summary,
                "required_user_action": "use a supported middleware or add a Phase 4 rules analyser for %s" % middleware,
            }
        ]
        output["next_actions"] = ["use a supported middleware such as %s" % ", ".join(supported)]
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % summary, file=sys.stderr)
        return 1
    return _write_completed_analysis_output(
        args,
        output_root,
        incident_dir,
        incident_mode,
        previous_incident_status,
        output_dir,
        incident_id,
        middleware,
        input_data,
        skill_runtime,
        analysis_file,
        normalize_collection_report_gaps,
        run_phase4_analysis,
        run_directed_recollection_if_needed,
    )
