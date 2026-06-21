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
    assert module.DEFAULT_RUNTIME_MAP == runtime_root / "core" / "interfaces" / "plugin" / "script-runtime-map.example.yaml"

    monkeypatch.delenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", raising=False)
    importlib.reload(module)


def test_source_checkout_root_points_to_repo_root(monkeypatch):
    monkeypatch.delenv("MIDSTACK_TRIAGE_RUNTIME_ROOT", raising=False)
    module = importlib.import_module("execution.remote.runtime_support")
    module = importlib.reload(module)

    assert module.ROOT == ROOT
    assert module.DEFAULT_MANIFEST == ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml"
    assert module.DEFAULT_RUNTIME_MAP == ROOT / "core" / "interfaces" / "plugin" / "script-runtime-map.example.yaml"


def test_load_config_reads_yaml_object(tmp_path):
    module = importlib.import_module("execution.remote.runtime_support")
    target = tmp_path / "config.yaml"
    target.write_text(yaml.safe_dump({"status": "ok"}), encoding="utf-8")

    assert module.load_config(target) == {"status": "ok"}


def test_load_script_entries_resolves_scripts_from_multiple_manifests(tmp_path):
    module = importlib.import_module("execution.remote.runtime_support")
    mongodb_manifest = tmp_path / "domains" / "mongodb" / "scripts" / "manifest.yaml"
    kubernetes_manifest = tmp_path / "domains" / "kubernetes" / "scripts" / "manifest.yaml"
    runtime_map = tmp_path / "core" / "interfaces" / "plugin" / "script-runtime-map.example.yaml"
    mongodb_script = mongodb_manifest.parent / "collect" / "collect-pods-state.sh"
    kubernetes_script = kubernetes_manifest.parent / "collect" / "collect-logs-current.sh"
    mongodb_script.parent.mkdir(parents=True)
    kubernetes_script.parent.mkdir(parents=True)
    runtime_map.parent.mkdir(parents=True)
    mongodb_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    kubernetes_script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    mongodb_manifest.write_text(
        yaml.safe_dump(
            {
                "middleware": "mongodb",
                "scripts": [
                    {
                        "script_id": "mongodb.collect.pods.state",
                        "source": "collect/collect-pods-state.sh",
                        "runtime": "shell",
                        "readonly": True,
                        "default_packaged": True,
                        "mvp": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    kubernetes_manifest.write_text(
        yaml.safe_dump(
            {
                "middleware": "kubernetes",
                "scripts": [
                    {
                        "script_id": "kubernetes.collect.logs.current",
                        "source": "collect/collect-logs-current.sh",
                        "runtime": "shell",
                        "readonly": True,
                        "default_packaged": True,
                        "mvp": True,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    runtime_map.write_text(
        yaml.safe_dump(
            {
                "scripts": [
                    {
                        "script_id": "kubernetes.collect.logs.current",
                        "runtime_path": "assets/scripts/kubernetes/collect-logs-current.sh",
                        "runtime": "shell",
                        "readonly": True,
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    entries = module.load_script_entries([mongodb_manifest, kubernetes_manifest], runtime_map, ["kubernetes.collect.logs.current"])

    assert len(entries) == 1
    assert entries[0]["script_id"] == "kubernetes.collect.logs.current"
    assert entries[0]["source_path"] == kubernetes_script


def test_local_access_from_config_defaults_node_access():
    cli = importlib.import_module("execution.remote.cli")

    access = cli._local_access_from_config({"context": {"current_context": "prod-cluster"}})

    assert access["execution_mode"] == "local"
    assert access["primary_ip"] == "local"
    assert access["current_context"] == "prod-cluster"
    assert access["node_access"] == {
        "mode": "kubernetes_api_only",
        "ssh": {"enabled": False, "auth_preference": "key_or_agent"},
    }


def test_local_access_from_config_preserves_explicit_node_ssh():
    cli = importlib.import_module("execution.remote.cli")

    access = cli._local_access_from_config(
        {
            "access": {
                "node_access": {
                    "mode": "ssh",
                    "ssh": {
                        "enabled": True,
                        "auth_preference": "password",
                        "username": "node-user",
                        "password": "secret",
                        "port": 2202,
                    },
                }
            }
        }
    )

    assert access["node_access"]["ssh"]["enabled"] is True
    assert access["node_access"]["ssh"]["auth_preference"] == "password"
    assert access["node_access"]["ssh"]["username"] == "node-user"
    assert access["node_access"]["ssh"]["port"] == 2202


def test_run_result_records_transport():
    contracts = importlib.import_module("execution.remote.contracts")

    result = contracts.build_run_result(
        "incident-1",
        "midstack-triage",
        "local",
        "local",
        "mongo",
        "2026-06-19T00:00:00+08:00",
        [],
        [],
        {"code": "", "message": ""},
        [],
        "success",
    )

    assert result["transport"] == "local"
