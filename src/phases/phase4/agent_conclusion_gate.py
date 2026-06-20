"""Conservative gate for promoting Agent reasoning to the formal conclusion."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


AGENT_CONCLUSION_GATE_SCHEMA_VERSION = "agent-conclusion-gate.v1"
MIN_AGENT_CONFIDENCE = 0.8
CURRENT_INCIDENT_EVIDENCE_PREFIXES = (
    "structured_record",
    "signal_bundle",
    "collection_report",
    "deepening_findings",
    "deep_analysis_results",
    "verification_requests",
)
HYPOTHESIS_ONLY_PREFIXES = (
    "experience_matches",
    "retrieval_context",
    "customer_clue",
    "historical_experience",
    "runbook",
    "knowledge_asset",
)
CONCLUSION_CANDIDATE_REQUIRED_FIELDS = (
    "statement",
    "confidence",
    "impact_scope",
    "primary_cause_category",
)
ALLOWED_CONCLUSION_CONFIDENCE = {"low", "medium", "high"}
ALLOWED_SUPPORTED_LEVELS = {"phenomenon", "impact", "mechanism", "root_cause"}


def evaluate_agent_conclusion_gate(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate whether an Agent draft is eligible to override the formal conclusion.

    The gate records eligibility only. It intentionally never mutates
    ``conclusion_summary`` or applies an override in this slice.
    """
    agent_reasoning = analysis.get("agent_reasoning") if isinstance(analysis, dict) else {}
    if not isinstance(agent_reasoning, dict):
        return _gate_result(None, [_blocker("missing_agent_reasoning", "no agent reasoning draft is recorded")])

    blockers: List[Dict[str, str]] = []
    runtime = agent_reasoning.get("runtime") if isinstance(agent_reasoning.get("runtime"), dict) else {}
    selected_type = str(runtime.get("selected_type") or "").strip()
    if selected_type != "claude":
        blockers.append(_blocker("agent_runtime_not_claude", "agent runtime is `%s`, not `claude`" % (selected_type or "unknown")))

    candidates = _ranked_candidates(agent_reasoning)
    candidate = _first_eligible_candidate(candidates, analysis, blockers)
    if not candidate:
        blockers.append(_blocker("missing_supported_candidate", "no supported agent hypothesis is available"))
        return _gate_result(None, blockers)

    blockers = blockers + _candidate_blockers(candidate, analysis)
    return _gate_result(candidate, blockers)


def _candidate_blockers(candidate: Dict[str, Any], analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    blockers: List[Dict[str, str]] = []
    if candidate["status"] != "supported":
        blockers.append(_blocker("candidate_not_supported", "selected agent candidate is not supported"))
    if candidate["confidence"] < MIN_AGENT_CONFIDENCE:
        blockers.append(
            _blocker(
                "candidate_confidence_below_threshold",
                "selected agent candidate confidence %.2f is below %.2f" % (candidate["confidence"], MIN_AGENT_CONFIDENCE),
            )
        )
    if not candidate["statement"]:
        blockers.append(_blocker("candidate_statement_empty", "selected agent candidate statement is empty"))
    evidence_refs = _candidate_evidence_refs(candidate)
    if _uses_hypothesis_only_refs(evidence_refs):
        blockers.append(_blocker("hypothesis_only_source_used_as_evidence", "agent candidate cites hypothesis-only sources as evidence"))
    if not _has_current_incident_evidence_ref(evidence_refs):
        blockers.append(_blocker("missing_current_evidence_refs", "agent candidate has no current-incident evidence references"))
    if _references_deep_analysis_results(evidence_refs) and not isinstance(analysis.get("deep_analysis_results"), dict):
        blockers.append(_blocker("deep_analysis_results_not_materialized", "agent candidate cites deep_analysis_results before they are materialized"))
    if _has_unresolved_critical_gap(analysis):
        blockers.append(_blocker("unresolved_critical_gap", "critical evidence gaps remain unresolved"))
    missing_candidate_fields = _missing_conclusion_candidate_fields(candidate["conclusion_summary"])
    if missing_candidate_fields:
        blockers.append(
            _blocker(
                "conclusion_candidate_incomplete",
                "agent conclusion candidate missing required field(s): %s" % ",".join(missing_candidate_fields),
            )
        )
    if candidate["conclusion_summary"] and not _as_list(candidate["conclusion_summary"].get("evidence")):
        blockers.append(_blocker("conclusion_candidate_missing_evidence", "agent conclusion candidate has no direct evidence refs"))
    invalid_candidate_fields = _invalid_conclusion_candidate_fields(candidate["conclusion_summary"])
    for code, message in invalid_candidate_fields:
        blockers.append(_blocker(code, message))
    return blockers


def apply_agent_conclusion_override(analysis: Dict[str, Any]) -> bool:
    gate = analysis.get("agent_conclusion_gate") if isinstance(analysis, dict) else {}
    if not isinstance(gate, dict) or gate.get("decision") != "eligible":
        return False
    candidate = gate.get("selected_candidate") if isinstance(gate.get("selected_candidate"), dict) else {}
    conclusion = candidate.get("conclusion_summary") if isinstance(candidate.get("conclusion_summary"), dict) else {}
    if _missing_conclusion_candidate_fields(conclusion):
        return False
    analysis["conclusion_summary"] = _copy_conclusion_summary(conclusion)
    gate["override_applied"] = True
    gate["override_reason"] = "eligible_agent_conclusion_candidate"
    return True


def _gate_result(candidate: Dict[str, Any] | None, blockers: List[Dict[str, str]]) -> Dict[str, Any]:
    decision = "eligible" if candidate and not blockers else "blocked"
    return {
        "schema_version": AGENT_CONCLUSION_GATE_SCHEMA_VERSION,
        "decision": decision,
        "override_applied": False,
        "selected_candidate": candidate or {},
        "blockers": blockers,
        "policy": {
            "min_confidence": MIN_AGENT_CONFIDENCE,
            "eligible_runtime": "claude",
            "requires_current_incident_evidence_refs": True,
            "blocks_on_unresolved_critical_gap": True,
        },
    }


def _blocker(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def _ranked_candidates(agent_reasoning: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = [_candidate_from_hypothesis(item) for item in _as_list(agent_reasoning.get("hypotheses")) if isinstance(item, dict)]
    candidates = [item for item in candidates if item["statement"] or item["status"] == "supported"]
    return sorted(candidates, key=lambda item: (item["status"] == "supported", item["confidence"], item["statement"]), reverse=True)


def _first_eligible_candidate(
    candidates: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    global_blockers: List[Dict[str, str]],
) -> Dict[str, Any] | None:
    if not candidates:
        return None
    if global_blockers:
        return candidates[0]
    for candidate in candidates:
        if not _candidate_blockers(candidate, analysis):
            return candidate
    return candidates[0]


def _candidate_from_hypothesis(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "hypothesis_id": str(item.get("id") or item.get("hypothesis_id") or "").strip(),
        "statement": str(item.get("statement") or "").strip(),
        "status": str(item.get("status") or "").strip(),
        "confidence": _confidence(item.get("confidence")),
        "evidence_refs": _evidence_refs(item),
        "conclusion_summary": _conclusion_candidate(item),
    }


def _confidence(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _evidence_refs(item: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    refs.extend(str(value).strip() for value in _as_list(item.get("evidence_refs")) if str(value).strip())
    for evidence in _as_list(item.get("supporting_evidence")):
        if isinstance(evidence, dict):
            source = str(evidence.get("source") or "").strip()
            if source:
                refs.append(source)
        elif str(evidence).strip():
            refs.append(str(evidence).strip())
    return _unique(refs)


def _conclusion_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    candidate = item.get("conclusion_candidate")
    if not isinstance(candidate, dict):
        return {}
    result: Dict[str, Any] = {}
    for key in (
        "statement",
        "confidence",
        "deepest_supported_level",
        "primary_cause_category",
        "impact_scope",
    ):
        value = candidate.get(key)
        if value is not None:
            result[key] = str(value).strip()
    for key in ("evidence", "limitations"):
        values = [value for value in _as_list(candidate.get(key))]
        if values:
            result[key] = values
    return result


def _candidate_evidence_refs(candidate: Dict[str, Any]) -> List[str]:
    refs = [str(value).strip() for value in _as_list(candidate.get("evidence_refs")) if str(value).strip()]
    conclusion = candidate.get("conclusion_summary")
    if isinstance(conclusion, dict):
        refs.extend(str(value).strip() for value in _as_list(conclusion.get("evidence")) if str(value).strip())
    return _unique(refs)


def _missing_conclusion_candidate_fields(candidate: Dict[str, Any]) -> List[str]:
    return [key for key in CONCLUSION_CANDIDATE_REQUIRED_FIELDS if not str(candidate.get(key) or "").strip()]


def _invalid_conclusion_candidate_fields(candidate: Dict[str, Any]) -> List[tuple[str, str]]:
    invalid: List[tuple[str, str]] = []
    confidence = str(candidate.get("confidence") or "").strip()
    if confidence and confidence not in ALLOWED_CONCLUSION_CONFIDENCE:
        invalid.append(
            (
                "conclusion_candidate_invalid_confidence",
                "agent conclusion candidate confidence `%s` is not one of low, medium, high" % confidence,
            )
        )
    level = str(candidate.get("deepest_supported_level") or "").strip()
    if level and level not in ALLOWED_SUPPORTED_LEVELS:
        invalid.append(
            (
                "conclusion_candidate_invalid_supported_level",
                "agent conclusion candidate deepest_supported_level `%s` is not a supported level" % level,
            )
        )
    return invalid


def _copy_conclusion_summary(conclusion: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(conclusion)
    result["evidence"] = [item for item in _as_list(conclusion.get("evidence"))]
    result["limitations"] = [item for item in _as_list(conclusion.get("limitations"))]
    return result


def _has_current_incident_evidence_ref(refs: Iterable[str]) -> bool:
    return any(_has_prefix(ref, CURRENT_INCIDENT_EVIDENCE_PREFIXES) for ref in refs)


def _uses_hypothesis_only_refs(refs: Iterable[str]) -> bool:
    return any(_has_prefix(ref, HYPOTHESIS_ONLY_PREFIXES) for ref in refs)


def _references_deep_analysis_results(refs: Iterable[str]) -> bool:
    return any(_has_prefix(ref, ("deep_analysis_results",)) for ref in refs)


def _has_prefix(value: str, prefixes: Iterable[str]) -> bool:
    normalized = str(value or "").strip()
    return any(normalized == prefix or normalized.startswith(prefix + ".") for prefix in prefixes)


def _has_unresolved_critical_gap(analysis: Dict[str, Any]) -> bool:
    conclusion = analysis.get("conclusion_summary") if isinstance(analysis.get("conclusion_summary"), dict) else {}
    for item in _as_list(conclusion.get("limitations")):
        if _is_unresolved_critical_gap(item):
            return True
    for hypothesis in _as_list(analysis.get("hypotheses")):
        if not isinstance(hypothesis, dict):
            continue
        for item in _as_list(hypothesis.get("evidence_gaps")):
            if _is_unresolved_critical_gap(item):
                return True
    return False


def _is_unresolved_critical_gap(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    gap_type = str(item.get("gap_type") or "").strip()
    status = str(item.get("status") or "open").strip()
    return gap_type == "critical_gap" and status not in ("closed", "resolved", "waived")


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _unique(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
