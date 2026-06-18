import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def reload_workspace():
    module = importlib.import_module("shared.workspace")
    return importlib.reload(module)


def test_runtime_root_env_overrides_source_root(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", str(runtime))
    monkeypatch.delenv("MIDSTACK_TRIAGE_WORKSPACE", raising=False)

    workspace = reload_workspace()

    assert workspace.runtime_root() == runtime
    assert workspace.source_root() == ROOT
    assert workspace.workspace_root() == runtime


def test_workspace_root_is_separate_from_runtime_root(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    workspace_dir = tmp_path / "workspace"
    monkeypatch.setenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(workspace_dir))

    workspace = reload_workspace()

    assert workspace.runtime_root() == runtime
    assert workspace.workspace_root() == workspace_dir
    assert workspace.path_from_arg(".local/incidents") == workspace_dir / ".local/incidents"


def test_resolve_path_falls_back_to_runtime_root(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    workspace_dir = tmp_path / "workspace"
    fixture = runtime / "tests" / "fixtures" / "demo"
    fixture.mkdir(parents=True)
    monkeypatch.setenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(workspace_dir))

    workspace = reload_workspace()

    assert workspace.resolve_path("tests/fixtures/demo") == fixture
