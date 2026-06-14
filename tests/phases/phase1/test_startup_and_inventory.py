import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase1 import startup as phase1_startup
from phases.phase2 import inventory as phase2_inventory


def test_validate_remote_environment_stops_on_first_failure(monkeypatch):
    calls = []

    def fake_run_env_check(access, command):
        calls.append(command)
        return {"status": "passed" if command == "echo ok" else "failed", "stdout": "", "stderr": ""}

    monkeypatch.setattr(phase1_startup, "run_env_check", fake_run_env_check)
    result = phase1_startup.validate_remote_environment({"username": "root", "primary_ip": "127.0.0.1", "password": "x", "port": 22})

    assert result["status"] == "failed"
    assert calls == ["echo ok", "kubectl version --client=true >/dev/null"]


def test_discover_mongodb_inventory_auto_discovers_namespace(monkeypatch):
    def fake_run_remote_kubectl_json(access, resource, namespace, namespaced=True):
        if resource == "pods":
            return {
                "status": "passed",
                "resource": resource,
                "payload": {
                    "items": [
                        {
                            "metadata": {"name": "bnmongo-mongos-0", "namespace": "psmdb-test"},
                            "spec": {"containers": [{"name": "mongos"}]},
                            "status": {"phase": "Running"},
                        }
                    ]
                },
            }
        return {"status": "passed", "resource": resource, "payload": {"items": []}}

    monkeypatch.setattr(phase2_inventory, "run_remote_kubectl_json", fake_run_remote_kubectl_json)
    inventory = phase2_inventory.discover_mongodb_inventory({"primary_ip": "127.0.0.1"}, "")

    assert inventory["status"] == "passed"
    assert inventory["selected_namespace"] == "psmdb-test"
    assert inventory["targets"]["mongos_pod_ref"] == "bnmongo-mongos-0"
