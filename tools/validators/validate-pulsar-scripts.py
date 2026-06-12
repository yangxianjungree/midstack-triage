#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml

VALIDATORS_DIR = Path(__file__).resolve().parent
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

from asset_refs import (  # noqa: E402
    load_metadata_index,
    load_scenario_ids,
    validate_required_asset_ref,
)

ROOT = Path(__file__).resolve().parents[2]
MIDDLEWARE = "pulsar"
SCRIPT_ID_RE = re.compile(r"^pulsar\.(collect|normalize)\.[a-z0-9_]+\.[a-z0-9_]+$")
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
REQUIRED_RUNBOOK_FIELDS = {"id", "title", "middleware", "component", "scenario"}
REQUIRED_COMMAND_FIELDS = {"id", "title", "middleware", "component", "scenario"}
REQUIRED_SKILL_FIELDS = {"id", "title", "middleware", "component", "primary_scenario"}


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def fail(errors: List[str], message: str) -> None:
    errors.append(message)


def load_manifest() -> Dict[str, Dict[str, Any]]:
    manifest_path = ROOT / "domains" / MIDDLEWARE / "scripts" / "manifest.yaml"
    data = load_yaml(manifest_path)
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in data.get("scripts") or []:
        if isinstance(item, dict) and item.get("script_id"):
            by_id[str(item["script_id"])] = item
    return by_id


def validate_manifest(errors: List[str]) -> Dict[str, Dict[str, Any]]:
    manifest_path = ROOT / "domains" / MIDDLEWARE / "scripts" / "manifest.yaml"
    if not manifest_path.exists():
        fail(errors, "missing manifest: %s" % manifest_path)
        return {}
    data = load_yaml(manifest_path)
    by_id: Dict[str, Dict[str, Any]] = {}
    for item in data.get("scripts") or []:
        if not isinstance(item, dict):
            fail(errors, "manifest scripts entries must be objects")
            continue
        missing = REQUIRED_MANIFEST_FIELDS - set(item)
        if missing:
            fail(errors, "manifest entry missing fields: %s" % ", ".join(sorted(missing)))
        script_id = str(item.get("script_id") or "")
        if script_id and not SCRIPT_ID_RE.match(script_id):
            fail(errors, "invalid script_id: %s" % script_id)
        source = item.get("source")
        if isinstance(source, str):
            source_path = ROOT / "domains" / MIDDLEWARE / "scripts" / source
            if not source_path.exists():
                fail(errors, "manifest source does not exist: %s" % source)
        if script_id:
            if script_id in by_id:
                fail(errors, "duplicate script_id: %s" % script_id)
            by_id[script_id] = item
    return by_id


def validate_metadata_bundle(
    metadata_path: Path,
    required_fields: Set[str],
    scenarios: Set[str],
    manifest_by_id: Dict[str, Dict[str, Any]],
    runbooks: Dict[str, Path],
    commands: Dict[str, Path],
    skills: Dict[str, Path],
    errors: List[str],
) -> None:
    data = load_yaml(metadata_path)
    missing = required_fields - set(data)
    if missing:
        fail(errors, "%s missing fields: %s" % (metadata_path, ", ".join(sorted(missing))))
    if data.get("middleware") != MIDDLEWARE:
        fail(errors, "%s middleware must be %s" % (metadata_path, MIDDLEWARE))
    scenario = data.get("scenario") or data.get("primary_scenario")
    if isinstance(scenario, str) and scenario not in scenarios:
        fail(errors, "%s scenario does not exist: %s" % (metadata_path, scenario))
    for ref in data.get("required_assets") or []:
        validate_required_asset_ref(
            ref,
            str(metadata_path),
            manifest_by_id,
            runbooks,
            commands,
            skills,
            scenarios,
            errors,
        )


def main() -> int:
    errors: List[str] = []
    manifest_by_id = validate_manifest(errors)
    scenarios = load_scenario_ids()
    runbooks = load_metadata_index(MIDDLEWARE, "runbooks")
    commands = load_metadata_index(MIDDLEWARE, "commands")
    skills = load_metadata_index(MIDDLEWARE, "skills")

    for metadata_path in sorted((ROOT / "domains" / MIDDLEWARE / "runbooks").glob("**/metadata.yaml")):
        validate_metadata_bundle(
            metadata_path,
            REQUIRED_RUNBOOK_FIELDS,
            scenarios,
            manifest_by_id,
            runbooks,
            commands,
            skills,
            errors,
        )
    for metadata_path in sorted((ROOT / "domains" / MIDDLEWARE / "commands").glob("**/metadata.yaml")):
        validate_metadata_bundle(
            metadata_path,
            REQUIRED_COMMAND_FIELDS,
            scenarios,
            manifest_by_id,
            runbooks,
            commands,
            skills,
            errors,
        )
    for metadata_path in sorted((ROOT / "domains" / MIDDLEWARE / "skills").glob("**/metadata.yaml")):
        validate_metadata_bundle(
            metadata_path,
            REQUIRED_SKILL_FIELDS,
            scenarios,
            manifest_by_id,
            runbooks,
            commands,
            skills,
            errors,
        )
        data = load_yaml(metadata_path)
        for ref in data.get("required_assets") or []:
            if isinstance(ref, dict):
                validate_required_asset_ref(
                    ref,
                    str(metadata_path),
                    manifest_by_id,
                    runbooks,
                    commands,
                    skills,
                    scenarios,
                    errors,
                )

    if errors:
        print("Pulsar asset validation failed:", file=sys.stderr)
        for item in errors:
            print("- %s" % item, file=sys.stderr)
        return 1

    print("ok: validated %d Pulsar script(s)" % len(manifest_by_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
