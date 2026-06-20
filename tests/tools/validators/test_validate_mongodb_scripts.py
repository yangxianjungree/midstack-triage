#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = ROOT / "tools"
VALIDATORS_DIR = TOOLS_DIR / "validators"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(VALIDATORS_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATORS_DIR))

CLI_PATH = VALIDATORS_DIR / "validate-mongodb-scripts.py"


def load_wrapper_module():
    spec = importlib.util.spec_from_file_location("validate_mongodb_scripts", CLI_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_mongodb_scripts_passes_for_current_repo():
    from mongodb_assets import cli as module

    assert module.main([]) == 0


def test_runtime_map_includes_domain_neutral_kubernetes_log_assets():
    runtime_map = yaml.safe_load((ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml").read_text(encoding="utf-8"))
    manifest = yaml.safe_load((ROOT / "domains" / "kubernetes" / "scripts" / "manifest.yaml").read_text(encoding="utf-8"))

    manifest_ids = {item["script_id"] for item in manifest["scripts"]}
    runtime_ids = {item["script_id"] for item in runtime_map["scripts"]}

    assert {"kubernetes.collect.logs.current", "kubernetes.collect.logs.previous"} <= manifest_ids
    assert manifest_ids <= runtime_ids


def test_default_mongodb_collection_set_uses_shared_kubernetes_logs():
    mongodb_manifest = yaml.safe_load((ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml").read_text(encoding="utf-8"))
    kubernetes_manifest = yaml.safe_load((ROOT / "domains" / "kubernetes" / "scripts" / "manifest.yaml").read_text(encoding="utf-8"))

    combined = {
        item["script_id"]: item
        for manifest in (mongodb_manifest, kubernetes_manifest)
        for item in manifest["scripts"]
    }
    default_ids = {script_id for script_id, item in combined.items() if item.get("mvp") is True}

    assert len(default_ids) == 12
    assert {"kubernetes.collect.logs.current", "kubernetes.collect.logs.previous"} <= default_ids
    assert "mongodb.collect.logs.current" not in default_ids
    assert "mongodb.collect.logs.previous" not in default_ids


def test_documented_default_collection_lists_match_runtime_order():
    from mongodb_assets import cli as module

    errors = []
    manifest_by_id = module.validate_manifest(ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml", errors)
    shared_by_id = module.shared_kubernetes_manifest_by_id()
    runtime_by_id = module.validate_runtime_map(ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml", manifest_by_id, errors)
    expected_ids = module.default_collection_script_ids(manifest_by_id, shared_by_id, runtime_by_id)

    module.validate_documented_default_collection_set(expected_ids, errors)

    assert errors == []


def test_documented_default_collection_lists_report_mismatch(tmp_path):
    from mongodb_assets import cli as module

    doc = tmp_path / "doc.md"
    doc.write_text("marker\n\n1. `mongodb.collect.pods.state`\n", encoding="utf-8")
    errors = []

    module.validate_documented_default_collection_set(
        ["mongodb.collect.pods.state", "mongodb.collect.statefulsets.yaml"],
        errors,
        docs=[(doc, "marker")],
    )

    assert any("default MVP script list differs from runtime order" in item for item in errors)


def test_compatibility_aliases_must_not_be_default_collection_assets():
    from mongodb_assets import cli as module

    errors = []
    module.validate_compatibility_aliases(
        {
            "mongodb.collect.logs.current": {
                "compatibility_alias": True,
                "mvp": True,
                "collection_tier": "baseline",
                "superseded_by": "kubernetes.collect.logs.current",
            },
            "mongodb.collect.logs.previous": {
                "compatibility_alias": True,
                "mvp": False,
                "collection_tier": "directed",
                "superseded_by": "kubernetes.collect.logs.missing",
            },
        },
        {"kubernetes.collect.logs.current": {"script_id": "kubernetes.collect.logs.current"}},
        errors,
    )

    assert "mongodb.collect.logs.current compatibility alias must not be an MVP script" in errors
    assert "mongodb.collect.logs.current compatibility alias must not be a baseline script" in errors
    assert "mongodb.collect.logs.previous superseded_by target is not a known packaged asset: kubernetes.collect.logs.missing" in errors


def test_validate_mongodb_scripts_wrapper_stays_thin():
    text = CLI_PATH.read_text(encoding="utf-8")

    assert "from mongodb_assets.cli import main" in text
    assert "raise SystemExit(main())" in text
    assert len(text.splitlines()) <= 20


def test_validate_mongodb_scripts_wrapper_loads():
    module = load_wrapper_module()

    assert callable(module.main)


def test_mongodb_skill_metadata_requires_version_and_known_status(tmp_path):
    from mongodb_assets.domain_assets import validate_skill_metadata

    metadata_path = tmp_path / "metadata.yaml"
    metadata_path.write_text(
        yaml.safe_dump(
            {
                "id": "mongodb-test-skill",
                "title": "MongoDB Test Skill",
                "middleware": "mongodb",
                "component": "connectivity",
                "primary_scenario": "connection-failure",
                "inputs": ["input"],
                "outputs": ["output"],
                "required_assets": [{"type": "scenario", "id": "connection-failure"}],
                "safety_constraints": ["read-only"],
                "status": "invalid",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# Test Skill\n", encoding="utf-8")
    errors = []

    validate_skill_metadata(
        metadata_path,
        {
            "asset_status": {"active", "draft", "deprecated", "experimental"},
            "triage_surface_types": {"connectivity"},
            "scenario_types": {"connection-failure"},
        },
        {
            "connection-failure": {
                "applicable_middleware": ["mongodb"],
            }
        },
        {},
        {},
        {},
        {},
        {"connection-failure"},
        errors,
    )

    assert any("missing skill metadata fields: version" in item for item in errors)
    assert any("status must be one of" in item for item in errors)
