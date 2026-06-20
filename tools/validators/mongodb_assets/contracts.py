#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from typing import Any, Dict, List


TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import load_yaml  # noqa: E402

from .common import (  # noqa: E402
    MIDDLEWARE,
    REQUIRED_ADAPTER_OUTPUT_FIELDS,
    REQUIRED_CONTEXT_FIELDS,
    REQUIRED_MANIFEST_FIELDS,
    REQUIRED_OUTPUT_FIELDS,
    REQUIRED_REMOTE_REQUEST_FIELDS,
    REQUIRED_REMOTE_RESULT_FIELDS,
    REQUIRED_RUNTIME_FIELDS,
    REQUIRED_RUNTIME_MAP_FIELDS,
    REQUIRED_SCENARIO_FIELDS,
    SCRIPT_ID_RE,
    VALID_ADAPTER_COMMANDS,
    VALID_ADAPTER_STATUS,
    VALID_COLLECTION_TIERS,
    VALID_COST_CLASSES,
    VALID_EXECUTOR_STATUS,
    VALID_NOISE_CLASSES,
    VALID_RISK_LEVELS,
    VALID_RUNTIMES,
    VALID_SCRIPT_STATUS,
    VALID_SIGNAL_LAYERS,
    fail,
    require_list_of_strings,
)


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
    triage_surface_types = taxonomy_ids(taxonomy_dir / "triage-surface-types.yaml", errors)
    capability_types = taxonomy_ids(taxonomy_dir / "capability-types.yaml", errors)

    status_data = load_yaml(taxonomy_dir / "status-types.yaml")
    status_types: Dict[str, set] = {}
    for key in ("script_output_status", "remote_executor_status", "adapter_output_status", "asset_status", "review_score"):
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
        "triage_surface_types": triage_surface_types,
        "capability_types": capability_types,
        "script_output_status": status_types.get("script_output_status") or VALID_SCRIPT_STATUS,
        "remote_executor_status": status_types.get("remote_executor_status") or VALID_EXECUTOR_STATUS,
        "adapter_output_status": status_types.get("adapter_output_status") or VALID_ADAPTER_STATUS,
        "asset_status": status_types.get("asset_status") or {"active", "draft", "deprecated", "experimental"},
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
    return scenarios


def validate_manifest(manifest_path: Path, errors: List[str]) -> Dict[str, Dict[str, Any]]:
    data = load_yaml(manifest_path)
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "manifest.middleware must be %s" % MIDDLEWARE)
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
        if item.get("collection_tier") not in VALID_COLLECTION_TIERS:
            fail(errors, "%s collection_tier must be one of %s" % (script_id, sorted(VALID_COLLECTION_TIERS)))
        if item.get("signal_layer") not in VALID_SIGNAL_LAYERS:
            fail(errors, "%s signal_layer must be one of %s" % (script_id, sorted(VALID_SIGNAL_LAYERS)))
        if item.get("cost_class") not in VALID_COST_CLASSES:
            fail(errors, "%s cost_class must be one of %s" % (script_id, sorted(VALID_COST_CLASSES)))
        if item.get("noise_class") not in VALID_NOISE_CLASSES:
            fail(errors, "%s noise_class must be one of %s" % (script_id, sorted(VALID_NOISE_CLASSES)))
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
            fail(errors, "%s runtime_path must be runtime-relative" % script_id)
        if script_id.startswith("mongodb.") and not runtime_path.startswith("assets/scripts/mongodb/"):
            fail(errors, "%s runtime_path must start with assets/scripts/mongodb/" % script_id)

    packaged_ids = {script_id for script_id, item in manifest_by_id.items() if item.get("default_packaged") is True}
    runtime_ids = {script_id for script_id in runtime_by_id if script_id.startswith("mongodb.")}
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
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (context_path, MIDDLEWARE))
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
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (request_path, MIDDLEWARE))
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


def validate_adapter_output(output_path: Path, taxonomies: Dict[str, set], errors: List[str]) -> None:
    data = load_yaml(output_path)
    missing = REQUIRED_ADAPTER_OUTPUT_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing adapter output fields: %s" % (output_path, ", ".join(sorted(missing))))
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (output_path, MIDDLEWARE))
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
