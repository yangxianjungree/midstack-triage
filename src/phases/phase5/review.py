"""Phase 5 review helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from shared.analysis_common import analysis_text, flatten_strings
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


LEVEL_VALUE = {"low": 1, "medium": 2, "high": 3}


def score_item(level: str, reason: str) -> Dict[str, str]:
    return {"level": level, "reason": reason}


def level_from_confidence(confidence: str) -> str:
    return "high" if confidence == "high" else ("medium" if confidence == "medium" else "low")


def overall_level(score: Dict[str, Dict[str, str]]) -> str:
    values = [LEVEL_VALUE.get(item.get("level", "low"), 1) for item in score.values()]
    average = sum(values) / float(len(values) or 1)
    if average >= 2.67:
        return "high"
    if average >= 1.67:
        return "medium"
    return "low"


def downgrade_level(level: str, target: str) -> str:
    current_value = LEVEL_VALUE.get(level, 1)
    target_value = LEVEL_VALUE.get(target, 1)
    if target_value < current_value:
        return target
    return level


def append_reason(item: Dict[str, str], reason: str) -> None:
    current = str(item.get("reason") or "").strip()
    item["reason"] = ("%s %s" % (current, reason)).strip() if current else reason


def conclusion_level(conclusion: Dict[str, Any]) -> str:
    level = str(conclusion.get("deepest_supported_level") or "").strip()
    if level:
        return level
    statement = str(conclusion.get("statement") or "").lower()
    category = str(conclusion.get("primary_cause_category") or "").lower()
    if "root" in statement or "root" in category or "corrupt" in statement or "journal" in statement or "fatal" in statement:
        return "root_cause"
    if "caused by" in statement or "because" in statement or "mechanism" in statement:
        return "mechanism"
    if "impact" in statement or "availability" in statement or "ready" in statement:
        return "impact"
    return "phenomenon"


def has_critical_gap(analysis: Dict[str, Any]) -> bool:
    text = analysis_text(analysis)
    return "critical_gap" in text or "critical gap" in text


def has_next_actions(analysis: Dict[str, Any]) -> bool:
    value = analysis.get("next_actions")
    return isinstance(value, list) and bool(value)


def supported_hypotheses(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    hypotheses = [item for item in analysis.get("hypotheses") or [] if isinstance(item, dict)]
    return [item for item in hypotheses if item.get("status") == "supported" or item.get("validation_result") == "supported"]


def insufficient_hypotheses(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    hypotheses = [item for item in analysis.get("hypotheses") or [] if isinstance(item, dict)]
    return [item for item in hypotheses if item.get("status") == "insufficient" or item.get("validation_result") == "insufficient"]


def review_process_findings(analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    conclusion = analysis.get("conclusion_summary") or {}
    confidence = str(conclusion.get("confidence") or "low")
    level = conclusion_level(conclusion)
    text = analysis_text(analysis)
    findings: List[Dict[str, str]] = []

    if any(token in text for token in ("answer-led", "answer_led", "known answer", "historical answer", "user disclosed", "customer clue as evidence")):
        findings.append(
            {
                "code": "answer_led_bias",
                "severity": "must_fix",
                "message": "Potential answer-led bias: clue, historical answer, or disclosed answer appears to support the conclusion.",
            }
        )

    if level == "root_cause" and confidence == "high" and not supported_hypotheses(analysis):
        findings.append(
            {
                "code": "surface_to_root_cause_jump",
                "severity": "should_fix",
                "message": "Root-cause conclusion is high confidence without a supported hypothesis path.",
            }
        )

    if level == "root_cause" and not (conclusion.get("evidence") or []):
        findings.append(
            {
                "code": "missing_evidence_bridge",
                "severity": "should_fix",
                "message": "Root-cause conclusion has no explicit evidence bridge in conclusion_summary.evidence.",
            }
        )

    if has_critical_gap(analysis):
        if not has_next_actions(analysis):
            findings.append(
                {
                    "code": "critical_gap_ignored",
                    "severity": "must_fix",
                    "message": "A critical gap is recorded but no next action explains how to close or escalate it.",
                }
            )
        if level == "root_cause" and confidence == "high":
            findings.append(
                {
                    "code": "overconfident_conclusion",
                    "severity": "must_fix",
                    "message": "Root-cause conclusion remains high confidence despite an unresolved critical gap.",
                }
            )

    if insufficient_hypotheses(analysis) and confidence == "high" and level in ("mechanism", "root_cause"):
        findings.append(
            {
                "code": "overconfident_conclusion",
                "severity": "must_fix",
                "message": "Conclusion is high confidence at mechanism/root-cause level while one or more hypotheses remain insufficient.",
            }
        )

    if (has_critical_gap(analysis) or insufficient_hypotheses(analysis)) and not has_next_actions(analysis):
        findings.append(
            {
                "code": "missing_next_action",
                "severity": "should_fix",
                "message": "Evidence is insufficient but analysis does not provide read-only next actions.",
            }
        )

    return findings


def apply_process_findings_to_score(score: Dict[str, Dict[str, str]], findings: List[Dict[str, str]]) -> None:
    impact = {
        "answer_led_bias": ("hypothesis_coverage", "validation_depth"),
        "surface_to_root_cause_jump": ("validation_depth", "conclusion_confidence"),
        "missing_evidence_bridge": ("evidence_completeness", "validation_depth"),
        "critical_gap_ignored": ("validation_depth", "conclusion_confidence"),
        "overconfident_conclusion": ("conclusion_confidence",),
        "missing_next_action": ("knowledge_reusability", "validation_depth"),
    }
    for finding in findings:
        code = str(finding.get("code") or "")
        severity = str(finding.get("severity") or "")
        target_level = "low" if severity == "must_fix" else "medium"
        for dimension in impact.get(code, ()):
            item = score.get(dimension)
            if not item:
                continue
            item["level"] = downgrade_level(str(item.get("level") or "low"), target_level)
            append_reason(item, "Process finding %s: %s" % (code, finding.get("message") or "review required."))


def review_score_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    conclusion = analysis.get("conclusion_summary") or {}
    hypotheses = [item for item in analysis.get("hypotheses") or [] if isinstance(item, dict)]
    knowledge_candidates = [item for item in analysis.get("knowledge_candidates") or [] if isinstance(item, dict)]
    conclusion_evidence = conclusion.get("evidence") or []
    supported = [item for item in hypotheses if item.get("status") == "supported" or item.get("validation_result") == "supported"]
    refuted = [item for item in hypotheses if item.get("status") == "refuted" or item.get("validation_result") == "refuted"]
    validation_actions = []
    for item in hypotheses:
        for action in item.get("validation_actions") or []:
            validation_actions.append(action)

    if conclusion_evidence:
        evidence_score = score_item("high", "Conclusion includes explicit evidence.")
    elif supported:
        evidence_score = score_item("medium", "Hypotheses include supported results, but conclusion evidence is thin.")
    else:
        evidence_score = score_item("low", "No explicit conclusion evidence or supported hypothesis found.")

    if len(hypotheses) >= 2 and supported:
        hypothesis_score = score_item("high", "Analysis includes multiple hypotheses and at least one supported path.")
    elif hypotheses:
        hypothesis_score = score_item("medium", "Analysis includes hypotheses, but coverage is limited.")
    else:
        hypothesis_score = score_item("low", "No hypotheses generated.")

    if validation_actions:
        validation_score = score_item("high", "Analysis includes explicit validation actions.")
    elif supported or refuted:
        validation_score = score_item("medium", "Hypotheses have validation results, but no additional validation actions were executed.")
    else:
        validation_score = score_item("low", "No validation actions or decisive validation results.")

    confidence_score = score_item(
        level_from_confidence(str(conclusion.get("confidence") or "low")),
        "Derived from conclusion_summary.confidence.",
    )

    if knowledge_candidates:
        knowledge_score = score_item("high", "Analysis produced reusable knowledge candidates.")
    elif conclusion.get("primary_cause_category") == "baseline":
        knowledge_score = score_item("medium", "Baseline case is reusable for regression, not production knowledge.")
    else:
        knowledge_score = score_item("low", "No knowledge candidates generated.")

    score = {
        "evidence_completeness": evidence_score,
        "hypothesis_coverage": hypothesis_score,
        "validation_depth": validation_score,
        "conclusion_confidence": confidence_score,
        "knowledge_reusability": knowledge_score,
    }
    apply_process_findings_to_score(score, review_process_findings(analysis))
    return score


def review_suggestions(score: Dict[str, Dict[str, str]], analysis: Dict[str, Any], findings: List[Dict[str, str]] = None) -> List[str]:
    conclusion = analysis.get("conclusion_summary") or {}
    is_baseline = conclusion.get("primary_cause_category") == "baseline"
    suggestions: List[str] = []
    if score["evidence_completeness"]["level"] != "high":
        suggestions.append("Add stronger evidence extraction or evidence-to-conclusion linking.")
    if score["hypothesis_coverage"]["level"] != "high" and not is_baseline:
        suggestions.append("Add scenario-specific hypothesis rules or counter-hypotheses.")
    if score["validation_depth"]["level"] != "high":
        suggestions.append("Add explicit validation actions for supported and refuted hypotheses.")
    if score["knowledge_reusability"]["level"] != "high" and not is_baseline:
        suggestions.append("Improve knowledge candidate generation from matching assets and incident evidence.")
    for finding in findings or []:
        code = str(finding.get("code") or "")
        if code == "answer_led_bias":
            suggestions.append("Separate current incident evidence from user clues, historical answers, and runbook-derived hypotheses.")
        elif code == "critical_gap_ignored":
            suggestions.append("Add a read-only validation action or next action for each unresolved critical_gap.")
        elif code == "overconfident_conclusion":
            suggestions.append("Lower conclusion confidence or conclusion depth until the relevant critical gaps are closed.")
        elif code == "missing_evidence_bridge":
            suggestions.append("Add the evidence bridge from observed signals to the claimed mechanism or root cause.")
        elif code == "surface_to_root_cause_jump":
            suggestions.append("Keep root-cause claims as hypotheses until direct process-internal or application-log evidence supports them.")
        elif code == "missing_next_action":
            suggestions.append("Add the highest-value read-only next action for insufficient hypotheses or unresolved critical gaps.")
    return suggestions


def review_regression_risks(findings: List[Dict[str, str]]) -> List[str]:
    risks: List[str] = []
    for finding in findings:
        if finding.get("severity") == "must_fix":
            risks.append("%s: %s" % (finding.get("code"), finding.get("message")))
    return risks


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
    findings = review_process_findings(analysis)
    score = review_score_from_analysis(analysis)
    level = overall_level(score)
    analysis["review"] = {
        "score": score,
        "overall": {"level": level, "reason": "Average of local review score dimensions."},
        "improvement_suggestions": review_suggestions(score, analysis, findings),
        "regression_risks": review_regression_risks(findings),
        "generated_at": now_iso(),
    }
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
