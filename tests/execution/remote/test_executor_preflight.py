import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.executor_preflight import validate_executor_capabilities  # noqa: E402


def test_local_executor_preflight_skips_sshpass_and_checks_local_kubectl():
    commands = []

    def run_local(access, script, timeout=60):
        commands.append(script)
        if script == "kubectl auth can-i create pods/exec -A":
            return subprocess.CompletedProcess(["bash"], 0, "yes\n", "")
        return subprocess.CompletedProcess(["bash"], 0, "", "")

    ok, checks, error = validate_executor_capabilities(
        {"execution_mode": "local"},
        run_ssh_fn=run_local,
        which_fn=lambda _name: None,
    )

    assert ok is True
    assert error == {"code": "", "message": ""}
    assert checks[0]["name"] == "local_shell"
    assert "sshpass" not in [item["name"] for item in checks]
    assert commands == [
        "echo ok",
        "kubectl version --client=true >/dev/null",
        "kubectl get nodes -o name >/dev/null",
        "kubectl auth can-i create pods/exec -A",
    ]
