import sys
from pathlib import Path
from types import SimpleNamespace

import yaml


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from commands import plugin_cli as module  # noqa: E402
from shared.workspace import load_yaml, path_from_arg, read_current_incident, resolve_path  # noqa: E402


def test_path_from_arg_uses_workspace_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    assert path_from_arg(".local/incidents") == tmp_path / ".local/incidents"


def test_resolve_path_prefers_workspace_when_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    incident = tmp_path / ".local" / "incidents" / "demo"
    incident.mkdir(parents=True)
    assert resolve_path(".local/incidents/demo") == incident


def test_path_from_arg_targets_workspace_for_new_output_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    target = path_from_arg(".local/incidents/new-case")
    assert target == tmp_path / ".local" / "incidents" / "new-case"
    assert not target.exists()


def test_resolve_path_falls_back_to_repo_for_fixtures(monkeypatch):
    monkeypatch.delenv("MIDSTACK_TRIAGE_WORKSPACE", raising=False)
    fixture = resolve_path("tests/fixtures/active/mongodb/connection-failure-sample")
    assert fixture == ROOT / "tests" / "fixtures" / "active" / "mongodb" / "connection-failure-sample"


def test_start_ready_output_points_to_midstack_analyse(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

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

    current_incident = read_current_incident(tmp_path / ".local" / "incidents")
    output = load_yaml(current_incident / "adapter-output.yaml")
    assert output["status"] == "ready"
    assert output["next_actions"] == [
        "run /midstack:analyse",
        "or run /midstack:analyse %s" % current_incident.name,
    ]
    assert output["user_message"] == (
        "local incident %s is ready; namespace auto-discovered as psmdb-test; next run /midstack:analyse"
        % current_incident.name
    )


def test_offline_analyse_does_not_call_remote_collection(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    fixture = ROOT / "tests" / "fixtures" / "active" / "mongodb" / "kubernetes-crashloop-sample"
    output_dir = tmp_path / ".local" / "incidents" / "offline"

    def fail_remote_collection(*_args, **_kwargs):
        raise AssertionError("offline analyse must not call remote collection")

    monkeypatch.setattr(module, "run_remote_collection", fail_remote_collection)

    args = SimpleNamespace(
        input_dir=str(fixture),
        remote_run_dir=None,
        remote_config=None,
        incident_dir=None,
        output_dir=str(output_dir),
        output_root=".local/incidents",
        scenario=None,
        customer_clue=None,
        remote_output_dir=".local/remote-runs",
        remote_namespace="",
        object_inventory="",
        execution_mode="offline",
    )

    assert module.command_analyse(args) == 0
    adapter = yaml.safe_load((output_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
    assert adapter["status"] == "completed"
