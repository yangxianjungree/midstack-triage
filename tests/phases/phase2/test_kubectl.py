import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase2 import kubectl as phase2_kubectl


def test_run_remote_kubectl_json_returns_payload(monkeypatch):
    calls = []

    def fake_run_env_check(access, command):
        calls.append((access, command))
        return {"status": "passed", "stdout": '{"items": [{"metadata": {"name": "pod-0"}}]}'}

    monkeypatch.setattr(phase2_kubectl, "run_env_check", fake_run_env_check)

    result = phase2_kubectl.run_remote_kubectl_json({"primary_ip": "127.0.0.1"}, "pods", "psmdb-test")

    assert result == {"status": "passed", "resource": "pods", "payload": {"items": [{"metadata": {"name": "pod-0"}}]}}
    assert calls == [({"primary_ip": "127.0.0.1"}, "kubectl get pods -n psmdb-test -o json")]


def test_run_remote_kubectl_json_reports_invalid_json(monkeypatch):
    def fake_run_env_check(access, command):
        return {"status": "passed", "stdout": "not-json"}

    monkeypatch.setattr(phase2_kubectl, "run_env_check", fake_run_env_check)

    result = phase2_kubectl.run_remote_kubectl_json({"primary_ip": "127.0.0.1"}, "pods", "")

    assert result["status"] == "failed"
    assert result["resource"] == "pods"
    assert result["error"]["stdout"] == "not-json"
