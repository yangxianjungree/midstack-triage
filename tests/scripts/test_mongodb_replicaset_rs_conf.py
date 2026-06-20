import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "collect" / "collect-replicaset-rs-status.sh"


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
pod = {
    "metadata": {
        "name": "mongo-shard0-0",
        "labels": {"component": "shard"},
    },
    "spec": {"containers": [{"name": "mongodb"}]},
    "status": {"phase": "Running", "conditions": [{"type": "Ready", "status": "True"}]},
}
if args[:2] == ["get", "pods"]:
    print(json.dumps({"items": [pod]}))
    raise SystemExit(0)
if args[:2] == ["get", "pod"]:
    print(json.dumps(pod))
    raise SystemExit(0)
if args[:1] == ["exec"]:
    joined = " ".join(args)
    if "command -v" in joined:
        print("mongosh")
        raise SystemExit(0)
    if "rs.conf" in joined:
        print(json.dumps({
            "_id": "rs0",
            "version": 8,
            "term": 72,
            "protocolVersion": 1,
            "members": [
                {"_id": 0, "host": "mongo-shard0-0:27017", "priority": 1, "votes": 1},
                {"_id": 1, "host": "mongo-shard0-1:27017", "priority": 1, "votes": 1},
            ],
            "settings": {"chainingAllowed": True},
            "ok": 1,
        }))
        raise SystemExit(0)
print("unexpected kubectl args: %s" % args, file=sys.stderr)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)


def test_replicaset_rs_conf_collects_config_records(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_kubectl(bin_dir)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": "mongodb.collect.replicaset.rs_conf",
            "namespace": "psmdb-test",
            "capabilities": {"kubectl_available": True, "kubectl_exec_available": True},
            "targets": {"namespace": "psmdb-test"},
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

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    configs = output["structured_record_patch"]["details"]["replica_configs"]
    assert output["script_id"] == "mongodb.collect.replicaset.rs_conf"
    assert output["status"] == "success"
    assert configs[0]["source_method"] == "rs.conf"
    assert configs[0]["replica_set_id"] == "rs0"
    assert configs[0]["version"] == 8
    assert configs[0]["members"][0]["host"] == "mongo-shard0-0:27017"
    assert output["collection_report_patch"]["collection_actions"][0]["method"] == "kubectl exec + rs.conf"
