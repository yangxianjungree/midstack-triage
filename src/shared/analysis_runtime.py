"""Analysis contract helpers shared by Midstack command entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analysis_common import analysis_text, as_list
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
    conclusion = analysis.get("conclusion_summary")
    if not isinstance(conclusion, dict):
        return False
    changed = False
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
    lines.extend(["", "## Hypotheses", ""])
    for item in as_list(analysis.get("hypotheses")):
        if not isinstance(item, dict):
            continue
        lines.append("- `%s` %s: %s" % (item.get("status", ""), item.get("hypothesis_id", ""), item.get("statement", "")))
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
            "",
            "## Evidence and Source Boundaries",
            "",
            "- Current incident artifacts are evidence; customer clues, historical cases, runbooks, and experience patterns are hypothesis or validation-path sources only.",
            "- Do not use a user clue or known historical answer as direct support for the current incident conclusion unless current evidence confirms it.",
            "- If a hypothesis came from a clue, runbook, or historical pattern, say so in the hypothesis statement, evidence gap, or validation action.",
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
            "- If a `critical_gap` can be closed by a known read-only playbook, record it as a `validation_action` with status `planned` or `blocked` and include it in `next_actions`.",
            "- Examples include healthy peer `rs.status`, `kubectl logs --previous`, peer connectivity checks, discovering the application log sink when `kubectl logs` is shallow, collecting MongoDB file log tails after log sink discovery, node-side file log tail from kubelet pod volumes for fast-crashing containers, pod describe/termination detail, CoreDNS/DNS probes for DNS lookup failures, and flannel overlay checks for DNS timeouts with suspicious Service backends.",
            "- DNS lookup errors in MongoDB startup logs support a DNS hypothesis; they should not become a mechanism-level conclusion unless CoreDNS state or an in-cluster DNS probe also supports it.",
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
            "",
        ]
    )
    task_file.write_text("\n".join(lines), encoding="utf-8")
    return task_file
