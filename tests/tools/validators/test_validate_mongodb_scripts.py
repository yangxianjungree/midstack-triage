#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path


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
