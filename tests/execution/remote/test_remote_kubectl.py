import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.kubectl import kubectl_scope, run_remote_kubectl_json  # noqa: E402


def test_kubectl_scope_defaults_to_all_namespaces_when_namespace_missing():
    assert kubectl_scope("", namespaced=True) == "-A"
    assert kubectl_scope("psmdb-test", namespaced=True) == "-n psmdb-test"
    assert kubectl_scope("", namespaced=False) == ""


def test_run_remote_kubectl_json_returns_payload():
    calls = []

    def fake_run_env_check(access, command):
        calls.append((access, command))
        return {"status": "passed", "stdout": '{"items": [{"metadata": {"name": "pod-0"}}]}'}

    result = run_remote_kubectl_json({"primary_ip": "127.0.0.1"}, "pods", "psmdb-test", run_env_check_fn=fake_run_env_check)

    assert result == {"status": "passed", "resource": "pods", "payload": {"items": [{"metadata": {"name": "pod-0"}}]}}
    assert calls == [({"primary_ip": "127.0.0.1"}, "kubectl get pods -n psmdb-test -o json")]


def test_run_remote_kubectl_json_reports_invalid_json():
    def fake_run_env_check(access, command):
        return {"status": "passed", "stdout": "not-json"}

    result = run_remote_kubectl_json({"primary_ip": "127.0.0.1"}, "pods", "", run_env_check_fn=fake_run_env_check)

    assert result["status"] == "failed"
    assert result["resource"] == "pods"
    assert result["error"]["stdout"] == "not-json"
