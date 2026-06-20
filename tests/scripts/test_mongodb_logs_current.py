import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "collect" / "collect-logs-current.sh"


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
            {"metadata": {"name": "mongo-0", "labels": {"app": "mongodb", "role": "shard"}}},
            {"metadata": {"name": "mongo-1", "labels": {"app": "mongodb", "role": "shard"}}},
            {"metadata": {"name": "mongo-2", "labels": {"app": "mongodb", "role": "shard"}}},
        ]
    }))
    raise SystemExit(0)
if args[:1] == ["logs"]:
    pod = args[3]
    print("short log from %s" % pod)
    raise SystemExit(0)
print("unexpected kubectl args: %s" % args, file=sys.stderr)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)


def run_logs_current(tmp_path: Path, script_id: str = "mongodb.collect.logs.current") -> tuple[subprocess.CompletedProcess, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_kubectl(bin_dir)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": script_id,
            "namespace": "psmdb-test",
            "capabilities": {"kubectl_available": True},
            "logs_query": {"tail_lines": 20, "max_targets": 2},
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


def test_logs_current_honors_max_targets_and_records_short_log_policy(tmp_path):
    proc, output_file = run_logs_current(tmp_path)

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    logs = output["structured_record_patch"]["details"]["raw_logs"]
    gap = output["collection_report_patch"]["evidence_gaps"][0]

    assert [item["pod_ref"] for item in logs] == ["mongo-0", "mongo-1"]
    assert output["collection_report_patch"]["collection_actions"][0]["sample_policy"] == {
        "tail_lines": 20,
        "max_targets": 2,
        "candidate_count": 3,
        "selected_count": 2,
    }
    assert gap["gap_type"] == "critical_gap"
    assert gap["gap_category"] == "log_sample_quality"
    assert gap["sample_policy"]["tail_lines"] == 20
    assert gap["sample_policy"]["max_targets"] == 2
    assert gap["recommended_action"] == "run mongodb.collect.logs.discover_sink to inspect MongoDB log destination and path"


def test_kubernetes_logs_current_uses_domain_neutral_short_log_gap(tmp_path):
    proc, output_file = run_logs_current(tmp_path, "kubernetes.collect.logs.current")

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    gap = output["collection_report_patch"]["evidence_gaps"][0]

    assert output["script_id"] == "kubernetes.collect.logs.current"
    assert output["collection_report_patch"]["collection_actions"][0]["method"] == "kubectl logs"
    assert "MongoDB" not in gap["gap"]
    assert "MongoDB" not in gap["why_important"]
    assert "mongodb.collect.logs.discover_sink" not in gap.get("recommended_action", "")
    assert gap["recommended_action"] == "inspect domain-specific log sink when container stdout/stderr is insufficient"
