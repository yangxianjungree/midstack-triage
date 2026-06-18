"""Script output.yaml contract validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from execution.remote.runtime_support import load_config

LoadConfigFn = Callable[[Path], Dict[str, Any]]

SCRIPT_OUTPUT_REQUIRED_FIELDS = (
    "script_id",
    "status",
    "summary",
    "started_at",
    "finished_at",
    "artifacts",
    "structured_record_patch",
    "signal_bundle_patch",
    "collection_report_patch",
    "warnings",
    "evidence_gaps",
)
SCRIPT_OUTPUT_ALLOWED_STATUSES = {"success", "partial", "blocked"}


def validate_script_output_contract(
    output_path: Path,
    expected_script_id: str,
    load_config_fn: LoadConfigFn = load_config,
) -> Tuple[bool, Dict[str, Any], str]:
    try:
        data = load_config_fn(output_path)
    except Exception as exc:
        return False, {}, "output.yaml is not valid YAML: %s" % exc
    if not isinstance(data, dict) or not data:
        return False, {}, "output.yaml must contain a YAML object"

    missing = [field for field in SCRIPT_OUTPUT_REQUIRED_FIELDS if field not in data]
    if missing:
        return False, data, "output.yaml is missing required fields: %s" % ", ".join(missing)

    actual_script_id = str(data.get("script_id") or "")
    if actual_script_id != expected_script_id:
        return False, data, "output.yaml script_id mismatch: expected %s, got %s" % (expected_script_id, actual_script_id or "missing")

    status = str(data.get("status") or "")
    if status not in SCRIPT_OUTPUT_ALLOWED_STATUSES:
        return False, data, "output.yaml status must be one of %s, got %s" % (sorted(SCRIPT_OUTPUT_ALLOWED_STATUSES), status or "missing")

    if not isinstance(data.get("artifacts"), list):
        return False, data, "output.yaml artifacts must be a list"
    if not isinstance(data.get("warnings"), list):
        return False, data, "output.yaml warnings must be a list"
    if not isinstance(data.get("evidence_gaps"), list):
        return False, data, "output.yaml evidence_gaps must be a list"
    for patch_key in ("structured_record_patch", "signal_bundle_patch", "collection_report_patch"):
        if not isinstance(data.get(patch_key), dict):
            return False, data, "output.yaml %s must be an object" % patch_key
    for item in data.get("artifacts") or []:
        if not isinstance(item, dict):
            return False, data, "output.yaml artifacts entries must be objects"
        artifact_path = str(item.get("path") or "")
        if not artifact_path:
            return False, data, "output.yaml artifacts entries must include path"
        if artifact_path.startswith("/") or any(part == ".." for part in artifact_path.split("/")):
            return False, data, "output.yaml artifact paths must stay relative to artifact-dir: %s" % artifact_path
    return True, data, ""
