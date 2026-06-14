import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote import access as remote_access


def test_validate_remote_environment_stops_on_first_failure(monkeypatch):
    calls = []

    def fake_run_env_check(access, command):
        calls.append(command)
        return {"status": "passed" if command == "echo ok" else "failed", "stdout": "", "stderr": ""}

    monkeypatch.setattr(remote_access, "run_env_check", fake_run_env_check)
    result = remote_access.validate_remote_environment({"username": "root", "primary_ip": "127.0.0.1", "password": "x", "port": 22})

    assert result["status"] == "failed"
    assert calls == ["echo ok", "kubectl version --client=true >/dev/null"]
