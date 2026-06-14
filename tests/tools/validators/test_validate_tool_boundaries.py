#!/usr/bin/env python3

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "tools" / "validators" / "validate-tool-boundaries.py"


def load_module():
    spec = importlib.util.spec_from_file_location("validate_tool_boundaries", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_current_repo_boundaries_pass():
    module = load_module()
    assert module.validate_tool_directories(ROOT) == []
    assert module.validate_wrapper_scripts(ROOT) == []
    assert module.validate_src_import_boundary(ROOT) == []


def test_validate_wrapper_script_rejects_thick_logic(tmp_path):
    module = load_module()
    wrapper = tmp_path / "tools" / "plugin" / "midstack-local.py"
    wrapper.parent.mkdir(parents=True)
    wrapper.write_text(
        """#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

def parse_args():
    parser = argparse.ArgumentParser()
    return parser.parse_args()

from commands.plugin_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )

    errors = module.validate_wrapper_script(
        wrapper,
        module.THIN_WRAPPER_SPECS["tools/plugin/midstack-local.py"],
    )

    assert any("forbidden thick-wrapper marker: argparse" in error for error in errors)
    assert any("forbidden thick-wrapper marker: def parse_args" in error for error in errors)


def test_validate_src_import_boundary_rejects_tools_import(tmp_path):
    module = load_module()
    source_file = tmp_path / "src" / "demo.py"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("from tools.plugin import midstack_local\n", encoding="utf-8")

    errors = module.validate_src_import_boundary(tmp_path)

    assert errors == ["src runtime must not import tools/: %s" % source_file]
