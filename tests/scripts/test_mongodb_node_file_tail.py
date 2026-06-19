import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "collect" / "collect-log-node-file-tail.sh"


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def make_fake_kubectl(bin_dir: Path) -> None:
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env python3
import json
import sys

args = sys.argv[1:]
if args[:2] == ["get", "pods"]:
    print(json.dumps({
        "items": [
            {
                "metadata": {
                    "name": "mongo-0",
                    "uid": "pod-uid-1",
                    "labels": {"app": "mongodb"},
                },
                "spec": {
                    "nodeName": "worker-2",
                    "containers": [
                        {
                            "name": "mongodb",
                            "volumeMounts": [
                                {"name": "logs", "mountPath": "/opt/bitnami/mongodb/logs"}
                            ],
                        }
                    ],
                    "volumes": [{"name": "logs", "emptyDir": {}}],
                },
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "False"}],
                    "containerStatuses": [{"restartCount": 4}],
                },
            }
        ]
    }))
    raise SystemExit(0)
if args[:2] == ["get", "nodes"]:
    print(json.dumps({
        "items": [
            {
                "metadata": {"name": "worker-2"},
                "status": {"addresses": [{"type": "InternalIP", "address": "10.0.0.22"}]},
            }
        ]
    }))
    raise SystemExit(0)
print("unexpected kubectl args: %s" % args, file=sys.stderr)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)


def run_node_file_tail(tmp_path: Path, context) -> tuple[subprocess.CompletedProcess, Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    make_fake_kubectl(bin_dir)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(context_file, context)
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bin_dir, os.pathsep, env.get("PATH", ""))
    proc = subprocess.run(
        [
            str(SCRIPT),
            "--context-file",
            str(context_file),
            "--output-file",
            str(output_file),
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=20,
    )
    return proc, output_file, bin_dir


def test_local_node_file_tail_blocks_without_explicit_node_ssh(tmp_path):
    marker = tmp_path / "ssh-attempted"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake_ssh = tmp_path / "bin" / "ssh"
    fake_ssh.write_text("#!/usr/bin/env bash\ntouch %s\nexit 9\n" % marker, encoding="utf-8")
    fake_ssh.chmod(0o755)
    context = {
        "script_id": "mongodb.collect.logs.node_file_tail",
        "namespace": "psmdb-test",
        "access": {"execution_mode": "local", "node_access": {"mode": "kubernetes_api_only", "ssh": {"enabled": False}}},
        "targets": {"pod_refs": ["mongo-0"]},
    }

    proc, output_file, bin_dir = run_node_file_tail(tmp_path, context)

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert output["status"] == "blocked"
    assert "node SSH access is not enabled" in output["summary"]
    assert not marker.exists()


def test_local_node_file_tail_uses_explicit_node_ssh(tmp_path):
    marker = tmp_path / "sshpass-args"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_kubectl(bin_dir)
    sshpass = bin_dir / "sshpass"
    sshpass.write_text(
        "#!/usr/bin/env bash\nprintf '%%s\\n' \"$@\" > %s\nprintf 'FATAL WiredTiger journal corrupted\\n'\n" % marker,
        encoding="utf-8",
    )
    sshpass.chmod(0o755)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": "mongodb.collect.logs.node_file_tail",
            "namespace": "psmdb-test",
            "access": {
                "execution_mode": "local",
                "node_access": {
                    "mode": "ssh",
                    "ssh": {
                        "enabled": True,
                        "username": "node-user",
                        "password": "secret",
                        "port": 2202,
                    },
                },
            },
            "targets": {"pod_refs": ["mongo-0"]},
        },
    )
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bin_dir, os.pathsep, env.get("PATH", ""))

    proc = subprocess.run(
        [
            str(SCRIPT),
            "--context-file",
            str(context_file),
            "--output-file",
            str(output_file),
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    args = marker.read_text(encoding="utf-8")
    assert output["status"] in ("success", "partial")
    assert "-p\n2202" in args
    assert "node-user@10.0.0.22" in args
