import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.transport import FunctionRemoteTransport  # noqa: E402


def test_function_transport_delegates_run_and_copy_operations(tmp_path):
    calls = []

    def run_ssh(access, remote_script, timeout=60):
        calls.append(("run", access["primary_ip"], remote_script, timeout))
        return subprocess.CompletedProcess(["ssh"], 0, "ok", "")

    def scp_to(access, local_path, remote_path):
        calls.append(("copy_to", str(local_path), remote_path))

    def scp_from(access, remote_path, local_path, recursive=False):
        calls.append(("copy_from", remote_path, str(local_path), recursive))

    transport = FunctionRemoteTransport(run_ssh, scp_to, scp_from)
    access = {"primary_ip": "192.0.2.10"}
    local_file = tmp_path / "payload.yaml"
    result = transport.run(access, "echo ok", timeout=12)
    transport.copy_to(access, local_file, "/tmp/payload.yaml")
    transport.copy_from(access, "/tmp/out", tmp_path / "out", recursive=True)

    assert result.stdout == "ok"
    assert calls == [
        ("run", "192.0.2.10", "echo ok", 12),
        ("copy_to", str(local_file), "/tmp/payload.yaml"),
        ("copy_from", "/tmp/out", str(tmp_path / "out"), True),
    ]
