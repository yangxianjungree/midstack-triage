"""Structured deep-analysis request helpers for Phase 4."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


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
