import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "domains" / "mongodb" / "scripts" / "normalize" / "normalize-logs-highlights.py"


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_normalize_logs_highlights_reads_kubernetes_previous_log_artifacts(tmp_path):
    current_dir = tmp_path / "remote-run" / "mongodb.collect.logs.current" / "artifacts" / "raw" / "logs-current"
    previous_dir = tmp_path / "remote-run" / "kubernetes.collect.logs.previous" / "artifacts" / "raw" / "logs-previous"
    current_dir.mkdir(parents=True)
    previous_dir.mkdir(parents=True)
    (current_dir / "mongo-0.log").write_text("current log is quiet\n", encoding="utf-8")
    (previous_dir / "mongo-0.log").write_text("election timeout while stepping down primary\n", encoding="utf-8")
    context_file = tmp_path / "context.yaml"
    output_file = tmp_path / "output.yaml"
    artifact_dir = tmp_path / "artifacts"
    write_yaml(
        context_file,
        {
            "script_id": "mongodb.normalize.logs.highlights",
            "inputs": {
                "log_artifact_dirs": {
                    "current": [str(tmp_path / "remote-run" / "mongodb.collect.logs.current" / "artifacts")],
                    "previous": [
                        str(tmp_path / "remote-run" / "mongodb.collect.logs.previous" / "artifacts"),
                        str(tmp_path / "remote-run" / "kubernetes.collect.logs.previous" / "artifacts"),
                    ],
                }
            },
            "normalize_query": {"per_file_highlight_limit": 10, "total_highlight_limit": 10},
        },
    )

    proc = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--context-file",
            str(context_file),
            "--output-file",
            str(output_file),
            "--artifact-dir",
            str(artifact_dir),
        ],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=20,
    )

    assert proc.returncode == 0, proc.stderr
    output = yaml.safe_load(output_file.read_text(encoding="utf-8"))
    processed = output["structured_record_patch"]["details"]["processed_logs"]

    assert output["status"] == "success"
    assert processed["source_log_file_count"] == 2
    assert any(item["log_type"] == "previous" for item in processed["stats"])
    assert any(item["message"] == "election timeout while stepping down primary" for item in processed["highlights"])
