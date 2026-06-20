"""Analysis contract helpers shared by Midstack command entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis_common import analysis_text, as_list
from .verification_guardrails import apply_verification_request_guardrails
from .workspace import load_yaml, now_iso, write_yaml


ANALYSIS_RULES_FALLBACK_FILENAME = "analysis.rules-fallback.yaml"
LEGACY_ANALYSIS_RULE_DRAFT_FILENAME = "analysis.rule-draft.yaml"
ANALYSIS_RULE_DRAFT_FILENAME = ANALYSIS_RULES_FALLBACK_FILENAME
AGENT_REASONING_TASK_FILENAME = "agent-reasoning-task.md"


def analysis_summary_text(analysis: Dict[str, Any]) -> str:
    conclusion = analysis.get("conclusion_summary") or {}
    statement = str(conclusion.get("statement") or "").strip()
    confidence = str(conclusion.get("confidence") or "").strip()
    if statement and confidence:
        return "finalized analysis: %s (confidence=%s)" % (statement, confidence)
    if statement:
        return "finalized analysis: %s" % statement
    return "finalized analysis is available"


def analysis_next_action_texts(analysis: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    for item in as_list(analysis.get("next_actions")):
        if isinstance(item, dict):
            action = str(item.get("action") or "").strip()
            if action:
                items.append(action)
        elif item:
            items.append(str(item))
    return items


def timeline_report_lines(analysis: Dict[str, Any], limit: int = 8) -> List[str]:
    timeline = analysis.get("reasoning_timeline") or {}
    events = as_list(timeline.get("events") if isinstance(timeline, dict) else [])
    layer_priority = {"diagnostic": 0, "signal": 1, "kubernetes": 2, "analysis": 3, "collection": 4}
    events = sorted(
        events,
        key=lambda item: (
            layer_priority.get(str((item or {}).get("layer") or ""), 9) if isinstance(item, dict) else 9,
            str((item or {}).get("time") or "") if isinstance(item, dict) else "",
            str((item or {}).get("summary") or "") if isinstance(item, dict) else "",
        ),
    )
    lines: List[str] = []
    for item in events[:limit]:
        if not isinstance(item, dict):
            continue
        summary = str(item.get("summary") or "").strip()
        if not summary:
            continue
        time = str(item.get("time") or "time unknown").strip()
        time_precision = str(item.get("time_precision") or "").strip()
        time_label = ""
        if time_precision == "log_local_time":
            time_label = " `(log-local)`"
        layer = str(item.get("layer") or "unknown").strip()
        source = str(item.get("source") or "").strip()
        suffix = " source=%s" % source if source else ""
        lines.append("- `%s`%s `%s` %s%s" % (time, time_label, layer, summary, suffix))
    if not lines:
        return ["- No timeline events recorded."]
    if len(events) > limit:
        lines.append("- ... %s more event(s) omitted from report; see `analysis.yaml`." % (len(events) - limit))
    return lines


def deepening_report_lines(analysis: Dict[str, Any], limit: int = 8) -> List[str]:
    findings = as_list(analysis.get("deepening_findings"))
    lines: List[str] = []
    for item in findings[:limit]:
        if not isinstance(item, dict):
            continue
        statement = str(item.get("statement") or "").strip()
        if not statement:
            continue
        finding_id = str(item.get("finding_id") or "finding").strip()
        severity = str(item.get("severity") or "unknown").strip()
        supports = [str(value) for value in as_list(item.get("supports")) if str(value).strip()]
        refutes = [str(value) for value in as_list(item.get("refutes")) if str(value).strip()]
        suffixes = []
        if supports:
            suffixes.append("supports=%s" % ",".join(supports))
        if refutes:
            suffixes.append("refutes=%s" % ",".join(refutes))
        suffix = " %s" % " ".join(suffixes) if suffixes else ""
        lines.append("- `%s` `%s` %s%s" % (severity, finding_id, statement, suffix))
    if not lines:
        return ["- No mechanism-deepening findings recorded."]
    if len(findings) > limit:
        lines.append("- ... %s more finding(s) omitted from report; see `analysis.yaml`." % (len(findings) - limit))
    return lines


def verification_request_report_lines(analysis: Dict[str, Any], limit: int = 8) -> List[str]:
    requests = as_list(analysis.get("verification_requests"))
    lines: List[str] = []
    for item in requests[:limit]:
        if not isinstance(item, dict):
            continue
        request_id = str(item.get("request_id") or "verification").strip()
        hypothesis_id = str(item.get("hypothesis_id") or "unknown").strip()
        purpose = str(item.get("purpose") or "").strip()
        status = str(item.get("status") or "unknown").strip()
        risk_level = str(item.get("risk_level") or "unknown").strip()
        execution_policy = str(item.get("execution_policy") or "unknown").strip()
        asset_tier = str(item.get("asset_tier") or "unknown").strip()
        reason = str(item.get("reason") or "").strip()
        asset = item.get("asset") or {}
        asset_type = str(asset.get("type") or "unknown").strip() if isinstance(asset, dict) else "unknown"
        asset_id = str(asset.get("id") or "unknown").strip() if isinstance(asset, dict) else "unknown"
        argv = asset.get("argv") if isinstance(asset, dict) else []
        guardrail_reason = str(item.get("guardrail_reason") or "").strip()
        suffixes = ["asset=%s/%s" % (asset_type, asset_id)]
        if isinstance(argv, list) and argv:
            suffixes.append("argv=%s" % " ".join(str(part) for part in argv))
        if guardrail_reason:
            suffixes.append("guardrail=%s" % guardrail_reason)
        if reason:
            suffixes.append("reason=%s" % reason)
        suffix = " %s" % " ".join(suffixes)
        lines.append(
            "- `%s` `%s` `%s` `%s` `%s` %s: %s%s"
            % (status, risk_level, execution_policy, asset_tier, request_id, hypothesis_id, purpose, suffix)
        )
    if not lines:
        return ["- No verification requests recorded."]
    if len(requests) > limit:
        lines.append("- ... %s more request(s) omitted from report; see `analysis.yaml`." % (len(requests) - limit))
    return lines


def deep_analysis_request_report_lines(analysis: Dict[str, Any], limit: int = 8) -> List[str]:
    requests = as_list(analysis.get("deep_analysis_requests"))
    lines: List[str] = []
    for item in requests[:limit]:
        if not isinstance(item, dict):
            continue
        request_id = str(item.get("request_id") or "deep-analysis").strip()
        capability = str(item.get("capability") or "unknown").strip()
        purpose = str(item.get("purpose") or "").strip()
        status = str(item.get("status") or "unknown").strip()
        risk_level = str(item.get("risk_level") or "unknown").strip()
        execution_boundary = str(item.get("execution_boundary") or "unknown").strip()
        inputs = [str(value) for value in as_list(item.get("inputs")) if str(value).strip()]
        expected = [str(value) for value in as_list(item.get("expected_output")) if str(value).strip()]
        suffixes = []
        if inputs:
            suffixes.append("inputs=%s" % ",".join(inputs))
        if expected:
            suffixes.append("expected=%s" % ",".join(expected))
        suffix = " %s" % " ".join(suffixes) if suffixes else ""
        lines.append(
            "- `%s` `%s` `%s` `%s` `%s`: %s%s"
            % (status, risk_level, execution_boundary, capability, request_id, purpose, suffix)
        )
    if not lines:
        return ["- No deep analysis requests recorded."]
    if len(requests) > limit:
        lines.append("- ... %s more request(s) omitted from report; see `analysis.yaml`." % (len(requests) - limit))
    return lines


def agent_reasoning_report_lines(analysis: Dict[str, Any], limit: int = 6) -> List[str]:
    agent_reasoning = analysis.get("agent_reasoning")
    if not isinstance(agent_reasoning, dict):
        return ["- No agent reasoning draft recorded."]
    runtime = agent_reasoning.get("runtime") if isinstance(agent_reasoning.get("runtime"), dict) else {}
    selected_type = str(runtime.get("selected_type") or "unknown").strip()
    model = str(runtime.get("model") or "unknown").strip()
    artifact = str(agent_reasoning.get("artifact") or "unknown").strip()
    lines = ["- Runtime: `%s` `%s` `%s`" % (selected_type, model, artifact)]
    boundary = str(agent_reasoning.get("boundary") or "").strip()
    if boundary:
        lines.append("- Boundary: %s" % boundary)
    for item in as_list(agent_reasoning.get("hypotheses"))[:limit]:
        if not isinstance(item, dict):
            continue
        hypothesis_id = str(item.get("id") or "hypothesis").strip()
        status = str(item.get("status") or "unknown").strip()
        confidence = str(item.get("confidence") if item.get("confidence") is not None else "unknown").strip()
        statement = str(item.get("statement") or "").strip()
        if statement:
            lines.append("- `%s` `%s` %s: %s" % (status, confidence, hypothesis_id, statement))
    if len(as_list(agent_reasoning.get("hypotheses"))) > limit:
        lines.append("- ... %s more hypothesis draft(s) omitted from report; see `analysis.yaml`." % (len(as_list(agent_reasoning.get("hypotheses"))) - limit))
    return lines


def analysis_rules_fallback_candidates(output_dir: Path) -> List[Path]:
    return [
        output_dir / ANALYSIS_RULES_FALLBACK_FILENAME,
        output_dir / LEGACY_ANALYSIS_RULE_DRAFT_FILENAME,
    ]


def find_analysis_rules_fallback_file(output_dir: Path) -> Optional[Path]:
    for path in analysis_rules_fallback_candidates(output_dir):
        if path.exists():
            return path
    return None


def write_analysis_rules_fallback(output_dir: Path, analysis: Dict[str, Any]) -> Path:
    primary = output_dir / ANALYSIS_RULES_FALLBACK_FILENAME
    write_yaml(primary, analysis)
    legacy = output_dir / LEGACY_ANALYSIS_RULE_DRAFT_FILENAME
    if legacy.exists():
        write_yaml(legacy, analysis)
    return primary


def analysis_matches_rules_fallback(analysis: Dict[str, Any], output_dir: Path) -> bool:
    for path in analysis_rules_fallback_candidates(output_dir):
        if not path.exists():
            continue
        try:
            if analysis == load_yaml(path):
                return True
        except Exception:
            continue
    return False


analysis_matches_rule_draft = analysis_matches_rules_fallback


def direct_error_terms_present(analysis: Dict[str, Any]) -> bool:
    text = analysis_text(analysis)
    return any(term in text for term in ("fatal", "wiredtiger", "corrupt", "journal", "bad magic number", "assertion", "unclean shutdown"))


def signal_bundle_has_id(signal_bundle: Dict[str, Any], signal_id: str) -> bool:
    for item in signal_bundle.get("abnormal_signals") or []:
        if isinstance(item, dict) and str(item.get("signal_id") or "") == signal_id:
            return True
    return False


def append_limitation(conclusion: Dict[str, Any], limitation: Dict[str, Any]) -> None:
    limitations = conclusion.setdefault("limitations", [])
    if not isinstance(limitations, list):
        limitations = [limitations]
        conclusion["limitations"] = limitations
    text = json.dumps(limitation, sort_keys=True)
    for item in limitations:
        if json.dumps(item, sort_keys=True) == text:
            return
    limitations.append(limitation)


def collection_report_has_critical_gap(collection_report: Dict[str, Any]) -> bool:
    for item in collection_report.get("evidence_gaps") or []:
        if isinstance(item, dict) and str(item.get("gap_type") or "") == "critical_gap":
            return True
    return False


def hypothesis_has_gap(hypothesis: Dict[str, Any], text: str) -> bool:
    needle = text.lower()
    for item in as_list(hypothesis.get("evidence_gaps")):
        if isinstance(item, dict) and needle in str(item.get("gap") or "").lower():
            return True
        if needle in str(item).lower():
            return True
    return False


def hypothesis_has_planned_validation(hypothesis: Dict[str, Any], text: str) -> bool:
    needle = text.lower()
    for item in as_list(hypothesis.get("validation_actions")):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").lower()
        action = str(item.get("action") or "").lower()
        if status == "planned" and needle in action:
            return True
    return False


def enforce_split_brain_enabling_cause_guardrail(analysis: Dict[str, Any]) -> bool:
    changed = False
    for hypothesis in as_list(analysis.get("hypotheses")):
        if not isinstance(hypothesis, dict):
            continue
        statement = str(hypothesis.get("statement") or "").lower()
        if "configuration or member metadata drift" not in statement:
            continue
        needs_rs_conf = hypothesis_has_gap(hypothesis, "rs.conf") or hypothesis_has_planned_validation(hypothesis, "rs.conf")
        if not needs_rs_conf:
            continue
        if hypothesis.get("status") == "supported":
            hypothesis["status"] = "insufficient"
            changed = True
        if hypothesis.get("validation_result") == "supported":
            hypothesis["validation_result"] = "insufficient"
            changed = True

        conclusion = analysis.get("conclusion_summary") or {}
        if isinstance(conclusion, dict) and conclusion.get("primary_cause_category") == "replica_set_config_divergence":
            conclusion["primary_cause_category"] = "split_brain_enabling_cause_unproven"
            append_limitation(
                conclusion,
                {
                    "gap": "rs.conf() comparison across all affected members is not available",
                    "gap_type": "critical_gap",
                    "related_stage": "finalize",
                    "why_important": "Divergent member views support a split-brain mechanism, but config drift as the enabling cause remains unproven until rs.conf() is compared.",
                },
            )
            changed = True
    return changed


def direct_root_cause_terms_present(analysis: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    text = analysis_text(analysis)
    if direct_error_terms_present(analysis):
        return True
    if any(token in text for token in ("flannel-vxlan-down", "flannel.1", "vxlan", "overlay partition", "pod-subnet-isolated")):
        return True
    return any(
        signal_bundle_has_id(signal_bundle, signal_id)
        for signal_id in ("flannel-vxlan-down", "flannel-route-install-failed", "pod-subnet-isolated", "kube-dns-backend-on-overlay-partition")
    )


def apply_analysis_guardrails(analysis: Dict[str, Any], collection_report: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    changed = False
    if apply_verification_request_guardrails(analysis):
        changed = True
    conclusion = analysis.get("conclusion_summary")
    if not isinstance(conclusion, dict):
        return changed
    if enforce_split_brain_enabling_cause_guardrail(analysis):
        changed = True
    direct_root_cause_supported = direct_root_cause_terms_present(analysis, signal_bundle)
    if not conclusion.get("deepest_supported_level"):
        category = str(conclusion.get("primary_cause_category") or "")
        if direct_root_cause_supported:
            conclusion["deepest_supported_level"] = "root_cause"
        elif category.startswith("kubernetes-") or category in ("container-restart", "service-routing"):
            conclusion["deepest_supported_level"] = "impact"
        else:
            conclusion["deepest_supported_level"] = "phenomenon"
        changed = True

    level = str(conclusion.get("deepest_supported_level") or "")
    confidence = str(conclusion.get("confidence") or "")
    if collection_report_has_critical_gap(collection_report) and level == "root_cause" and confidence == "high" and not direct_root_cause_supported:
        conclusion["confidence"] = "medium"
        append_limitation(
            conclusion,
            {
                "gap": "unresolved critical_gap limits root-cause confidence",
                "gap_type": "critical_gap",
                "related_stage": "finalize",
                "why_important": "Final root-cause confidence was capped because critical evidence gaps remain open.",
            },
        )
        changed = True
    if signal_bundle_has_id(signal_bundle, "pod-crashloop") and level == "root_cause" and not direct_root_cause_supported:
        conclusion["deepest_supported_level"] = "impact"
        if confidence == "high":
            conclusion["confidence"] = "medium"
        append_limitation(
            conclusion,
            {
                "gap": "MongoDB process-internal fatal evidence is not present",
                "gap_type": "critical_gap",
                "related_stage": "finalize",
                "why_important": "CrashLoopBackOff supports process failure but not the internal MongoDB root cause.",
                "recommended_action": "discover application log sink and collect MongoDB file logs if kubectl logs is too short",
            },
        )
        changed = True
    return changed


def write_report(output_dir: Path, input_data: Dict[str, Any], analysis: Dict[str, Any]) -> Path:
    conclusion = analysis.get("conclusion_summary") or {}
    report_file = output_dir / "report.md"
    lines = [
        "# Midstack Triage Report",
        "",
        "## Incident",
        "",
        "- Incident ID: `%s`" % input_data.get("incident_id", output_dir.name),
        "- Middleware: `%s`" % input_data.get("middleware", "mongodb"),
        "- Namespace: `%s`" % input_data.get("namespace", ""),
        "- Cluster: `%s`" % input_data.get("cluster_id", ""),
        "- Customer clue: %s" % input_data.get("customer_clue", ""),
        "",
        "## Conclusion",
        "",
        "- Statement: %s" % conclusion.get("statement", ""),
        "- Confidence: `%s`" % conclusion.get("confidence", ""),
        "- Deepest supported level: `%s`" % conclusion.get("deepest_supported_level", ""),
        "- Primary cause category: `%s`" % conclusion.get("primary_cause_category", ""),
        "- Impact scope: %s" % conclusion.get("impact_scope", ""),
        "",
        "## Evidence",
        "",
    ]
    evidence = as_list(conclusion.get("evidence"))
    lines.extend(["- %s" % item for item in evidence] if evidence else ["- No explicit evidence recorded."])
    lines.extend(["", "## Timeline", ""])
    lines.extend(timeline_report_lines(analysis))
    lines.extend(["", "## Mechanism Deepening", ""])
    lines.extend(deepening_report_lines(analysis))
    lines.extend(["", "## Hypotheses", ""])
    for item in as_list(analysis.get("hypotheses")):
        if not isinstance(item, dict):
            continue
        lines.append("- `%s` %s: %s" % (item.get("status", ""), item.get("hypothesis_id", ""), item.get("statement", "")))
    lines.extend(["", "## Verification Requests", ""])
    lines.extend(verification_request_report_lines(analysis))
    lines.extend(["", "## Deep Analysis Requests", ""])
    lines.extend(deep_analysis_request_report_lines(analysis))
    lines.extend(["", "## Agent Reasoning Draft", ""])
    lines.extend(agent_reasoning_report_lines(analysis))
    lines.extend(["", "## Evidence Gaps", ""])
    gaps = as_list(conclusion.get("limitations"))
    if gaps:
        for item in gaps:
            if isinstance(item, dict):
                gap_type = str(item.get("gap_type") or "gap")
                gap = str(item.get("gap") or item)
                why = str(item.get("why_important") or "").strip()
                suffix = " %s" % why if why else ""
                lines.append("- `[%s]` %s%s" % (gap_type, gap, suffix))
            else:
                lines.append("- %s" % item)
    else:
        lines.append("- No explicit evidence gaps recorded.")
    lines.extend(["", "## Next Read-Only Actions", ""])
    actions = as_list(analysis.get("next_actions"))
    lines.extend(["- %s" % ((item or {}).get("action") if isinstance(item, dict) else item) for item in actions] if actions else ["- No next actions recorded."])
    lines.extend(["", "## Knowledge Candidates", ""])
    candidates = as_list(analysis.get("knowledge_candidates"))
    if candidates:
        for item in candidates:
            if isinstance(item, dict):
                lines.append("- `%s` %s: `%s`" % (item.get("candidate_type", ""), item.get("title", ""), item.get("asset_path", "")))
    else:
        lines.append("- No knowledge candidates recorded.")
    lines.append("")
    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file


def write_agent_reasoning_task(
    output_dir: Path,
    input_data: Dict[str, Any],
    analysis_file: Path,
    rules_fallback_file: Path,
    report_file: Path,
    matched_skills: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    from shared.skill_resolver import extract_skill_workflow, matched_asset_refs, resolve_skills

    task_file = output_dir / AGENT_REASONING_TASK_FILENAME
    middleware = str(input_data.get("middleware") or "mongodb")
    scenario = str(input_data.get("scenario") or "unknown")
    if matched_skills is None:
        matched_skills = resolve_skills(middleware, scenario)
    inference = input_data.get("scenario_inference") or {}
    lines = [
        "# Midstack Agent Reasoning Task",
        "",
        "## Goal",
        "",
        "Use the stage-3 evidence package to complete stage-4 reasoning and stage-5 summarization.",
        "Treat `%s` as a non-authoritative rules fallback only." % rules_fallback_file.name,
        "",
        "## Incident",
        "",
        "- Incident ID: `%s`" % input_data.get("incident_id", output_dir.name),
        "- Middleware: `%s`" % middleware,
        "- Scenario: `%s`" % scenario,
        "- Scenario inference confidence: `%s`" % inference.get("confidence", "unknown"),
        "- Scenario unresolved: `%s`" % inference.get("unresolved", False),
        "- Namespace: `%s`" % input_data.get("namespace", ""),
        "- Cluster: `%s`" % input_data.get("cluster_id", ""),
        "- Customer clue: %s" % input_data.get("customer_clue", ""),
        "",
        "## Matched Assets",
        "",
    ]
    if matched_skills:
        for skill in matched_skills:
            metadata = skill["metadata"]
            lines.append(
                "- Skill `%s` (`%s`): %s"
                % (skill["id"], skill["skill_dir"].relative_to(Path(__file__).resolve().parents[2]), metadata.get("title", ""))
            )
            workflow = extract_skill_workflow(skill["skill_md_path"])
            if workflow:
                lines.append("  - Workflow excerpt:")
                for workflow_line in workflow.splitlines():
                    lines.append("    - %s" % workflow_line.lstrip("- ").strip())
    else:
        lines.append("- No matched skill for scenario `%s`." % scenario)
    for asset in input_data.get("matched_assets") or matched_asset_refs(middleware, matched_skills):
        if asset.get("path"):
            lines.append("- %s `%s` → `%s`" % (asset.get("type"), asset.get("id"), asset.get("path")))
    lines.extend(
        [
            "",
            "## Read First",
            "",
            "- `input.yaml`: frozen start-stage input and customer clue.",
            "- `structured_record.yaml`: structured object, topology, status, and log details.",
            "- `signal_bundle.yaml`: curated abnormal signals, object links, and timeline hints.",
            "- `collection_report.yaml`: collection coverage, failures, and evidence gaps.",
            "- `%s`: current rules fallback analysis for reference only." % rules_fallback_file.name,
            "",
            "## Required Output Files",
            "",
            "- Update `%s` as the formal phase-4/5 output." % analysis_file.name,
            "- Update `%s` so it matches the final `%s`." % (report_file.name, analysis_file.name),
            "",
            "## Analysis Contract",
            "",
            "- Produce multiple hypotheses when evidence supports multiple plausible paths.",
            "- Each hypothesis must include `hypothesis_id`, `statement`, `causal_path`, `supporting_evidence`, `counter_evidence`, `disconfirming_conditions`, `evidence_gaps`, `validation_actions`, and `validation_result`.",
            "- `validation_result` must be one of `supported`, `refuted`, or `insufficient`.",
            "- Classify material evidence gaps as `expected_gap` or `critical_gap` in the relevant hypothesis or conclusion text.",
            "- `expected_gap` means the missing evidence is common or has a reasonable substitute; `critical_gap` means the missing evidence limits hypothesis validation or conclusion depth.",
            "- `conclusion_summary` must include `statement`, `confidence`, `impact_scope`, `primary_cause_category`, `evidence`, and `limitations`.",
            "- When useful, include `deepest_supported_level` in `conclusion_summary` with one of `phenomenon`, `impact`, `mechanism`, or `root_cause`.",
            "- `next_actions` should stay read-only unless the evidence clearly justifies a higher-risk action.",
            "- Distinguish missing evidence from evidence that disproves a hypothesis.",
            "- If evidence is insufficient, keep the conclusion and hypothesis status conservative instead of forcing certainty.",
            "- Preserve top-level `deepening_findings`, `reasoning_timeline`, `verification_requests`, `deep_analysis_requests`, `retrieval_context`, `experience_matches`, and `source_boundaries`; these fields must stay present when refining `analysis.yaml`.",
            "- Use `reasoning_timeline` to correlate symptoms, collection actions, and hypothesis checks, but do not treat ordering alone as proof of causality.",
            "- Use `deepening_findings` to continue from a mechanism conclusion toward enabling/root cause; if a finding refutes a candidate mechanism, do not repeat it as an unqualified next action.",
            "",
            "## Evidence and Source Boundaries",
            "",
            "- Current incident artifacts are evidence; customer clues, historical cases, runbooks, and experience patterns are hypothesis or validation-path sources only.",
            "- Do not use a user clue or known historical answer as direct support for the current incident conclusion unless current evidence confirms it.",
            "- `experience_matches` and other hypothesis-only sources must not become direct supporting evidence in `supporting_evidence` or `conclusion_summary.evidence`.",
            "- If a hypothesis came from a clue, runbook, or historical pattern, say so in the hypothesis statement, evidence gap, or validation action.",
            "",
            "## Experience Retrieval Contract",
            "",
            "- `retrieval_context` is a future retrieval query context derived from current incident inputs, signals, objects, and evidence gaps; do not use it as a conclusion.",
            "- `experience_matches` is currently an empty list unless a real retrieval implementation populates it.",
            "- `source_boundaries` records which sources are current-incident evidence and which are hypothesis-only sources.",
            "",
            "## Conclusion Ceiling",
            "",
            "- Keep `conclusion_summary.statement` within the deepest level directly supported by current evidence.",
            "- Kubernetes runtime, event, and readiness signals can support phenomenon or impact conclusions; they do not by themselves prove process-internal root cause.",
            "- Missing peer `rs.status`, missing MongoDB fatal logs, or unresolved `critical_gap` should cap root-cause confidence at low or medium.",
            "- If the root cause is not directly supported, write the likely path as a hypothesis and put the required read-only validation in `next_actions`.",
            "",
            "## Directed Recollection Guidance",
            "",
            "- This task does not authorize arbitrary shell execution.",
            "- Prefer first-class repository read-only assets for repeatable validations.",
            "- If a `critical_gap` can be closed by a first-class repository read-only asset, record it as a `validation_action` with status `planned` or `blocked` and include it in `next_actions`.",
            "- If a `critical_gap` needs a second-class ad hoc read-only command, record it under top-level `verification_requests` instead of writing a free shell command.",
            "- Ad hoc command requests must use `asset_tier: ad_hoc_readonly`, `asset.type: ad_hoc_command`, structured `asset.argv`, `risk_level: read-only`, `execution_policy: approval_required`, and `status: planned`.",
            "- Do not use shell strings, pipes, redirects, mutation commands, or environment-changing commands in ad hoc requests.",
            "- This task does not authorize auto-executing ad hoc commands; if a command changes state or cannot pass the read-only guardrail, mark it with `execution_policy: blocked`.",
            "- Examples include healthy peer `rs.status`, `kubectl logs --previous`, peer connectivity checks, discovering the application log sink when `kubectl logs` is shallow, collecting MongoDB file log tails after log sink discovery, node-side file log tail from kubelet pod volumes for fast-crashing containers, pod describe/termination detail, CoreDNS/DNS probes for DNS lookup failures, and flannel overlay checks for DNS timeouts with suspicious Service backends.",
            "- DNS lookup errors in MongoDB startup logs support a DNS hypothesis; they should not become a mechanism-level conclusion unless CoreDNS state or an in-cluster DNS probe also supports it.",
            "",
            "## Deep Analysis Guidance",
            "",
            "- Use `deep_analysis_requests` for deeper reasoning work that should be visible but is not itself an executable collection action.",
            "- Supported capabilities are `baseline_scan`, `code_logic_analysis`, `code_path_tracing`, and `repro_script_generation`.",
            "- These requests are plan-only by default: `execution_boundary: plan_only`, `risk_level: read-only`, and `scope: current_incident`.",
            "- If a deep analysis needs more live evidence, express that as a guarded `verification_requests` entry; do not smuggle shell commands into `deep_analysis_requests`.",
            "- A repro request should produce a read-only plan, fixture, or simulator proposal. It must not mutate the live cluster, reconfigure MongoDB, restart pods, or write workload data.",
            "",
            "## Timeline Reporting",
            "",
            "- Keep `reasoning_timeline.events` sourced to current incident artifacts.",
            "- Report the key timeline events in `report.md` so readers can see what happened and when.",
            "- If event time is unknown, keep `time_precision: unknown` instead of inventing timestamps.",
            "",
            "## Working Rules",
            "",
            "- Prefer `signal_bundle.yaml` and `collection_report.yaml` for reasoning inputs; use `structured_record.yaml` for necessary detail lookup.",
            "- Before finalizing, inspect `signal_bundle.log_highlights`, `structured_record.details.dns_checks`, `structured_record.details.network_overlay`, `structured_record.details.kube_dns_endpoints`, `structured_record.details.pod_terminations`, and any `file_tail` log evidence.",
            "- Treat `dns_checks.status=failed` with DNS-layer error text differently from `dns_checks.status=blocked`; blocked probes are evidence gaps, not DNS-failure evidence.",
            "- Do not silently rewrite `input.yaml` or other start-stage files.",
            "- Keep raw evidence references explicit in `supporting_evidence`, `counter_evidence`, and `limitations`.",
            "",
            "## Deliverable Check",
            "",
            "- `analysis.yaml` reflects the final Agent reasoning rather than the rules-only draft.",
            "- `analysis.yaml` records multi-hypothesis reasoning, gap severity, source boundaries, and conclusion ceiling where relevant.",
            "- `report.md` matches the final conclusion, confidence, evidence gaps, supported level, and next actions.",
            "- Run finalize after refinement so `reasoning-manifest.yaml` points at a new append-only reasoning segment instead of losing the previous reasoning history.",
            "",
        ]
    )
    task_file.write_text("\n".join(lines), encoding="utf-8")
    return task_file
