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
