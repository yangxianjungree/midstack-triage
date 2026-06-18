import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from execution.remote.transport import FunctionRemoteTransport, LocalTransport  # noqa: E402


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


def test_local_transport_runs_commands_and_copies_files(tmp_path):
    transport = LocalTransport()
    source = tmp_path / "source.yaml"
    source.write_text("ok: true\n", encoding="utf-8")
    staged = tmp_path / "workspace" / "source.yaml"

    transport.copy_to({}, source, str(staged))
    result = transport.run({}, "cat %s" % staged, timeout=12)
    copied = tmp_path / "copied.yaml"
    transport.copy_from({}, str(staged), copied)

    assert result.returncode == 0
    assert result.stdout == "ok: true\n"
    assert copied.read_text(encoding="utf-8") == "ok: true\n"


def test_local_transport_copies_directories_recursively(tmp_path):
    transport = LocalTransport()
    source_dir = tmp_path / "workspace" / "artifacts"
    source_dir.mkdir(parents=True)
    (source_dir / "pods.json").write_text("{}\n", encoding="utf-8")
    dest_dir = tmp_path / "out" / "artifacts"

    transport.copy_from({}, str(source_dir), dest_dir, recursive=True)

    assert (dest_dir / "pods.json").read_text(encoding="utf-8") == "{}\n"
