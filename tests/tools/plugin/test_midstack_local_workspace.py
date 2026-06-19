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


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


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
    phase1_intake = load_yaml(current_incident / "phase1-intake.yaml")
    assert phase1_intake["status"] == "ready_for_validation"
    assert phase1_intake["environment_mode"] == "remote"
    assert phase1_intake["intake_scenario"]["id"] == "remote_ssh"
    assert output["next_actions"] == [
        "run /midstack:analyse",
        "or run /midstack:analyse %s" % current_incident.name,
    ]
    assert output["user_message"] == (
        "local incident %s is ready; namespace auto-discovered as psmdb-test; next run /midstack:analyse"
        % current_incident.name
    )


def test_start_blocked_writes_follow_up_questions_for_missing_remote_inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="",
        customer_clue="mongo node may be unhealthy",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        output_root=".local/incidents",
    )

    rc = module.command_start(args)
    assert rc == 0

    current_incident = read_current_incident(tmp_path / ".local" / "incidents")
    output = load_yaml(current_incident / "adapter-output.yaml")
    intake = load_yaml(current_incident / "phase1-intake.yaml")
    assert output["status"] == "blocked"
    assert intake["status"] == "blocked"
    assert [item["field"] for item in output["follow_up_questions"]] == [
        "environment_mode",
        "environment_ip",
        "username",
        "password",
    ]
    assert output["next_actions"] == [item["question"] for item in output["follow_up_questions"]]


def test_start_missing_remote_ip_records_available_local_context_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="local-context-hint",
        customer_clue="mongo node may be unhealthy",
        environment_ip=[],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    assert module.command_start(
        args,
        probe_local_context=lambda: {
            "status": "available",
            "reason": "",
            "current_context": "prod-cluster",
        },
    ) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "local-context-hint"
    intake = load_yaml(incident_dir / "phase1-intake.yaml")
    output = load_yaml(incident_dir / "adapter-output.yaml")
    assert intake["local_context"] == {
        "status": "available",
        "reason": "",
        "current_context": "prod-cluster",
    }
    assert "prod-cluster" in output["follow_up_questions"][0]["question"]
    assert output["follow_up_questions"][0]["field"] == "environment_mode"


def test_start_ready_remote_does_not_probe_local_context(tmp_path, monkeypatch):
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
        incident_id="remote-no-local-probe",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    def fail_probe():
        raise AssertionError("ready remote start must not probe local context")

    assert module.command_start(args, probe_local_context=fail_probe) == 0

    intake = load_yaml(tmp_path / ".local" / "incidents" / "remote-no-local-probe" / "phase1-intake.yaml")
    assert intake["local_context"]["status"] == "not_checked"


def test_start_can_continue_blocked_incident_with_missing_remote_answers(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    calls = []

    def validate_remote_environment(access):
        calls.append(access)
        return {"status": "passed", "checks": []}

    monkeypatch.setattr(module, "validate_remote_environment", validate_remote_environment)
    monkeypatch.setattr(
        module,
        "discover_mongodb_inventory",
        lambda access, namespace: {
            "status": "passed",
            "selected_namespace": "psmdb-test",
            "namespace_source": "auto_discovered",
        },
    )

    first_args = SimpleNamespace(
        middleware="mongodb",
        incident_id="phase1-continue-demo",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="",
        password="",
        port=22022,
        namespace="",
        cluster_id="",
        output_root=".local/incidents",
    )
    assert module.command_start(first_args) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "phase1-continue-demo"
    first_output = load_yaml(incident_dir / "adapter-output.yaml")
    assert first_output["status"] == "blocked"
    assert [item["field"] for item in first_output["follow_up_questions"]] == ["username", "password"]

    second_args = SimpleNamespace(
        middleware="",
        incident_id="phase1-continue-demo",
        customer_clue="",
        environment_ip=[],
        username="root",
        password="123",
        port=None,
        namespace="",
        cluster_id="",
        environment_mode="",
        output_root=".local/incidents",
    )
    assert module.command_start(second_args) == 0

    output = load_yaml(incident_dir / "adapter-output.yaml")
    input_data = load_yaml(incident_dir / "input.yaml")
    remote_config = load_yaml(incident_dir / "remote-config.yaml")
    assert output["status"] == "ready"
    assert input_data["middleware"] == "mongodb"
    assert input_data["customer_clue"] == "mongo node may be unhealthy"
    assert input_data["environment_ips"] == ["192.168.154.251"]
    assert remote_config["access"]["username"] == "root"
    assert remote_config["access"]["password"] == "123"
    assert remote_config["access"]["port"] == 22022
    assert calls[-1]["primary_ip"] == "192.168.154.251"
    assert calls[-1]["port"] == 22022


def test_start_remote_validation_failure_writes_follow_up_question(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    monkeypatch.setattr(
        module,
        "validate_remote_environment",
        lambda access: {
            "status": "failed",
            "checks": [{"name": "ssh", "status": "blocked", "error_code": "ssh_auth_failed"}],
        },
    )

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="remote-validation-follow-up",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="root",
        password="bad",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    output = load_yaml(tmp_path / ".local" / "incidents" / "remote-validation-follow-up" / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "remote_environment_validation_failed"
    assert output["follow_up_questions"][0]["field"] == "remote_access"
    assert output["next_actions"] == [output["follow_up_questions"][0]["question"]]


def test_start_historical_resolved_incident_warns_but_allows_live_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    monkeypatch.setattr(module, "validate_remote_environment", lambda access: {"status": "passed", "checks": []})
    monkeypatch.setattr(
        module,
        "discover_mongodb_inventory",
        lambda access, namespace: {
            "status": "passed",
            "namespace_source": "auto_discovered",
            "selected_namespace": "psmdb-test",
        },
    )

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="historical-resolved-incident",
        customer_clue="昨天 MongoDB 脑裂过一次，现在已经恢复了",
        environment_ip=["192.168.154.251"],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "historical-resolved-incident"
    output = load_yaml(incident_dir / "adapter-output.yaml")
    input_data = load_yaml(incident_dir / "input.yaml")
    meta = load_yaml(incident_dir / "meta.yaml")
    assert output["status"] == "ready"
    assert "live collection only proves current state" in output["warnings"][0]
    assert input_data["incident_time"]["mode"] == "historical_resolved"
    assert meta["incident_time"]["still_active"] is False


def test_start_ambiguous_mongodb_namespaces_writes_namespace_follow_up(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    monkeypatch.setattr(module, "validate_remote_environment", lambda access: {"status": "passed", "checks": []})
    monkeypatch.setattr(
        module,
        "discover_mongodb_inventory",
        lambda access, namespace: {
            "status": "ambiguous",
            "candidate_namespaces": ["mongo-a", "mongo-b"],
            "namespace_source": "ambiguous",
        },
    )

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="namespace-ambiguous-follow-up",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    output = load_yaml(tmp_path / ".local" / "incidents" / "namespace-ambiguous-follow-up" / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "multiple_mongodb_namespaces_detected"
    assert output["follow_up_questions"][0]["field"] == "namespace"
    assert "mongo-a, mongo-b" in output["follow_up_questions"][0]["question"]
    assert output["next_actions"] == [output["follow_up_questions"][0]["question"]]


def test_start_mongodb_namespace_not_found_writes_namespace_follow_up(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    monkeypatch.setattr(module, "validate_remote_environment", lambda access: {"status": "passed", "checks": []})
    monkeypatch.setattr(
        module,
        "discover_mongodb_inventory",
        lambda access, namespace: {
            "status": "not_found",
            "candidate_namespaces": [],
            "namespace_source": "not_found",
        },
    )

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="namespace-not-found-follow-up",
        customer_clue="mongo node may be unhealthy",
        environment_ip=["192.168.154.251"],
        username="root",
        password="123",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="remote",
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    output = load_yaml(tmp_path / ".local" / "incidents" / "namespace-not-found-follow-up" / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "mongodb_namespace_not_detected"
    assert output["follow_up_questions"][0]["field"] == "namespace"
    assert output["next_actions"] == [output["follow_up_questions"][0]["question"]]


def test_start_without_middleware_is_runtime_blocked_instead_of_argparse_error(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = module.build_parser().parse_args(["start", "--output-root", ".local/incidents"])

    assert module.command_start(args) == 0
    current_incident = read_current_incident(tmp_path / ".local" / "incidents")
    output = load_yaml(current_incident / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "missing_middleware"
    assert output["follow_up_questions"][0]["field"] == "middleware"


def test_start_local_mode_ready_with_local_context_and_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    calls = []

    def fail_remote_validation(access):
        raise AssertionError("local start must not validate remote SSH access")

    def discover_inventory(access, namespace):
        calls.append((access, namespace))
        return {
            "status": "passed",
            "selected_namespace": "psmdb-test",
            "namespace_source": "auto_discovered",
        }

    monkeypatch.setattr(module, "validate_remote_environment", fail_remote_validation)
    monkeypatch.setattr(module, "discover_mongodb_inventory", discover_inventory)

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="local-ready-start",
        customer_clue="mongo node may be unhealthy",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="local",
        output_root=".local/incidents",
    )

    assert module.command_start(
        args,
        probe_local_context=lambda: {
            "status": "available",
            "reason": "",
            "current_context": "prod-cluster",
        },
    ) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "local-ready-start"
    output = load_yaml(incident_dir / "adapter-output.yaml")
    intake = load_yaml(incident_dir / "phase1-intake.yaml")
    local_config = load_yaml(incident_dir / "local-config.yaml")
    assert output["status"] == "ready"
    assert intake["environment_mode"] == "local"
    assert local_config["context"]["current_context"] == "prod-cluster"
    assert local_config["access"]["node_access"] == {
        "mode": "kubernetes_api_only",
        "ssh": {"enabled": False, "auth_preference": "key_or_agent"},
    }
    assert calls == [({"execution_mode": "local", "current_context": "prod-cluster"}, "")]
    assert output["next_actions"] == [
        "run /midstack:analyse --execution-mode local",
        "or run /midstack:analyse local-ready-start --execution-mode local",
    ]


def test_start_local_mode_blocks_when_local_context_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="local-context-missing",
        customer_clue="mongo node may be unhealthy",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="local",
        output_root=".local/incidents",
    )

    assert module.command_start(
        args,
        probe_local_context=lambda: {
            "status": "unavailable",
            "reason": "kubectl_not_found",
            "current_context": "",
        },
    ) == 0

    output = load_yaml(tmp_path / ".local" / "incidents" / "local-context-missing" / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "local_context_unavailable"


def test_start_local_mode_ready_does_not_emit_follow_up_questions(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
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
        incident_id="local-context-follow-up",
        customer_clue="我就在故障集群控制面机器上",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="local",
        output_root=".local/incidents",
    )

    assert module.command_start(
        args,
        probe_local_context=lambda: {
            "status": "available",
            "reason": "",
            "current_context": "prod-cluster",
        },
    ) == 0

    output = load_yaml(tmp_path / ".local" / "incidents" / "local-context-follow-up" / "adapter-output.yaml")
    assert output["status"] == "ready"
    assert "follow_up_questions" not in output


def test_start_offline_mode_blocks_with_artifact_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="",
        customer_clue="mongo node may be unhealthy",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="offline",
        output_root=".local/incidents",
    )

    rc = module.command_start(args)
    assert rc == 0

    current_incident = read_current_incident(tmp_path / ".local" / "incidents")
    output = load_yaml(current_incident / "adapter-output.yaml")
    assert output["status"] == "blocked"
    assert output["blocking_items"][0]["code"] == "offline_start_needs_artifacts"


def test_start_offline_mode_ready_with_valid_artifact_source(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    artifact_dir = tmp_path / "artifacts" / "mongodb-offline"
    artifact_dir.mkdir(parents=True)
    for filename in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml"):
        (artifact_dir / filename).write_text("{}\n", encoding="utf-8")

    def fail_remote_validation(_access):
        raise AssertionError("offline start must not validate remote access")

    monkeypatch.setattr(module, "validate_remote_environment", fail_remote_validation)

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="offline-artifact-start",
        customer_clue="线上生产告警，已有证据目录",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="offline",
        artifact_source=str(artifact_dir),
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "offline-artifact-start"
    output = load_yaml(incident_dir / "adapter-output.yaml")
    intake = load_yaml(incident_dir / "phase1-intake.yaml")
    input_data = load_yaml(incident_dir / "input.yaml")
    assert output["status"] == "ready"
    assert intake["offline_artifact"]["status"] == "ready"
    assert input_data["artifact_source"] == str(artifact_dir)
    assert input_data["execution_mode"] == "offline"
    assert not (incident_dir / "remote-config.yaml").exists()
    assert output["next_actions"] == [
        "run /midstack:analyse --execution-mode offline",
        "or run /midstack:analyse offline-artifact-start --execution-mode offline",
    ]


def test_start_manual_offline_pasted_evidence_is_saved_as_raw_only(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    args = SimpleNamespace(
        middleware="mongodb",
        incident_id="manual-evidence-start",
        customer_clue="ToDesk 环境，只能粘贴命令输出",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="offline",
        artifact_source="",
        pasted_evidence="kubectl get pods\npod-a CrashLoopBackOff\n",
        output_root=".local/incidents",
    )

    assert module.command_start(args) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "manual-evidence-start"
    output = load_yaml(incident_dir / "adapter-output.yaml")
    intake = load_yaml(incident_dir / "phase1-intake.yaml")
    raw_file = incident_dir / "logs" / "raw" / "manual-evidence.txt"
    assert output["status"] == "blocked"
    assert intake["manual_evidence"]["status"] == "captured"
    assert raw_file.read_text(encoding="utf-8") == "kubectl get pods\npod-a CrashLoopBackOff\n"
    assert not (incident_dir / "structured_record.yaml").exists()
    assert not (incident_dir / "signal_bundle.yaml").exists()
    assert not (incident_dir / "collection_report.yaml").exists()


def test_start_manual_offline_continuation_preserves_raw_evidence_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))

    first_args = SimpleNamespace(
        middleware="mongodb",
        incident_id="manual-evidence-continue",
        customer_clue="ToDesk 环境，只能粘贴命令输出",
        environment_ip=[],
        username="",
        password="",
        port=22,
        namespace="",
        cluster_id="",
        environment_mode="offline",
        artifact_source="",
        pasted_evidence="kubectl get pods\npod-a CrashLoopBackOff\n",
        output_root=".local/incidents",
    )

    assert module.command_start(first_args) == 0

    second_args = SimpleNamespace(
        middleware="",
        incident_id="manual-evidence-continue",
        customer_clue="",
        environment_ip=[],
        username="",
        password="",
        port=None,
        namespace="",
        cluster_id="",
        environment_mode="",
        artifact_source="",
        pasted_evidence="",
        output_root=".local/incidents",
    )

    assert module.command_start(second_args) == 0

    incident_dir = tmp_path / ".local" / "incidents" / "manual-evidence-continue"
    input_data = load_yaml(incident_dir / "input.yaml")
    intake = load_yaml(incident_dir / "phase1-intake.yaml")
    raw_file = incident_dir / "logs" / "raw" / "manual-evidence.txt"
    assert input_data["manual_evidence_ref"] == "logs/raw/manual-evidence.txt"
    assert intake["manual_evidence"] == {
        "status": "captured",
        "kind": "pasted_text",
        "ref": "logs/raw/manual-evidence.txt",
    }
    assert raw_file.read_text(encoding="utf-8") == "kubectl get pods\npod-a CrashLoopBackOff\n"


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


def test_local_analyse_incident_uses_local_collection(tmp_path, monkeypatch):
    monkeypatch.setenv("MIDSTACK_TRIAGE_WORKSPACE", str(tmp_path))
    incident_dir = tmp_path / ".local" / "incidents" / "mongodb-local-ready"
    incident_dir.mkdir(parents=True)
    write_yaml(
        incident_dir / "input.yaml",
        {
            "incident_id": "mongodb-local-ready",
            "middleware": "mongodb",
            "namespace": "psmdb-test",
            "cluster_id": "",
            "environment_mode": "local",
            "execution_mode": "local",
            "customer_clue": "MongoDB pod is not ready.",
            "scenario": "unknown",
        },
    )
    write_yaml(
        incident_dir / "meta.yaml",
        {
            "incident_id": "mongodb-local-ready",
            "middleware": "mongodb",
            "status": "ready",
            "current_command": "start",
        },
    )
    write_yaml(
        incident_dir / "local-config.yaml",
        {
            "access": {
                "execution_mode": "local",
                "current_context": "prod-cluster",
            }
        },
    )
    remote_run_dir = tmp_path / ".local" / "remote-runs" / "mongodb-local-run"
    script_dir = remote_run_dir / "mongodb.collect.pods.state"
    script_dir.mkdir(parents=True)
    write_yaml(
        script_dir / "context.yaml",
        {
            "incident_id": "mongodb-local-run",
            "middleware": "mongodb",
            "namespace": "psmdb-test",
            "cluster_id": "local-run",
            "topology_type": "unknown",
        },
    )
    write_yaml(
        remote_run_dir / "remote-executor-run.yaml",
        {
            "incident_id": "mongodb-local-run",
            "middleware": "mongodb",
            "status": "success",
            "namespace": "psmdb-test",
            "selected_ip": "local",
            "error": {"code": "", "message": ""},
            "script_results": [
                {
                    "script_id": "mongodb.collect.pods.state",
                    "status": "success",
                    "summary": "pods collected",
                }
            ],
        },
    )
    write_yaml(
        script_dir / "remote-executor-result.yaml",
        {
            "script_id": "mongodb.collect.pods.state",
            "status": "success",
            "process": {"exit_code": 0},
        },
    )
    write_yaml(
        script_dir / "output.yaml",
        {
            "script_id": "mongodb.collect.pods.state",
            "status": "success",
            "summary": "pods collected",
            "structured_record_patch": {
                "details": {
                    "pods": [
                        {
                            "name": "mongo-0",
                            "namespace": "psmdb-test",
                            "status": "Running",
                        }
                    ]
                }
            },
            "signal_bundle_patch": {
                "abnormal_signals": [
                    {
                        "signal_id": "pod-not-ready",
                        "object_ref": "pod/mongo-0",
                    }
                ]
            },
            "collection_report_patch": {
                "successful_items": [
                    {
                        "item": "pods/state",
                        "source": "kubectl",
                    }
                ]
            },
        },
    )
    (script_dir / "remote.stdout.txt").write_text("ok\n", encoding="utf-8")
    calls = []

    def fake_local_collection(args, output_dir, script_ids=None):
        calls.append((args.local_config, args.remote_namespace, script_ids))
        return remote_run_dir

    monkeypatch.setattr(module, "run_local_collection", fake_local_collection)

    args = SimpleNamespace(
        input_dir=None,
        remote_run_dir=None,
        remote_config=None,
        incident_dir=str(incident_dir),
        output_dir=None,
        output_root=".local/incidents",
        scenario=None,
        customer_clue=None,
        remote_output_dir=".local/remote-runs",
        remote_namespace="",
        object_inventory="",
        execution_mode="local",
    )

    assert module.command_analyse(args) == 0

    adapter = load_yaml(incident_dir / "adapter-output.yaml")
    assert adapter["status"] == "completed"
    assert calls == [(str(incident_dir / "local-config.yaml"), "psmdb-test", None)]
    assert (incident_dir / "analysis.yaml").exists()
    assert (incident_dir / "remote-executor-run.yaml").exists()
    record_ref_names = {item["name"] for item in adapter["record_refs"]}
    assert "collection_plan" in record_ref_names
    collection_plan = load_yaml(incident_dir / "collection_plan.yaml")
    assert collection_plan["baseline_script_ids"]
    assert "mongodb.collect.logs.file_tail" in collection_plan["directed_script_ids"]
    collection_report = load_yaml(incident_dir / "collection_report.yaml")
    assert collection_report["collection_coverage"]["summary"]["baseline_collected"] == 1
    assert "mongodb.collect.nodes.state" in collection_report["collection_coverage"]["layers"]["system"]["missing_scripts"]
    signal_bundle = load_yaml(incident_dir / "signal_bundle.yaml")
    assert signal_bundle["signal_groups"] == [
        {
            "layer": "pod",
            "category": "runtime_failure",
            "object_ref": "pod/mongo-0",
            "signals": ["pod-not-ready"],
            "severity": "",
        }
    ]
