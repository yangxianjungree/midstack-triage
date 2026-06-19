import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "collect" / "collect-pods-state.sh"


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
                    "namespace": "psmdb-test",
                    "labels": {"app": "mongodb"},
                    "ownerReferences": [{"kind": "StatefulSet", "name": "mongo"}],
                },
                "spec": {
                    "nodeName": "worker-1",
                    "containers": [
                        {
                            "name": "mongodb",
                            "resources": {
                                "requests": {"cpu": "500m", "memory": "1Gi"},
                                "limits": {"cpu": "2", "memory": "4Gi"},
                            },
                        },
                        {
                            "name": "metrics",
                            "resources": {
                                "requests": {"cpu": "50m", "memory": "64Mi"},
                            },
                        },
                    ],
                },
                "status": {
                    "phase": "Running",
                    "podIP": "10.244.1.20",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [
                        {"name": "mongodb", "ready": True, "restartCount": 0, "state": {"running": {}}},
                        {"name": "metrics", "ready": True, "restartCount": 0, "state": {"running": {}}},
                    ],
                },
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


def run_pods_state(tmp_path: Path) -> tuple[subprocess.CompletedProcess, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_kubectl(bin_dir)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": "mongodb.collect.pods.state",
            "namespace": "psmdb-test",
            "capabilities": {"kubectl_available": True},
            "pod_query": {"mode": "by_namespace_scan"},
        },
    )
    env = dict(os.environ)
    env["PATH"] = "%s%s%s" % (bin_dir, os.pathsep, env.get("PATH", ""))
    proc = subprocess.run(
        [
            "bash",
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
    return proc, output_file


def test_pods_state_records_resource_requests_and_limits(tmp_path):
    proc, output_file = run_pods_state(tmp_path)

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    pod = output["structured_record_patch"]["details"]["pods"][0]
    profile = pod["resource_profile"]

    assert profile["requests"]["cpu_millicores"] == 550
    assert profile["requests"]["memory_mi"] == 1088
    assert profile["limits"]["cpu_millicores"] == 2000
    assert profile["limits"]["memory_mi"] == 4096
    assert profile["containers"][0]["name"] == "mongodb"
    assert profile["containers"][0]["requests"]["memory_mi"] == 1024
    assert pod["yaml"]["spec"]["containers"][0]["resources"]["limits"]["memory"] == "4Gi"
