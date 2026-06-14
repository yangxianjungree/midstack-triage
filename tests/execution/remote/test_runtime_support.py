import importlib
import os
import sys
from pathlib import Path


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
