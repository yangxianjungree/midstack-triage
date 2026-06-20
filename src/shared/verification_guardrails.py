"""Guardrails for Phase 4 verification requests."""

from __future__ import annotations

from typing import Any, Dict, List


READONLY_ARGV_PREFIXES = (
    ("kubectl", "get"),
    ("kubectl", "describe"),
    ("kubectl", "logs"),
    ("kubectl", "top"),
    ("mongosh",),
    ("mongo",),
)


def ad_hoc_readonly_command_request(
    request_id: str,
    hypothesis_id: str,
    purpose: str,
    argv: List[str],
    expected_evidence: List[str],
    reason: str,
) -> Dict[str, Any]:
    return {
        "request_id": request_id,
        "hypothesis_id": hypothesis_id,
        "purpose": purpose,
        "asset_tier": "ad_hoc_readonly",
        "asset": {
            "type": "ad_hoc_command",
            "id": request_id,
            "argv": list(argv),
        },
        "risk_level": "read-only",
        "execution_policy": "approval_required",
        "expected_evidence": list(expected_evidence),
        "reason": reason,
        "status": "planned",
    }


def apply_verification_request_guardrails(analysis: Dict[str, Any]) -> bool:
    changed = False
    requests = analysis.get("verification_requests")
    if not isinstance(requests, list):
        return False
    for item in requests:
        if not isinstance(item, dict):
            continue
        if _guard_verification_request(item):
            changed = True
    return changed


def _guard_verification_request(item: Dict[str, Any]) -> bool:
    asset_tier = str(item.get("asset_tier") or "")
    asset = item.get("asset") if isinstance(item.get("asset"), dict) else {}
    asset_type = str((asset or {}).get("type") or "")
    if asset_tier == "ad_hoc_readonly" or asset_type == "ad_hoc_command":
        return _guard_ad_hoc_readonly_request(item, asset or {})
    if str(item.get("risk_level") or "") == "destructive" or str(item.get("execution_policy") or "") == "blocked":
        return _mark_blocked(item, "verification request is blocked by policy")
    return False


def _guard_ad_hoc_readonly_request(item: Dict[str, Any], asset: Dict[str, Any]) -> bool:
    changed = False
    argv = asset.get("argv")
    if not _is_string_list(argv) or not _argv_has_readonly_prefix(argv):
        changed = _mark_blocked(item, "ad hoc command must be structured argv with an allowed read-only prefix") or changed
    else:
        if item.get("asset_tier") != "ad_hoc_readonly":
            item["asset_tier"] = "ad_hoc_readonly"
            changed = True
        if item.get("risk_level") != "read-only":
            item["risk_level"] = "read-only"
            changed = True
        if item.get("execution_policy") != "approval_required":
            item["execution_policy"] = "approval_required"
            changed = True
        if item.get("status") != "planned":
            item["status"] = "planned"
            changed = True
    return changed


def _mark_blocked(item: Dict[str, Any], reason: str) -> bool:
    changed = False
    for key, value in (
        ("asset_tier", "blocked"),
        ("risk_level", "destructive"),
        ("execution_policy", "blocked"),
        ("status", "blocked"),
    ):
        if item.get(key) != value:
            item[key] = value
            changed = True
    if item.get("guardrail_reason") != reason:
        item["guardrail_reason"] = reason
        changed = True
    return changed


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) and item for item in value)


def _argv_has_readonly_prefix(argv: List[str]) -> bool:
    normalized = tuple(item.strip().lower() for item in argv if item.strip())
    for prefix in READONLY_ARGV_PREFIXES:
        if normalized[: len(prefix)] == prefix:
            return True
    return False
