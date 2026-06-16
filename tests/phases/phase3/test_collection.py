import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "active" / "mongodb"

from phases.phase3 import collection as phase3_collection


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_normalize_collection_report_gaps_assigns_gap_types():
    collection_report = {
        "evidence_gaps": [
            "application log source is unknown; kubectl logs too short",
            {"gap": "peer describe output not collected yet"},
        ]
    }

    phase3_collection.normalize_collection_report_gaps(collection_report)

    assert collection_report["evidence_gaps"][0]["gap_type"] == "critical_gap"
    assert collection_report["evidence_gaps"][1]["gap_type"] == "expected_gap"
    assert collection_report["evidence_gaps"][0]["related_stage"] == "signal_collection"


def test_apply_scenario_routing_sets_unknown_scenario(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "input.yaml",
        {
            "middleware": "mongodb",
            "scenario": "unknown",
            "customer_clue": "mongos connection timeout and connection refused",
        },
    )
    fixture_root = FIXTURE_ROOT / "connection-failure-sample"
    write_yaml(output_dir / "signal_bundle.yaml", yaml.safe_load((fixture_root / "signal_bundle.yaml").read_text(encoding="utf-8")))
    write_yaml(output_dir / "structured_record.yaml", yaml.safe_load((fixture_root / "structured_record.yaml").read_text(encoding="utf-8")))

    args = SimpleNamespace(customer_clue="")
    updated = phase3_collection.apply_scenario_routing_if_needed(output_dir, args)

    assert updated["scenario"] == "connection-failure"
    assert updated["scenario_inference"]["confidence"] in ("high", "medium")
    assert args.scenario == "connection-failure"


def test_enrich_skill_runtime_context_records_missing_scripts(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "input.yaml",
        {
            "middleware": "mongodb",
            "scenario": "kubernetes-runtime",
        },
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {
            "collection_actions": [],
            "successful_items": [{"item": "remote-executor/mongodb.collect.pods.state"}],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": [],
        },
    )

    runtime = phase3_collection.enrich_skill_runtime_context(
        output_dir,
        {"middleware": "mongodb", "scenario": "kubernetes-runtime"},
    )

    assert "mongodb-triage-kubernetes-runtime-failure" in runtime["skills"][0]["id"]
    assert "mongodb.collect.pods.state" in runtime["required_scripts"]
    assert "mongodb.collect.dns.coredns" in runtime["missing_or_failed"]

    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))
    skill_check = collection_report["skill_evidence_check"]
    assert "mongodb.collect.pods.state" in skill_check["script_statuses"]
    assert "mongodb.collect.dns.coredns" in skill_check["missing_or_failed"]


def test_directed_recollection_prefers_dns_path_and_skill_pool(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "structured_record.yaml",
        {
            "details": {
                "raw_logs": [],
            }
        },
    )
    write_yaml(
        output_dir / "signal_bundle.yaml",
        {
            "abnormal_signals": [
                {"signal_id": "dns-resolution-failed"},
                {"signal_id": "pod-crashloop", "object_ref": "pod/bnmongo-shard0-data-0"},
            ]
        },
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {
            "collection_actions": [],
            "successful_items": [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": [
                {"gap": "lookup on 10.96.0.10:53 read udp connection refused"},
            ],
        },
    )

    selected = phase3_collection.directed_recollection_script_ids(
        output_dir,
        skill_pool={
            phase3_collection.SCRIPT_DNS_COREDNS,
            phase3_collection.SCRIPT_NETWORK_OVERLAY,
        },
    )

    assert selected == [
        phase3_collection.SCRIPT_DNS_COREDNS,
        phase3_collection.SCRIPT_NETWORK_OVERLAY,
    ]


def test_directed_recollection_falls_back_when_skill_pool_misses(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "structured_record.yaml", {"details": {}})
    write_yaml(
        output_dir / "signal_bundle.yaml",
        {
            "abnormal_signals": [
                {"signal_id": "pod-crashloop", "object_ref": "pod/bnmongo-shard0-data-0"},
            ]
        },
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {
            "collection_actions": [],
            "successful_items": [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": [
                {"gap": "application log source is unknown; kubectl logs too short"},
            ],
        },
    )

    selected = phase3_collection.directed_recollection_script_ids(output_dir, skill_pool={"mongodb.collect.pods.state"})

    assert phase3_collection.SCRIPT_LOG_SINK_DISCOVER in selected
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))
    assert "skill_pool_miss" in collection_report["warnings"][0]


def test_run_remote_collection_invokes_execution_module(tmp_path, monkeypatch):
    output_dir = tmp_path / "incident"
    remote_output_dir = tmp_path / "remote-runs"
    remote_run_dir = remote_output_dir / "mongodb-remote-run-20260614-000000"
    remote_run_dir.mkdir(parents=True, exist_ok=True)
    remote_config = tmp_path / "remote.yaml"
    remote_config.write_text("access: {}\n", encoding="utf-8")
    captured = {}

    def fake_run(command, env, stdout, stderr, universal_newlines, timeout):
        captured["command"] = command
        captured["env"] = env

        class Result:
            returncode = 0
            stdout = "local_dir=%s\n" % remote_run_dir
            stderr = ""

        return Result()

    monkeypatch.setattr(phase3_collection.subprocess, "run", fake_run)
    args = SimpleNamespace(
        remote_config=str(remote_config),
        remote_output_dir=str(remote_output_dir),
        remote_namespace="",
        object_inventory="",
    )

    result = phase3_collection.run_remote_collection(args, output_dir)

    assert result == remote_run_dir
    assert captured["command"][:3] == [sys.executable, "-m", "execution.remote.executor"]
    assert str(ROOT / "src") in captured["env"]["PYTHONPATH"].split(":")[0]
