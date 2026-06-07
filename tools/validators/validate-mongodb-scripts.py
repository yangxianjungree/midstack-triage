#!/usr/bin/env python3

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
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


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


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


def taxonomy_ids(path: Path, errors: List[str]) -> set:
    data = load_yaml(path)
    values = data.get("values")
    if not isinstance(values, list) or not values:
        fail(errors, "%s values must be a non-empty list" % path)
        return set()
    ids = set()
    for index, item in enumerate(values):
        if not isinstance(item, dict):
            fail(errors, "%s values[%d] must be an object" % (path, index))
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            fail(errors, "%s values[%d].id must be a non-empty string" % (path, index))
            continue
        if item_id in ids:
            fail(errors, "%s duplicate taxonomy id: %s" % (path, item_id))
        ids.add(item_id)
    return ids


def load_taxonomies(taxonomy_dir: Path, errors: List[str]) -> Dict[str, set]:
    risk_levels = taxonomy_ids(taxonomy_dir / "risk-levels.yaml", errors)
    scenario_types = taxonomy_ids(taxonomy_dir / "scenario-types.yaml", errors)
    capability_types = taxonomy_ids(taxonomy_dir / "capability-types.yaml", errors)

    status_data = load_yaml(taxonomy_dir / "status-types.yaml")
    status_types: Dict[str, set] = {}
    for key in ("script_output_status", "remote_executor_status", "adapter_output_status", "review_score"):
        value = status_data.get(key)
        if not isinstance(value, list) or not value:
            fail(errors, "%s %s must be a non-empty list" % (taxonomy_dir / "status-types.yaml", key))
            status_types[key] = set()
            continue
        status_types[key] = set(value)
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item:
                fail(errors, "%s %s[%d] must be a non-empty string" % (taxonomy_dir / "status-types.yaml", key, index))

    tag_data = load_yaml(taxonomy_dir / "tag-guidelines.yaml")
    principles = tag_data.get("principles")
    if not isinstance(principles, list) or not principles:
        fail(errors, "%s principles must be a non-empty list" % (taxonomy_dir / "tag-guidelines.yaml"))

    return {
        "risk_levels": risk_levels or VALID_RISK_LEVELS,
        "scenario_types": scenario_types,
        "capability_types": capability_types,
        "script_output_status": status_types.get("script_output_status") or VALID_SCRIPT_STATUS,
        "remote_executor_status": status_types.get("remote_executor_status") or VALID_EXECUTOR_STATUS,
        "adapter_output_status": status_types.get("adapter_output_status") or VALID_ADAPTER_STATUS,
    }


def load_scenarios(scenarios_dir: Path, middleware: str, errors: List[str]) -> Dict[str, Dict[str, Any]]:
    scenarios: Dict[str, Dict[str, Any]] = {}
    for scenario_file in sorted(scenarios_dir.glob("*/scenario.yaml")):
        data = load_yaml(scenario_file)
        missing = REQUIRED_SCENARIO_FIELDS - set(data)
        if missing:
            fail(errors, "%s missing scenario fields: %s" % (scenario_file, ", ".join(sorted(missing))))
        scenario_id = data.get("id")
        expected_id = scenario_file.parent.name
        if scenario_id != expected_id:
            fail(errors, "%s id must match directory name %s" % (scenario_file, expected_id))
        if isinstance(scenario_id, str):
            if scenario_id in scenarios:
                fail(errors, "duplicate scenario id: %s" % scenario_id)
            scenarios[scenario_id] = data
        for field in ("tags", "symptoms", "applicable_middleware", "diagnostic_goals", "route_hints"):
            if field in data:
                require_list_of_strings(data, field, scenario_file, errors)
        applicable = data.get("applicable_middleware") or []
        if isinstance(applicable, list) and middleware not in applicable:
            fail(errors, "%s applicable_middleware must include %s" % (scenario_file, middleware))
    return scenarios


def validate_scenario_reference(metadata_path: Path, scenario_id: str, scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    if scenario_id not in scenarios:
        fail(errors, "%s scenario reference does not exist: scenarios/%s/scenario.yaml" % (metadata_path, scenario_id))


def validate_component_reference(metadata_path: Path, component: str, errors: List[str]) -> None:
    component_readme = ROOT / "domains" / "mongodb" / "components" / component / "README.md"
    if not component_readme.exists():
        fail(errors, "%s component reference does not exist: %s" % (metadata_path, component_readme))


def validate_manifest(manifest_path: Path, errors: List[str]) -> Dict[str, Dict[str, Any]]:
    data = load_yaml(manifest_path)
    if data.get("middleware") != "mongodb":
        fail(errors, "manifest.middleware must be mongodb")
    scripts = data.get("scripts") or []
    if not isinstance(scripts, list):
        fail(errors, "manifest.scripts must be a list")
        return {}

    by_id: Dict[str, Dict[str, Any]] = {}
    script_root = manifest_path.parent
    for index, item in enumerate(scripts):
        if not isinstance(item, dict):
            fail(errors, "manifest.scripts[%d] must be an object" % index)
            continue
        missing = REQUIRED_MANIFEST_FIELDS - set(item)
        if missing:
            fail(errors, "%s missing fields: %s" % (item.get("script_id", "scripts[%d]" % index), ", ".join(sorted(missing))))
        script_id = str(item.get("script_id") or "")
        if not SCRIPT_ID_RE.match(script_id):
            fail(errors, "invalid script_id: %s" % script_id)
        if script_id in by_id:
            fail(errors, "duplicate script_id: %s" % script_id)
        by_id[script_id] = item

        runtime = item.get("runtime")
        if runtime not in VALID_RUNTIMES:
            fail(errors, "%s runtime must be one of %s" % (script_id, sorted(VALID_RUNTIMES)))
        source = str(item.get("source") or "")
        if os.path.isabs(source):
            fail(errors, "%s source must be relative" % script_id)
        source_path = script_root / source
        if not source_path.exists():
            fail(errors, "%s source file does not exist: %s" % (script_id, source))
        if runtime == "shell" and not source.endswith(".sh"):
            fail(errors, "%s shell source should end with .sh" % script_id)
        if runtime == "python" and not source.endswith(".py"):
            fail(errors, "%s python source should end with .py" % script_id)
        expected_phase = script_id.split(".")[1] if len(script_id.split(".")) > 1 else ""
        if item.get("phase") != expected_phase:
            fail(errors, "%s phase does not match script_id" % script_id)

    mvp_count = sum(1 for item in by_id.values() if item.get("mvp") is True)
    if mvp_count != 10:
        fail(errors, "MongoDB MVP script count must be 10, got %d" % mvp_count)
    return by_id


def validate_runtime_map(runtime_map_path: Path, manifest_by_id: Dict[str, Dict[str, Any]], errors: List[str]) -> Dict[str, Dict[str, Any]]:
    data = load_yaml(runtime_map_path)
    missing = REQUIRED_RUNTIME_MAP_FIELDS - set(data)
    if missing:
        fail(errors, "runtime map missing fields: %s" % ", ".join(sorted(missing)))
    scripts = data.get("scripts") or []
    if not isinstance(scripts, list):
        fail(errors, "runtime map scripts must be a list")
        return {}

    runtime_by_id: Dict[str, Dict[str, Any]] = {}
    for index, item in enumerate(scripts):
        if not isinstance(item, dict):
            fail(errors, "runtime_map.scripts[%d] must be an object" % index)
            continue
        missing = REQUIRED_RUNTIME_FIELDS - set(item)
        if missing:
            fail(errors, "%s missing runtime fields: %s" % (item.get("script_id", "scripts[%d]" % index), ", ".join(sorted(missing))))
        script_id = str(item.get("script_id") or "")
        if script_id in runtime_by_id:
            fail(errors, "duplicate runtime map script_id: %s" % script_id)
        runtime_by_id[script_id] = item
        runtime_path = str(item.get("runtime_path") or "")
        if os.path.isabs(runtime_path):
            fail(errors, "%s runtime_path must be plugin-relative" % script_id)
        if not runtime_path.startswith("assets/scripts/mongodb/"):
            fail(errors, "%s runtime_path must start with assets/scripts/mongodb/" % script_id)

    packaged_ids = {script_id for script_id, item in manifest_by_id.items() if item.get("default_packaged") is True}
    runtime_ids = set(runtime_by_id)
    if packaged_ids != runtime_ids:
        fail(errors, "runtime map ids differ from default_packaged manifest ids: missing=%s extra=%s" % (sorted(packaged_ids - runtime_ids), sorted(runtime_ids - packaged_ids)))

    for script_id in sorted(packaged_ids & runtime_ids):
        manifest_item = manifest_by_id[script_id]
        runtime_item = runtime_by_id[script_id]
        if manifest_item.get("runtime") != runtime_item.get("runtime"):
            fail(errors, "%s runtime mismatch between manifest and runtime map" % script_id)
        if manifest_item.get("readonly") != runtime_item.get("readonly"):
            fail(errors, "%s readonly mismatch between manifest and runtime map" % script_id)
    return runtime_by_id


def validate_context_example(context_path: Path, manifest_by_id: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    data = load_yaml(context_path)
    missing = REQUIRED_CONTEXT_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing context fields: %s" % (context_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % context_path)
    script_id = str(data.get("script_id") or "")
    if script_id not in manifest_by_id:
        fail(errors, "%s script_id is not registered in manifest: %s" % (context_path, script_id))

    access = data.get("access")
    if access is not None:
        if not isinstance(access, dict):
            fail(errors, "%s access must be an object" % context_path)
        else:
            candidate_ips = access.get("candidate_ips")
            if candidate_ips is not None and not isinstance(candidate_ips, list):
                fail(errors, "%s access.candidate_ips must be a list" % context_path)
            port = access.get("port")
            if port is not None and not isinstance(port, int):
                fail(errors, "%s access.port must be an integer" % context_path)

    targets = data.get("targets")
    if targets is not None and not isinstance(targets, dict):
        fail(errors, "%s targets must be an object" % context_path)
    capabilities = data.get("capabilities")
    if capabilities is not None and not isinstance(capabilities, dict):
        fail(errors, "%s capabilities must be an object" % context_path)


def validate_output_example(output_path: Path, manifest_by_id: Dict[str, Dict[str, Any]], taxonomies: Dict[str, set], errors: List[str]) -> None:
    data = load_yaml(output_path)
    missing = REQUIRED_OUTPUT_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing output fields: %s" % (output_path, ", ".join(sorted(missing))))
    script_id = str(data.get("script_id") or "")
    if script_id not in manifest_by_id:
        fail(errors, "%s script_id is not registered in manifest: %s" % (output_path, script_id))
    status = data.get("status")
    valid_status = taxonomies["script_output_status"]
    if status not in valid_status:
        fail(errors, "%s status must be one of %s" % (output_path, sorted(valid_status)))
    for field in ("artifacts", "warnings", "evidence_gaps"):
        if field in data and not isinstance(data.get(field), list):
            fail(errors, "%s %s must be a list" % (output_path, field))
    for field in ("structured_record_patch", "signal_bundle_patch", "collection_report_patch"):
        if field in data and not isinstance(data.get(field), dict):
            fail(errors, "%s %s must be an object" % (output_path, field))


def validate_remote_request(
    request_path: Path,
    manifest_by_id: Dict[str, Dict[str, Any]],
    runtime_by_id: Dict[str, Dict[str, Any]],
    errors: List[str],
) -> None:
    data = load_yaml(request_path)
    missing = REQUIRED_REMOTE_REQUEST_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing remote request fields: %s" % (request_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % request_path)
    script_id = str(data.get("script_id") or "")
    if script_id not in manifest_by_id:
        fail(errors, "%s script_id is not registered in manifest: %s" % (request_path, script_id))

    plugin_name = str(data.get("plugin_name") or "")
    access = data.get("access")
    if not isinstance(access, dict):
        fail(errors, "%s access must be an object" % request_path)
    else:
        candidate_ips = access.get("candidate_ips")
        if not isinstance(candidate_ips, list) or not candidate_ips:
            fail(errors, "%s access.candidate_ips must be a non-empty list" % request_path)
        if not isinstance(access.get("primary_ip"), str) or not access.get("primary_ip"):
            fail(errors, "%s access.primary_ip must be a non-empty string" % request_path)
        if not isinstance(access.get("port"), int):
            fail(errors, "%s access.port must be an integer" % request_path)

    script = data.get("script")
    runtime_entry = runtime_by_id.get(script_id) or {}
    if not isinstance(script, dict):
        fail(errors, "%s script must be an object" % request_path)
    else:
        if script.get("runtime_path") != runtime_entry.get("runtime_path"):
            fail(errors, "%s script.runtime_path must match runtime map for %s" % (request_path, script_id))
        if script.get("runtime") != runtime_entry.get("runtime"):
            fail(errors, "%s script.runtime must match runtime map for %s" % (request_path, script_id))
        if script.get("readonly") != runtime_entry.get("readonly"):
            fail(errors, "%s script.readonly must match runtime map for %s" % (request_path, script_id))
        arguments = script.get("arguments")
        if not isinstance(arguments, dict):
            fail(errors, "%s script.arguments must be an object" % request_path)
        else:
            for field in ("context_file", "output_file", "artifact_dir"):
                if not arguments.get(field):
                    fail(errors, "%s script.arguments.%s is required" % (request_path, field))

    remote_workspace = data.get("remote_workspace")
    if not isinstance(remote_workspace, dict):
        fail(errors, "%s remote_workspace must be an object" % request_path)
    else:
        expected_prefix = "/tmp/%s" % plugin_name
        for field in ("plugin_root", "script_root", "run_root", "script_path", "context_file", "output_file", "artifact_dir"):
            value = remote_workspace.get(field)
            if not isinstance(value, str) or not value:
                fail(errors, "%s remote_workspace.%s must be a non-empty string" % (request_path, field))
            elif plugin_name and not value.startswith(expected_prefix):
                fail(errors, "%s remote_workspace.%s must start with %s" % (request_path, field, expected_prefix))


def validate_remote_result(result_path: Path, manifest_by_id: Dict[str, Dict[str, Any]], taxonomies: Dict[str, set], errors: List[str]) -> None:
    data = load_yaml(result_path)
    missing = REQUIRED_REMOTE_RESULT_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing remote result fields: %s" % (result_path, ", ".join(sorted(missing))))
    script_id = str(data.get("script_id") or "")
    if script_id not in manifest_by_id:
        fail(errors, "%s script_id is not registered in manifest: %s" % (result_path, script_id))
    valid_status = taxonomies["remote_executor_status"]
    if data.get("status") not in valid_status:
        fail(errors, "%s status must be one of %s" % (result_path, sorted(valid_status)))
    if not isinstance(data.get("capability_checks"), list):
        fail(errors, "%s capability_checks must be a list" % result_path)
    for field in ("remote_paths", "retrieved_files", "process", "error"):
        if not isinstance(data.get(field), dict):
            fail(errors, "%s %s must be an object" % (result_path, field))
    process = data.get("process")
    if isinstance(process, dict) and not isinstance(process.get("exit_code"), int):
        fail(errors, "%s process.exit_code must be an integer" % result_path)
    if not isinstance(data.get("warnings"), list):
        fail(errors, "%s warnings must be a list" % result_path)


def validate_runbook_metadata(metadata_path: Path, taxonomies: Dict[str, set], scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    data = load_yaml(metadata_path)
    missing = REQUIRED_RUNBOOK_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing runbook metadata fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % metadata_path)
    validate_component_reference(metadata_path, str(data.get("component") or ""), errors)
    risk_levels = taxonomies["risk_levels"]
    if data.get("risk_level") not in risk_levels:
        fail(errors, "%s risk_level must be one of %s" % (metadata_path, sorted(risk_levels)))
    scenario_types = taxonomies["scenario_types"]
    if scenario_types and data.get("scenario") not in scenario_types:
        fail(errors, "%s scenario must be one of %s" % (metadata_path, sorted(scenario_types)))
    validate_scenario_reference(metadata_path, str(data.get("scenario") or ""), scenarios, errors)
    for field in ("tags", "required_tools", "applicable_env", "verification_steps", "rollback_or_safety_notes"):
        if field in data:
            require_list_of_strings(data, field, metadata_path, errors)
    runbook_path = metadata_path.with_name("runbook.md")
    if not runbook_path.exists():
        fail(errors, "%s companion runbook.md does not exist" % metadata_path)


def validate_command_metadata(metadata_path: Path, taxonomies: Dict[str, set], scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    data = load_yaml(metadata_path)
    missing = REQUIRED_COMMAND_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing command metadata fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % metadata_path)
    validate_component_reference(metadata_path, str(data.get("component") or ""), errors)
    risk_levels = taxonomies["risk_levels"]
    if data.get("risk_level") not in risk_levels:
        fail(errors, "%s risk_level must be one of %s" % (metadata_path, sorted(risk_levels)))
    scenario_types = taxonomies["scenario_types"]
    if scenario_types and data.get("scenario") not in scenario_types:
        fail(errors, "%s scenario must be one of %s" % (metadata_path, sorted(scenario_types)))
    validate_scenario_reference(metadata_path, str(data.get("scenario") or ""), scenarios, errors)
    for field in ("tags", "required_tools", "expected_signal"):
        if field in data:
            require_list_of_strings(data, field, metadata_path, errors)
    command_path = metadata_path.with_name("command.md")
    if not command_path.exists():
        fail(errors, "%s companion command.md does not exist" % metadata_path)


def validate_skill_metadata(metadata_path: Path, taxonomies: Dict[str, set], scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    data = load_yaml(metadata_path)
    missing = REQUIRED_SKILL_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing skill metadata fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % metadata_path)
    validate_component_reference(metadata_path, str(data.get("component") or ""), errors)
    scenario_types = taxonomies["scenario_types"]
    if scenario_types and data.get("primary_scenario") not in scenario_types:
        fail(errors, "%s primary_scenario must be one of %s" % (metadata_path, sorted(scenario_types)))
    validate_scenario_reference(metadata_path, str(data.get("primary_scenario") or ""), scenarios, errors)
    for field in ("inputs", "outputs", "required_assets", "safety_constraints"):
        if field in data:
            require_list_of_strings(data, field, metadata_path, errors)
    for ref in data.get("required_assets") or []:
        ref_path = ROOT / ref
        if not ref_path.exists() or not ref_path.is_dir():
            fail(errors, "%s required asset does not exist or is not a directory: %s" % (metadata_path, ref))
    skill_path = metadata_path.with_name("skill.md")
    if not skill_path.exists():
        fail(errors, "%s companion skill.md does not exist" % metadata_path)


def validate_adapter_output(output_path: Path, taxonomies: Dict[str, set], errors: List[str]) -> None:
    data = load_yaml(output_path)
    missing = REQUIRED_ADAPTER_OUTPUT_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing adapter output fields: %s" % (output_path, ", ".join(sorted(missing))))
    if data.get("middleware") != "mongodb":
        fail(errors, "%s middleware must be mongodb" % output_path)
    if data.get("command") not in VALID_ADAPTER_COMMANDS:
        fail(errors, "%s command must be one of %s" % (output_path, sorted(VALID_ADAPTER_COMMANDS)))
    valid_status = taxonomies["adapter_output_status"]
    if data.get("status") not in valid_status:
        fail(errors, "%s status must be one of %s" % (output_path, sorted(valid_status)))
    for field in ("record_refs", "blocking_items", "warnings"):
        if not isinstance(data.get(field), list):
            fail(errors, "%s %s must be a list" % (output_path, field))
    if "next_actions" in data:
        require_list_of_strings(data, "next_actions", output_path, errors)


def validate_domain_assets(taxonomies: Dict[str, set], scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    runbook_root = ROOT / "domains" / "mongodb" / "runbooks"
    command_root = ROOT / "domains" / "mongodb" / "commands"
    skill_root = ROOT / "domains" / "mongodb" / "skills"

    for metadata_path in sorted(runbook_root.glob("**/metadata.yaml")):
        validate_runbook_metadata(metadata_path, taxonomies, scenarios, errors)
    for metadata_path in sorted(command_root.glob("**/metadata.yaml")):
        validate_command_metadata(metadata_path, taxonomies, scenarios, errors)
    for metadata_path in sorted(skill_root.glob("**/metadata.yaml")):
        validate_skill_metadata(metadata_path, taxonomies, scenarios, errors)


def validate_fixtures(errors: List[str]) -> None:
    fixture_root = ROOT / "tests" / "fixtures" / "mongodb"
    if not fixture_root.exists():
        fail(errors, "MongoDB fixture root does not exist: %s" % fixture_root)
        return
    for case_dir in sorted(path for path in fixture_root.iterdir() if path.is_dir()):
        for filename in sorted(REQUIRED_FIXTURE_FILES):
            path = case_dir / filename
            if not path.exists():
                fail(errors, "%s missing fixture file: %s" % (case_dir, filename))
                continue
            load_yaml(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate MongoDB script manifest and plugin runtime map.")
    parser.add_argument("--manifest", default="domains/mongodb/scripts/manifest.yaml")
    parser.add_argument("--runtime-map", default="interfaces/plugin/script-runtime-map.example.yaml")
    parser.add_argument("--context-example", default="domains/mongodb/scripts/context.example.yaml")
    parser.add_argument("--output-example", default="domains/mongodb/scripts/output.example.yaml")
    parser.add_argument("--remote-request", default="interfaces/plugin/remote-executor-request.example.yaml")
    parser.add_argument("--remote-result", default="interfaces/plugin/remote-executor-result.example.yaml")
    parser.add_argument("--adapter-output", default="interfaces/plugin/adapter-output.example.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: List[str] = []
    taxonomies = load_taxonomies(ROOT / "core/taxonomies", errors)
    scenarios = load_scenarios(ROOT / "scenarios", "mongodb", errors)
    manifest_by_id = validate_manifest(ROOT / args.manifest, errors)
    runtime_by_id = validate_runtime_map(ROOT / args.runtime_map, manifest_by_id, errors)
    validate_context_example(ROOT / args.context_example, manifest_by_id, errors)
    validate_output_example(ROOT / args.output_example, manifest_by_id, taxonomies, errors)
    validate_remote_request(ROOT / args.remote_request, manifest_by_id, runtime_by_id, errors)
    validate_remote_result(ROOT / args.remote_result, manifest_by_id, taxonomies, errors)
    validate_domain_assets(taxonomies, scenarios, errors)
    validate_fixtures(errors)
    validate_adapter_output(ROOT / args.adapter_output, taxonomies, errors)
    if errors:
        for error in errors:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print("ok: validated %d MongoDB script(s)" % len(manifest_by_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
