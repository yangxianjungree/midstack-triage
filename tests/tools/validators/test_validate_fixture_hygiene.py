#!/usr/bin/env python3

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "tools" / "validators" / "validate-fixture-hygiene.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_fixture_hygiene", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_fixture(root: Path, relpath: str, text: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_hygiene_scans_golden_path_fixtures(tmp_path):
    module = load_module()
    write_fixture(
        tmp_path,
        "tests/golden-paths/fixtures/context.yaml",
        "token: ghp_1234567890abcdef1234567890abcdef\n",
    )

    errors, warnings = module.validate_fixture_hygiene(tmp_path)

    assert warnings == []
    assert errors == ["possible secret in fixture: tests/golden-paths/fixtures/context.yaml"]


def test_hygiene_blocks_generated_artifacts(tmp_path):
    module = load_module()
    write_fixture(tmp_path, "tests/fixtures/active/mongodb/case/remote-config.yaml", "access: {}\n")

    errors, warnings = module.validate_fixture_hygiene(tmp_path)

    assert warnings == []
    assert errors == ["generated fixture artifact tracked in repository: tests/fixtures/active/mongodb/case/remote-config.yaml"]


def test_hygiene_blocks_public_ip_but_warns_private_ip(tmp_path):
    module = load_module()
    write_fixture(tmp_path, "tests/fixtures/active/mongodb/case/input.yaml", "public: 8.8.8.8\nprivate: 192.168.1.10\n")

    errors, warnings = module.validate_fixture_hygiene(tmp_path)

    assert errors == ["public IP address in fixture: tests/fixtures/active/mongodb/case/input.yaml (8.8.8.8)"]
    assert warnings == ["private IP address in fixture: tests/fixtures/active/mongodb/case/input.yaml (192.168.1.10)"]


def test_hygiene_allows_test_values(tmp_path):
    module = load_module()
    write_fixture(
        tmp_path,
        "tests/golden-paths/fixtures/context.yaml",
        "username: test-user\npassword: example-password\nprimary_ip: 10.0.0.1\n",
    )

    errors, warnings = module.validate_fixture_hygiene(tmp_path)

    assert errors == []
    assert warnings == []
