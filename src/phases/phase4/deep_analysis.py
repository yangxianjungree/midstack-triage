"""Structured deep-analysis request helpers for Phase 4."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


DEEP_ANALYSIS_SCHEMA_VERSION = "deep-analysis.v1"


def deep_analysis_request(
    request_id: str,
    capability: str,
    purpose: str,
    inputs: Iterable[str],
    expected_output: Iterable[str],
    hypothesis_ids: Iterable[str] = (),
    trigger_findings: Iterable[str] = (),
    guidance: str = "",
) -> Dict[str, Any]:
    request = {
        "request_id": request_id,
        "capability": capability,
        "purpose": purpose,
        "scope": "current_incident",
        "risk_level": "read-only",
        "execution_boundary": "plan_only",
        "status": "planned",
        "inputs": list(inputs),
        "expected_output": list(expected_output),
    }
    hypothesis_id_list = [str(item) for item in hypothesis_ids if str(item).strip()]
    finding_id_list = [str(item) for item in trigger_findings if str(item).strip()]
    if hypothesis_id_list:
        request["hypothesis_ids"] = hypothesis_id_list
    if finding_id_list:
        request["trigger_findings"] = finding_id_list
    if guidance:
        request["guidance"] = guidance
    return request


def dedupe_deep_analysis_requests(requests: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for request in requests:
        request_id = str(request.get("request_id") or "").strip()
        capability = str(request.get("capability") or "").strip()
        key = (request_id, capability)
        if key in seen:
            continue
        seen.add(key)
        result.append(request)
    return result


def materialize_deep_analysis(
    analysis: Dict[str, Any],
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    requests = [item for item in analysis.get("deep_analysis_requests") or [] if isinstance(item, dict)]
    results = [_materialize_request(item, analysis, structured_record, signal_bundle) for item in requests]
    completed = [item for item in results if item.get("status") == "completed"]
    return {
        "schema_version": DEEP_ANALYSIS_SCHEMA_VERSION,
        "execution_boundary": "read_only_materialization",
        "summary": {
            "total_requests": len(results),
            "completed_requests": len(completed),
            "capabilities": _unique(item.get("capability") for item in results),
        },
        "results": results,
    }


def deep_analysis_summary(deep_analysis: Dict[str, Any]) -> Dict[str, Any]:
    results = [item for item in deep_analysis.get("results") or [] if isinstance(item, dict)]
    return {
        "artifact": "deep-analysis.yaml",
        "summary": dict(deep_analysis.get("summary") or {}),
        "highlights": [_highlight_for_result(item) for item in results[:6]],
    }


def _highlight_for_result(item: Dict[str, Any]) -> Dict[str, Any]:
    highlight: Dict[str, Any] = {
        "request_id": str(item.get("request_id") or ""),
        "capability": str(item.get("capability") or ""),
        "status": str(item.get("status") or ""),
        "summary": str(item.get("summary") or ""),
    }
    output = item.get("output") if isinstance(item.get("output"), dict) else {}
    baseline_diff = output.get("baseline_diff") if isinstance(output.get("baseline_diff"), dict) else {}
    replica_sets = [rs for rs in baseline_diff.get("replica_sets") or [] if isinstance(rs, dict)]
    violations = _unique(violation for rs in replica_sets for violation in rs.get("violations") or [])
    if violations:
        highlight["violations"] = violations
    replica_set_ids = _unique(rs.get("replica_set_id") for rs in replica_sets)
    if replica_set_ids:
        highlight["replica_sets"] = replica_set_ids

    trace = [entry for entry in output.get("evidence_path_trace") or [] if isinstance(entry, dict)]
    supports = _unique(value for entry in trace for value in entry.get("supports") or [])
    refutes = _unique(value for entry in trace for value in entry.get("refutes") or [])
    if supports:
        highlight["supports"] = supports
    if refutes:
        highlight["refutes"] = refutes
    missing_edges = [edge for edge in output.get("missing_path_edges") or [] if isinstance(edge, dict)]
    if missing_edges:
        highlight["missing_path_edges"] = [
            {
                "request_id": str(edge.get("request_id") or ""),
                "purpose": str(edge.get("purpose") or ""),
                "status": str(edge.get("status") or ""),
            }
            for edge in missing_edges[:4]
        ]
    return highlight


def _materialize_request(
    request: Dict[str, Any],
    analysis: Dict[str, Any],
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    capability = str(request.get("capability") or "").strip()
    output = _output_for_capability(capability, analysis, structured_record, signal_bundle)
    return {
        "request_id": str(request.get("request_id") or ""),
        "capability": capability,
        "status": "completed",
        "risk_level": "read-only",
        "execution_boundary": "read_only_materialization",
        "summary": _summary_for_output(capability, output),
        "output": output,
    }


def _output_for_capability(
    capability: str,
    analysis: Dict[str, Any],
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    if capability == "baseline_scan":
        return {"baseline_diff": _replica_set_baseline_diff(structured_record)}
    if capability == "code_logic_analysis":
        return {
            "decision_rule_mapping": [
                "A MongoDB replica-set PRIMARY view depends on each member's local replica-set config, term, voting members, and heartbeat reachability.",
                "Two PRIMARY reports with divergent config_version/member/quorum views support a split-brain mechanism, but not a single enabling cause.",
                "Current TCP success weakens an ongoing network partition and shifts validation toward historical heartbeat/election/reconfig evidence.",
            ],
            "candidate_enabling_conditions": _candidate_enabling_conditions(analysis),
            "required_disconfirming_evidence": [
                "All affected members return identical rs.conf version, term, members, votes, priorities, and settings.",
                "Heartbeat/election/reconfig logs show no relevant timeout, stepdown, reconfig, auth, or process-layer event around the incident window.",
            ],
        }
    if capability == "code_path_tracing":
        return {
            "evidence_path_trace": _evidence_path_trace(analysis, structured_record, signal_bundle),
            "missing_path_edges": _missing_path_edges(analysis),
            "counter_evidence_by_hypothesis": _counter_evidence_by_hypothesis(analysis),
        }
    if capability == "repro_script_generation":
        return {
            "read_only_repro_plan": [
                "Build a synthetic fixture from input.yaml, structured_record.yaml, signal_bundle.yaml, collection_report.yaml, and analysis.yaml.",
                "Replay Phase 4 rules against the fixture and assert split-brain mechanism, enabling-cause hypotheses, verification_requests, and deep_analysis_results.",
                "Keep live-cluster mutation steps blocked; do not run rs.reconfig, pod restarts, deletes, writes, or repair commands.",
            ],
            "synthetic_fixture_requirements": [
                "At least two replica member views with divergent PRIMARY/config/member/quorum data.",
                "Optional current TCP/27017 success evidence to weaken sustained network partition.",
                "Expected critical gaps for rs.conf comparison and heartbeat/election/reconfig logs.",
            ],
            "blocked_mutation_steps": ["rs.reconfig", "kubectl delete", "kubectl rollout restart", "write workload data"],
        }
    return {"notes": ["No materializer exists for capability `%s`." % capability]}


def _replica_set_baseline_diff(structured_record: Dict[str, Any]) -> Dict[str, Any]:
    records = _replica_member_records(structured_record)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        replica_set_id = str(record.get("replica_set_id") or "unknown")
        groups.setdefault(replica_set_id, []).append(record)

    replica_sets = []
    for replica_set_id, items in groups.items():
        primary_views = [
            str(item.get("source_pod_ref") or "")
            for item in items
            if str((item.get("self_member") or {}).get("state_str") or "").upper() == "PRIMARY"
        ]
        config_views = sorted(
            {
                "%s/%s" % ((item.get("self_member") or {}).get("config_version"), (item.get("self_member") or {}).get("config_term"))
                for item in items
            }
        )
        member_views = sorted({_member_view_key(item) for item in items})
        quorum_counts = sorted({str(item.get("voting_members_count")) for item in items if item.get("voting_members_count") is not None})
        violations = []
        if len(primary_views) > 1:
            violations.append("multiple_primary_views")
        if len(config_views) > 1:
            violations.append("config_view_divergence")
        if len(member_views) > 1:
            violations.append("member_view_divergence")
        if len(quorum_counts) > 1:
            violations.append("quorum_view_divergence")
        replica_sets.append(
            {
                "replica_set_id": replica_set_id,
                "member_observations": len(items),
                "primary_views": primary_views,
                "config_views": config_views,
                "member_views": member_views,
                "voting_quorum_counts": quorum_counts,
                "violations": violations,
            }
        )
    return {
        "replica_set_count": len(replica_sets),
        "healthy_expectations": [
            "single PRIMARY view per replica set",
            "consistent config_version/config_term view",
            "consistent member list and voting quorum view",
        ],
        "replica_sets": replica_sets,
    }


def _candidate_enabling_conditions(analysis: Dict[str, Any]) -> List[str]:
    candidates = []
    for item in analysis.get("deepening_findings") or []:
        if not isinstance(item, dict):
            continue
        for value in item.get("supports") or []:
            text = str(value or "").strip()
            if text and text not in candidates:
                candidates.append(text)
    return candidates


def _evidence_path_trace(
    analysis: Dict[str, Any],
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
) -> List[Dict[str, Any]]:
    trace = []
    if _replica_member_records(structured_record):
        trace.append(
            {
                "source": "structured_record.details.replica_members",
                "meaning": "multi-member rs.status observations are available",
                "supports": ["split_brain_mechanism", "replica_set_view_divergence"],
            }
        )
    if signal_bundle.get("log_highlights"):
        trace.append(
            {
                "source": "signal_bundle.log_highlights",
                "meaning": "log highlights may constrain historical heartbeat, election, DNS, startup, or reconfig timing",
                "supports": ["timeline_correlation"],
            }
        )
    for item in analysis.get("deepening_findings") or []:
        if not isinstance(item, dict):
            continue
        trace.append(
            {
                "source": "analysis.deepening_findings.%s" % str(item.get("finding_id") or "finding"),
                "meaning": str(item.get("statement") or ""),
                "supports": list(item.get("supports") or []),
                "refutes": list(item.get("refutes") or []),
            }
        )
    return trace


def _missing_path_edges(analysis: Dict[str, Any]) -> List[Dict[str, str]]:
    missing = []
    for item in analysis.get("verification_requests") or []:
        if not isinstance(item, dict):
            continue
        missing.append(
            {
                "request_id": str(item.get("request_id") or ""),
                "purpose": str(item.get("purpose") or ""),
                "status": str(item.get("status") or ""),
            }
        )
    return missing


def _counter_evidence_by_hypothesis(analysis: Dict[str, Any]) -> Dict[str, List[Any]]:
    result: Dict[str, List[Any]] = {}
    for item in analysis.get("hypotheses") or []:
        if not isinstance(item, dict):
            continue
        hypothesis_id = str(item.get("hypothesis_id") or "")
        if hypothesis_id:
            result[hypothesis_id] = list(item.get("counter_evidence") or [])
    return result


def _summary_for_output(capability: str, output: Dict[str, Any]) -> str:
    if capability == "baseline_scan":
        replica_sets = (output.get("baseline_diff") or {}).get("replica_sets") or []
        violations = sorted({violation for item in replica_sets for violation in item.get("violations") or []})
        if violations:
            return "Detected baseline invariant violations: %s." % ", ".join(violations)
        return "No baseline invariant violations detected."
    if capability == "code_logic_analysis":
        return "Mapped replica-set decision logic to candidate enabling conditions."
    if capability == "code_path_tracing":
        missing = output.get("missing_path_edges") or []
        return "Traced evidence path with %d missing validation edge(s)." % len(missing)
    if capability == "repro_script_generation":
        return "Generated a read-only repro or fixture plan; live mutation remains blocked."
    return "Materialized deep analysis output."


def _replica_member_records(structured_record: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = structured_record.get("details") if isinstance(structured_record, dict) else {}
    return [item for item in (details or {}).get("replica_members") or [] if isinstance(item, dict)]


def _member_view_key(record: Dict[str, Any]) -> str:
    names = sorted(str(item.get("name") or "") for item in record.get("members") or [] if isinstance(item, dict))
    return "|".join(names)


def _unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
