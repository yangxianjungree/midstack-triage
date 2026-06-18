import importlib
import os
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def test_runtime_root_env_overrides_repo_root(monkeypatch):
    runtime_root = Path("/tmp/fake-plugin/runtime")
    monkeypatch.setenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", str(runtime_root))
    module = importlib.import_module("execution.remote.runtime_support")
    module = importlib.reload(module)

    assert module.ROOT == runtime_root
    assert module.DEFAULT_MANIFEST == runtime_root / "domains" / "mongodb" / "scripts" / "manifest.yaml"
    assert module.DEFAULT_RUNTIME_MAP == runtime_root / "interfaces" / "plugin" / "script-runtime-map.example.yaml"

    monkeypatch.delenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", raising=False)
    importlib.reload(module)


def test_source_checkout_root_points_to_repo_root(monkeypatch):
    monkeypatch.delenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", raising=False)
    module = importlib.import_module("execution.remote.runtime_support")
    module = importlib.reload(module)

    assert module.ROOT == ROOT
    assert module.DEFAULT_MANIFEST == ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml"
    assert module.DEFAULT_RUNTIME_MAP == ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml"


def test_load_config_reads_yaml_object(tmp_path):
    module = importlib.import_module("execution.remote.runtime_support")
    target = tmp_path / "config.yaml"
    target.write_text(yaml.safe_dump({"status": "ok"}), encoding="utf-8")

    assert module.load_config(target) == {"status": "ok"}
