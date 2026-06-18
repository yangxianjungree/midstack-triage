#!/usr/bin/env python3

import re
from pathlib import Path
from typing import Any, Dict, List


MIDDLEWARE = "mongodb"
SCRIPT_ID_RE = re.compile(r"^mongodb\.(collect|normalize)\.[a-z0-9_]+\.[a-z0-9_]+$")
VALID_RUNTIMES = {"shell", "python"}
REQUIRED_MANIFEST_FIELDS = {
    "script_id",
    "source",
    "phase",
    "target",
    "action",
    "runtime",
    "readonly",
    "default_packaged",
    "mvp",
}
REQUIRED_RUNTIME_FIELDS = {
    "script_id",
    "runtime_path",
    "runtime",
    "readonly",
}
REQUIRED_RUNTIME_MAP_FIELDS = {
    "plugin",
    "version",
    "generated_at",
    "scripts",
}
REQUIRED_REMOTE_REQUEST_FIELDS = {
    "executor_id",
    "incident_id",
    "script_id",
    "middleware",
    "plugin_name",
    "access",
    "script",
    "remote_workspace",
    "required_capabilities",
    "execution",
}
REQUIRED_REMOTE_RESULT_FIELDS = {
    "executor_id",
    "incident_id",
    "script_id",
    "plugin_name",
    "status",
    "selected_ip",
    "started_at",
    "finished_at",
    "capability_checks",
    "remote_paths",
    "retrieved_files",
    "process",
    "error",
    "warnings",
}
REQUIRED_CONTEXT_FIELDS = {
    "incident_id",
    "middleware",
    "script_id",
    "namespace",
    "cluster_id",
    "artifact_root",
}
REQUIRED_OUTPUT_FIELDS = {
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
}
VALID_SCRIPT_STATUS = {"success", "partial", "blocked"}
VALID_EXECUTOR_STATUS = {"success", "partial", "blocked", "failed"}
VALID_RISK_LEVELS = {"read-only", "low-risk", "high-risk"}
VALID_ADAPTER_COMMANDS = {"start", "analyse", "review"}
VALID_ADAPTER_STATUS = {"ready", "blocked", "completed", "failed"}
REQUIRED_RUNBOOK_FIELDS = {
    "id",
    "title",
    "middleware",
    "component",
    "scenario",
    "summary",
    "risk_level",
    "tags",
    "required_tools",
    "applicable_env",
    "verification_steps",
    "rollback_or_safety_notes",
}
REQUIRED_COMMAND_FIELDS = {
    "id",
    "title",
    "middleware",
    "component",
    "scenario",
    "risk_level",
    "tags",
    "required_tools",
    "expected_signal",
}
REQUIRED_SKILL_FIELDS = {
    "id",
    "version",
    "status",
    "title",
    "middleware",
    "component",
    "primary_scenario",
    "inputs",
    "outputs",
    "required_assets",
    "safety_constraints",
}
REQUIRED_ADAPTER_OUTPUT_FIELDS = {
    "plugin_name",
    "command",
    "incident_id",
    "middleware",
    "status",
    "summary",
    "user_message",
    "record_refs",
    "next_actions",
    "blocking_items",
    "warnings",
    "generated_at",
}
REQUIRED_SCENARIO_FIELDS = {
    "id",
    "title",
    "summary",
    "tags",
    "symptoms",
    "applicable_middleware",
    "diagnostic_goals",
    "route_hints",
}
REQUIRED_FIXTURE_FILES = {
    "input.yaml",
    "structured_record.yaml",
    "signal_bundle.yaml",
    "collection_report.yaml",
    "expected_analysis.yaml",
}


def fail(errors: List[str], message: str) -> None:
    errors.append(message)


def require_list_of_strings(data: Dict[str, Any], field: str, path: Path, errors: List[str]) -> None:
    value = data.get(field)
    if not isinstance(value, list):
        fail(errors, "%s %s must be a list" % (path, field))
        return
    for index, item in enumerate(value):
        if not isinstance(item, str):
            fail(errors, "%s %s[%d] must be a string" % (path, field, index))
