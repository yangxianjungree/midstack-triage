#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Any, Dict, List


VALIDATORS_DIR = Path(__file__).resolve().parents[1]
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))
TOOLS_DIR = Path(__file__).resolve().parents[2]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from asset_refs import load_metadata_index, load_scenario_ids, validate_required_asset_ref  # noqa: E402
from support.common import ROOT, load_yaml  # noqa: E402

from .common import (  # noqa: E402
    MIDDLEWARE,
    REQUIRED_COMMAND_FIELDS,
    REQUIRED_FIXTURE_FILES,
    REQUIRED_RUNBOOK_FIELDS,
    REQUIRED_SKILL_FIELDS,
    fail,
    require_list_of_strings,
)


def validate_scenario_reference(metadata_path: Path, scenario_id: str, scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    if scenario_id not in scenarios:
        fail(errors, "%s scenario reference does not exist: scenarios/%s/scenario.yaml" % (metadata_path, scenario_id))


def validate_component_reference(metadata_path: Path, component: str, triage_surfaces: set, errors: List[str]) -> None:
    if triage_surfaces and component not in triage_surfaces:
        fail(errors, "%s component must be a triage surface in core/taxonomies/triage-surface-types.yaml" % metadata_path)
    component_readme = ROOT / "domains" / MIDDLEWARE / "components" / component / "README.md"
    if not component_readme.exists():
        fail(errors, "%s component reference does not exist: %s" % (metadata_path, component_readme))


def validate_runbook_metadata(metadata_path: Path, taxonomies: Dict[str, set], scenarios: Dict[str, Dict[str, Any]], errors: List[str]) -> None:
    data = load_yaml(metadata_path)
    missing = REQUIRED_RUNBOOK_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing runbook metadata fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (metadata_path, MIDDLEWARE))
    validate_component_reference(metadata_path, str(data.get("component") or ""), taxonomies["triage_surface_types"], errors)
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
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (metadata_path, MIDDLEWARE))
    validate_component_reference(metadata_path, str(data.get("component") or ""), taxonomies["triage_surface_types"], errors)
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


def validate_skill_metadata(
    metadata_path: Path,
    taxonomies: Dict[str, set],
    scenarios: Dict[str, Dict[str, Any]],
    manifest_by_id: Dict[str, Dict[str, Any]],
    runbooks: Dict[str, Path],
    commands: Dict[str, Path],
    skills: Dict[str, Path],
    scenario_ids: set,
    errors: List[str],
) -> None:
    data = load_yaml(metadata_path)
    missing = REQUIRED_SKILL_FIELDS - set(data)
    if missing:
        fail(errors, "%s missing skill metadata fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (metadata_path, MIDDLEWARE))
    validate_component_reference(metadata_path, str(data.get("component") or ""), taxonomies["triage_surface_types"], errors)
    scenario_types = taxonomies["scenario_types"]
    if scenario_types and data.get("primary_scenario") not in scenario_types:
        fail(errors, "%s primary_scenario must be one of %s" % (metadata_path, sorted(scenario_types)))
    validate_scenario_reference(metadata_path, str(data.get("primary_scenario") or ""), scenarios, errors)
    for field in ("inputs", "outputs", "safety_constraints"):
        if field in data:
            require_list_of_strings(data, field, metadata_path, errors)
    required_assets = data.get("required_assets") or []
    if not isinstance(required_assets, list) or not required_assets:
        fail(errors, "%s required_assets must be a non-empty list" % metadata_path)
    for index, ref in enumerate(required_assets):
        if not isinstance(ref, (str, dict)):
            fail(errors, "%s required_assets[%d] must be a string or object" % (metadata_path, index))
            continue
        validate_required_asset_ref(
            ref,
            "%s required_assets[%d]" % (metadata_path, index),
            manifest_by_id,
            runbooks,
            commands,
            skills,
            scenario_ids,
            errors,
        )
    skill_path = metadata_path.with_name("skill.md")
    if not skill_path.exists():
        fail(errors, "%s companion skill.md does not exist" % metadata_path)


def validate_domain_assets(
    taxonomies: Dict[str, set],
    scenarios: Dict[str, Dict[str, Any]],
    manifest_by_id: Dict[str, Dict[str, Any]],
    errors: List[str],
) -> None:
    runbook_root = ROOT / "domains" / MIDDLEWARE / "runbooks"
    command_root = ROOT / "domains" / MIDDLEWARE / "commands"
    skill_root = ROOT / "domains" / MIDDLEWARE / "skills"
    runbooks = load_metadata_index(MIDDLEWARE, "runbooks")
    commands = load_metadata_index(MIDDLEWARE, "commands")
    skills = load_metadata_index(MIDDLEWARE, "skills")
    scenario_ids = load_scenario_ids()

    for metadata_path in sorted(runbook_root.glob("**/metadata.yaml")):
        validate_runbook_metadata(metadata_path, taxonomies, scenarios, errors)
    for metadata_path in sorted(command_root.glob("**/metadata.yaml")):
        validate_command_metadata(metadata_path, taxonomies, scenarios, errors)
    for metadata_path in sorted(skill_root.glob("**/metadata.yaml")):
        validate_skill_metadata(
            metadata_path,
            taxonomies,
            scenarios,
            manifest_by_id,
            runbooks,
            commands,
            skills,
            scenario_ids,
            errors,
        )


def validate_fixtures(errors: List[str]) -> None:
    fixture_root = ROOT / "tests" / "fixtures" / "active" / MIDDLEWARE
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
