import importlib.util
import os
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "collect" / "collect-resource-metrics.sh"
NORMALIZER = ROOT / "domains" / "mongodb" / "scripts" / "normalize" / "normalize-signals-bundle.py"


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def make_fake_kubectl(bin_dir: Path, *, fail_top: bool = False) -> None:
    kubectl = bin_dir / "kubectl"
    if fail_top:
        kubectl.write_text(
            """#!/usr/bin/env bash
if [[ "$1" == "top" ]]; then
  echo 'error: Metrics API not available' >&2
  exit 1
fi
echo "unexpected kubectl args: $*" >&2
exit 1
""",
            encoding="utf-8",
        )
    else:
        kubectl.write_text(
            """#!/usr/bin/env bash
if [[ "$1" == "top" && "$2" == "nodes" ]]; then
  cat <<'EOF'
worker-1  250m  12%  2048Mi  51%
worker-2  1500m  75%  6120Mi  89%
EOF
  exit 0
fi
if [[ "$1" == "top" && "$2" == "pods" ]]; then
  cat <<'EOF'
mongo-0  950m  1536Mi
mongo-1  120m  768Mi
EOF
  exit 0
fi
echo "unexpected kubectl args: $*" >&2
exit 1
""",
            encoding="utf-8",
        )
    kubectl.chmod(0o755)


def run_resource_metrics(tmp_path: Path, *, fail_top: bool = False) -> tuple[subprocess.CompletedProcess, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    make_fake_kubectl(bin_dir, fail_top=fail_top)
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": "mongodb.collect.resources.metrics",
            "namespace": "psmdb-test",
            "capabilities": {"kubectl_available": True},
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
    return proc, output_file


def test_resource_metrics_collects_node_and_pod_top_output(tmp_path):
    proc, output_file = run_resource_metrics(tmp_path)

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    metrics = output["structured_record_patch"]["details"]["resource_metrics"]
    assert output["status"] == "success"
    assert metrics["nodes"][1]["node_ref"] == "worker-2"
    assert metrics["nodes"][1]["cpu_percent"] == 75
    assert metrics["nodes"][1]["memory_percent"] == 89
    assert metrics["pods"][0]["pod_ref"] == "mongo-0"
    assert metrics["pods"][0]["cpu_millicores"] == 950
    assert output["signal_bundle_patch"]["resource_metrics"]["node_count"] == 2
    assert output["collection_report_patch"]["successful_items"][0]["item"] == "resource_metrics"


def test_resource_metrics_partial_when_metrics_api_unavailable(tmp_path):
    proc, output_file = run_resource_metrics(tmp_path, fail_top=True)

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    assert output["status"] == "partial"
    assert output["structured_record_patch"]["details"]["resource_metrics"]["nodes"] == []
    assert output["collection_report_patch"]["evidence_gaps"][0]["gap_type"] == "expected_gap"
    assert "metrics api" in output["collection_report_patch"]["evidence_gaps"][0]["gap"].lower()


def test_resource_metrics_normalizer_emits_resource_pressure_signals():
    spec = importlib.util.spec_from_file_location("normalize_signals_bundle", NORMALIZER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    outputs = {
        "mongodb.collect.resources.metrics": {
            "structured_record_patch": {
                "details": {
                    "resource_metrics": {
                        "nodes": [
                            {
                                "node_ref": "worker-1",
                                "cpu_percent": 91,
                                "memory_percent": 70,
                            }
                        ],
                        "pods": [
                            {
                                "pod_ref": "mongo-0",
                                "cpu_millicores": 1200,
                                "memory_mi": 768,
                            }
                        ],
                    }
                }
            }
        }
    }

    resources = module.resource_metric_signals(outputs)
    signals, _, _ = module.abnormal_signals_from_inventory(
        {"pods": {}, "statefulsets": {}},
        {"warnings": []},
        resources,
    )

    assert {item["signal_id"] for item in signals} == {
        "node-resource-pressure",
        "pod-resource-pressure",
    }
    assert {item["object_ref"] for item in signals} == {
        "node/worker-1",
        "pod/mongo-0",
    }
