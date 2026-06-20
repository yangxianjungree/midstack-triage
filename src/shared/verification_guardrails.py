"""Guardrails for Phase 4 verification requests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


READONLY_ARGV_PREFIXES = (
    ("kubectl", "get"),
    ("kubectl", "describe"),
    ("kubectl", "logs"),
    ("kubectl", "top"),
    ("mongosh",),
    ("mongo",),
)

BLOCKED_KUBECTL_SUBCOMMANDS = {
    "annotate",
    "apply",
    "attach",
    "autoscale",
    "cordon",
    "cp",
    "create",
    "debug",
    "delete",
    "drain",
    "edit",
    "exec",
    "label",
    "patch",
    "replace",
    "rollout",
    "scale",
    "set",
    "taint",
    "uncordon",
}

BLOCKED_MONGO_EVAL_TERMS = (
    "rs.reconfig",
    "replsetreconfig",
    ".drop(",
    ".dropdatabase(",
    ".dropindex(",
    ".createcollection(",
    ".createindex(",
    ".insertone(",
    ".insertmany(",
    ".updateone(",
    ".updatemany(",
    ".replaceone(",
    ".deleteone(",
    ".deletemany(",
    ".remove(",
    ".shutdownserver(",
    "shutdownserver",
)

SHELL_CONTROL_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<", "2>", "2>>"}


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
    if not _is_string_list(argv):
        changed = _mark_blocked(item, "ad hoc command must be structured argv with an allowed read-only prefix") or changed
    elif shell_reason := _argv_shell_control_reason(argv):
        changed = _mark_blocked(item, shell_reason) or changed
    elif mutation_reason := _argv_mutation_reason(argv):
        changed = _mark_blocked(item, mutation_reason) or changed
    elif not _argv_has_readonly_prefix(argv):
        changed = _mark_blocked(item, "ad hoc command must be structured argv with an allowed read-only prefix") or changed
    else:
        if asset.get("type") != "ad_hoc_command":
            asset["type"] = "ad_hoc_command"
            changed = True
        request_id = str(item.get("request_id") or "ad-hoc-command").strip() or "ad-hoc-command"
        if not asset.get("id"):
            asset["id"] = request_id
            changed = True
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


def _argv_shell_control_reason(argv: List[str]) -> Optional[str]:
    for item in argv:
        token = item.strip()
        if token in SHELL_CONTROL_TOKENS:
            return "shell control token `%s` is not allowed in ad hoc structured argv" % token
    return None


def _argv_mutation_reason(argv: List[str]) -> Optional[str]:
    normalized = [item.strip().lower() for item in argv if item.strip()]
    if not normalized:
        return None
    executable = normalized[0]
    if executable == "kubectl" and len(normalized) > 1 and normalized[1] in BLOCKED_KUBECTL_SUBCOMMANDS:
        return "kubectl %s is not allowed for ad hoc read-only verification" % normalized[1]
    if executable in {"mongo", "mongosh"}:
        text = " ".join(normalized)
        for term in BLOCKED_MONGO_EVAL_TERMS:
            if term in text:
                return "mongo shell mutation term `%s` is not allowed for ad hoc read-only verification" % term
    return None
