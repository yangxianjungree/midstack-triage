"""Helpers for Phase 4 hypothesis verification requests."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from shared.verification_guardrails import ad_hoc_readonly_command_request


def first_class_script_request(
    request_id: str,
    hypothesis_id: str,
    purpose: str,
    script_id: str,
    expected_evidence: Iterable[str],
    reason: str,
) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "hypothesis_id": hypothesis_id,
        "purpose": purpose,
        "asset_tier": "first_class",
        "asset": {
            "type": "script",
            "id": script_id,
        },
        "risk_level": "read-only",
        "execution_policy": "auto_allowed",
        "expected_evidence": list(expected_evidence),
        "reason": reason,
        "status": "planned",
    }


def dedupe_verification_requests(requests: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen = set()
    for request in requests:
        asset = request.get("asset") or {}
        key = (
            str(request.get("hypothesis_id") or ""),
            str(asset.get("type") or ""),
            str(asset.get("id") or ""),
            str(request.get("purpose") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(request)
    return result
