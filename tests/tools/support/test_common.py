#!/usr/bin/env python3

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

COMMON_PATH = TOOLS_DIR / "support" / "common.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tools_support_common", COMMON_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_resolve_repo_path_handles_relative_and_absolute(tmp_path):
    module = load_module()
    relative = module.resolve_repo_path("tests/fixtures")
    absolute = module.resolve_repo_path(str(tmp_path))

    assert relative == ROOT / "tests/fixtures"
    assert absolute == tmp_path


def test_write_yaml_and_load_yaml_round_trip(tmp_path):
    module = load_module()
    target = tmp_path / "sample.yaml"
    payload = {"status": "ok", "items": [1, 2, 3]}

    module.write_yaml(target, payload)

    assert module.load_yaml(target) == payload


def test_run_command_captures_stdout_and_stderr():
    module = load_module()

    proc = module.run_command([sys.executable, "-c", "import sys; print('ok'); print('warn', file=sys.stderr)"])

    assert proc.returncode == 0
    assert proc.stdout.strip() == "ok"
    assert proc.stderr.strip() == "warn"


def test_write_text_files_dry_run_and_conflict(tmp_path, capsys):
    module = load_module()
    existing = tmp_path / "existing.txt"
    existing.write_text("hello\n", encoding="utf-8")

    rc = module.write_text_files([(existing, "updated\n")], force=False, dry_run=True)
    assert rc == 0
    assert "would write" in capsys.readouterr().out

    rc = module.write_text_files([(existing, "updated\n")], force=False, dry_run=False)
    assert rc == 1
    assert "already exists" in capsys.readouterr().err
