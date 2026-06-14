import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
MIDSTACK_LOCAL_PATH = ROOT / "tools" / "plugin" / "midstack-local.py"


def load_midstack_local():
    spec = importlib.util.spec_from_file_location("midstack_local", MIDSTACK_LOCAL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_path_from_arg_uses_workspace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    module = load_midstack_local()
    assert module.path_from_arg(".local/incidents") == tmp_path / ".local/incidents"


def test_resolve_path_prefers_workspace_when_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    incident = tmp_path / ".local" / "incidents" / "demo"
    incident.mkdir(parents=True)
    module = load_midstack_local()
    assert module.resolve_path(".local/incidents/demo") == incident


def test_path_from_arg_targets_workspace_for_new_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    module = load_midstack_local()
    target = module.path_from_arg(".local/incidents/new-case")
    assert target == tmp_path / ".local" / "incidents" / "new-case"
    assert not target.exists()


def test_resolve_path_falls_back_to_repo_for_fixtures(monkeypatch):
    monkeypatch.delenv("MIDSTACK_TRIAGE_WORKSPACE", raising=False)
    module = load_midstack_local()
    fixture = module.resolve_path("tests/fixtures/mongodb/connection-failure-sample")
    assert fixture == ROOT / "tests" / "fixtures" / "mongodb" / "connection-failure-sample"


def test_start_ready_output_points_to_midstack_analyse(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    module = load_midstack_local()

    monkeypatch.setattr(module, "validate_remote_environment", lambda access: {"status": "passed", "checks": []})
    monkeypatch.setattr(
        module,
        "discover_mongodb_inventory",
        lambda access, namespace: {
            "status": "passed",
            "selected_namespace": "psmdb-test",
            "namespace_source": "auto_discovered",
        },
    )

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        output_root=".local/incidents",
    )

    rc = module.command_start(args)
    assert rc == 0

    current_incident = module.read_current_incident(tmp_path / ".local" / "incidents")
    output = module.load_yaml(current_incident / "adapter-output.yaml")
    assert output["status"] == "ready"
    assert output["next_actions"] == [
        "run /midstack:analyse",
        "or run /midstack:analyse %s" % current_incident.name,
    ]
    assert output["user_message"] == (
        "local incident %s is ready; namespace auto-discovered as psmdb-test; next run /midstack:analyse"
        % current_incident.name
    )
