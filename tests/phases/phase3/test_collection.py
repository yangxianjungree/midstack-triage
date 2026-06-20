import sys
from pathlib import Path
from types import SimpleNamespace

import yaml

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "active" / "mongodb"

from phases.phase3 import incident_build as phase3_incident_build
from phases.phase3 import collection_plan as phase3_collection_plan
from phases.phase3 import recollection as phase3_recollection
from phases.phase3 import recollection_run as phase3_recollection_run
from phases.phase3 import remote_collection as phase3_remote_collection
from phases.phase3 import remote_run as phase3_remote_run
from phases.phase3 import report_gaps as phase3_report_gaps
from phases.phase3 import scenario_routing as phase3_scenario_routing
from phases.phase3 import signal_governance as phase3_signal_governance
from phases.phase3 import skill_runtime as phase3_skill_runtime
from shared.analysis_runtime import apply_analysis_guardrails


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

    phase3_report_gaps.normalize_collection_report_gaps(collection_report)

    assert collection_report["evidence_gaps"][0]["gap_type"] == "critical_gap"
    assert collection_report["evidence_gaps"][1]["gap_type"] == "expected_gap"
    assert collection_report["evidence_gaps"][0]["related_stage"] == "signal_collection"


def test_build_baseline_collection_plan_classifies_layers_and_costs():
    manifest = {
        "middleware": "mongodb",
        "scripts": [
            {
                "script_id": "mongodb.collect.nodes.state",
                "phase": "collect",
                "target": "nodes",
                "readonly": True,
                "default_packaged": True,
                "mvp": True,
                "collection_tier": "baseline",
                "signal_layer": "system",
                "cost_class": "low",
                "noise_class": "low",
            },
            {
                "script_id": "mongodb.collect.events.yaml",
                "phase": "collect",
                "target": "events",
                "readonly": True,
                "default_packaged": True,
                "mvp": True,
                "collection_tier": "baseline",
                "signal_layer": "orchestration",
                "cost_class": "medium",
                "noise_class": "medium",
            },
            {
                "script_id": "mongodb.collect.logs.current",
                "phase": "collect",
                "target": "logs",
                "readonly": True,
                "default_packaged": True,
                "mvp": True,
                "collection_tier": "baseline",
                "signal_layer": "logs",
                "cost_class": "medium",
                "noise_class": "high",
                "sample_policy": {"tail_lines": 1000, "max_targets": 8},
            },
            {
                "script_id": "mongodb.collect.logs.file_tail",
                "phase": "collect",
                "target": "logs",
                "readonly": True,
                "default_packaged": True,
                "mvp": False,
                "collection_tier": "directed",
                "signal_layer": "logs",
                "cost_class": "high",
                "noise_class": "high",
                "trigger_policy": "only after log sink gap",
            },
        ],
    }

    plan = phase3_collection_plan.build_collection_plan(manifest)

    baseline_ids = [item["script_id"] for item in plan["baseline_scripts"]]
    directed_ids = [item["script_id"] for item in plan["directed_scripts"]]
    assert baseline_ids == [
        "mongodb.collect.nodes.state",
        "mongodb.collect.events.yaml",
        "mongodb.collect.logs.current",
    ]
    assert directed_ids == ["mongodb.collect.logs.file_tail"]
    assert plan["layer_summary"]["system"]["baseline_count"] == 1
    assert plan["layer_summary"]["orchestration"]["baseline_count"] == 1
    assert plan["layer_summary"]["logs"]["baseline_count"] == 1
    assert plan["resource_budget"]["baseline_cost_classes"] == {"low": 1, "medium": 2}
    assert plan["resource_budget"]["baseline_high_noise_count"] == 1
    assert plan["baseline_scripts"][2]["sample_policy"] == {"tail_lines": 1000, "max_targets": 8}


def test_write_collection_plan_loads_mongodb_manifest(tmp_path):
    output_dir = tmp_path / "incident"

    plan = phase3_collection_plan.write_collection_plan(output_dir, "mongodb")
    written = yaml.safe_load((output_dir / "collection_plan.yaml").read_text(encoding="utf-8"))

    assert written["middleware"] == "mongodb"
    assert written["baseline_script_ids"] == [item["script_id"] for item in written["baseline_scripts"]]
    assert "mongodb.collect.nodes.state" in written["baseline_script_ids"]
    assert "mongodb.collect.logs.file_tail" in [item["script_id"] for item in written["directed_scripts"]]
    assert written["resource_budget"]["baseline_high_noise_count"] >= 1
    assert plan["generated_at"] == written["generated_at"]


def test_collection_coverage_reports_layer_gaps_from_plan_and_statuses():
    plan = {
        "baseline_scripts": [
            {"script_id": "mongodb.collect.nodes.state", "signal_layer": "system", "tier": "baseline"},
            {"script_id": "mongodb.collect.events.yaml", "signal_layer": "orchestration", "tier": "baseline"},
            {"script_id": "mongodb.collect.logs.current", "signal_layer": "logs", "tier": "baseline"},
        ],
        "directed_scripts": [
            {"script_id": "mongodb.collect.logs.file_tail", "signal_layer": "logs", "tier": "directed"},
            {"script_id": "mongodb.collect.dns.coredns", "signal_layer": "network", "tier": "directed"},
        ],
    }
    statuses = {
        "mongodb.collect.nodes.state": "success",
        "mongodb.collect.events.yaml": "failed",
        "mongodb.collect.logs.current": "partial",
    }

    coverage = phase3_collection_plan.build_collection_coverage(plan, statuses)

    assert coverage["summary"] == {
        "baseline_expected": 3,
        "baseline_collected": 2,
        "baseline_missing": 1,
        "directed_deferred": 2,
    }
    assert coverage["layers"]["system"]["collected_scripts"] == ["mongodb.collect.nodes.state"]
    assert coverage["layers"]["orchestration"]["missing_scripts"] == ["mongodb.collect.events.yaml"]
    assert coverage["layers"]["logs"]["collected_scripts"] == ["mongodb.collect.logs.current"]
    assert coverage["layers"]["logs"]["directed_deferred_scripts"] == ["mongodb.collect.logs.file_tail"]
    assert coverage["layers"]["network"]["directed_deferred_scripts"] == ["mongodb.collect.dns.coredns"]


def test_write_collection_coverage_updates_collection_report(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "collection_plan.yaml",
        {
            "baseline_scripts": [
                {"script_id": "mongodb.collect.nodes.state", "signal_layer": "system", "tier": "baseline"},
                {"script_id": "mongodb.collect.logs.current", "signal_layer": "logs", "tier": "baseline"},
            ],
            "directed_scripts": [
                {"script_id": "mongodb.collect.logs.file_tail", "signal_layer": "logs", "tier": "directed"},
            ],
        },
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {
            "collection_actions": [],
            "successful_items": [{"item": "remote-executor/mongodb.collect.nodes.state"}],
            "failed_items": [{"item": "remote-executor/mongodb.collect.logs.current"}],
            "blank_items": [],
            "evidence_gaps": [],
        },
    )

    coverage = phase3_collection_plan.write_collection_coverage(output_dir)
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))

    assert collection_report["collection_coverage"] == coverage
    assert collection_report["collection_coverage"]["summary"]["baseline_missing"] == 1
    assert collection_report["collection_coverage"]["layers"]["logs"]["missing_scripts"] == ["mongodb.collect.logs.current"]
    assert collection_report["evidence_gaps"] == [
        {
            "gap": "baseline logs collection missing: mongodb.collect.logs.current",
            "gap_type": "critical_gap",
            "gap_category": "coverage_gap",
            "related_stage": "signal_collection",
            "signal_layer": "logs",
            "missing_scripts": ["mongodb.collect.logs.current"],
            "why_important": "Missing baseline logs evidence limits runtime and root-cause validation.",
            "recommended_action": "rerun live collection or inspect remote executor output for the missing baseline scripts",
        }
    ]


def test_write_collection_coverage_does_not_create_gaps_without_live_script_statuses(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "collection_plan.yaml",
        {
            "baseline_scripts": [
                {"script_id": "mongodb.collect.nodes.state", "signal_layer": "system", "tier": "baseline"},
            ],
            "directed_scripts": [],
        },
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {
            "collection_actions": [],
            "successful_items": [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": [],
        },
    )

    phase3_collection_plan.write_collection_coverage(output_dir)
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))

    assert collection_report["collection_coverage"]["summary"]["baseline_missing"] == 1
    assert collection_report["evidence_gaps"] == []


def test_coverage_gap_caps_unsupported_high_root_cause_confidence():
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB failed because runtime evidence is incomplete.",
            "confidence": "high",
            "deepest_supported_level": "root_cause",
            "primary_cause_category": "mongodb-runtime",
            "limitations": [],
        }
    }
    collection_report = {
        "evidence_gaps": [
            {
                "gap": "baseline logs collection missing: mongodb.collect.logs.current",
                "gap_type": "critical_gap",
                "gap_category": "coverage_gap",
            }
        ]
    }

    changed = apply_analysis_guardrails(analysis, collection_report, {"abnormal_signals": []})

    assert changed is True
    assert analysis["conclusion_summary"]["confidence"] == "medium"
    assert analysis["conclusion_summary"]["limitations"][0]["gap_type"] == "critical_gap"


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
    updated = phase3_scenario_routing.apply_scenario_routing_if_needed(output_dir, args)

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

    runtime = phase3_skill_runtime.enrich_skill_runtime_context(
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


def test_resolve_skill_runtime_returns_pure_context(tmp_path):
    output_dir = tmp_path / "incident"
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
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))

    runtime = phase3_skill_runtime.resolve_skill_runtime(
        {"middleware": "mongodb", "scenario": "kubernetes-runtime"},
        output_dir,
        collection_report,
    )

    assert runtime["skills"][0]["id"] == "mongodb-triage-kubernetes-runtime-failure"
    assert "mongodb.collect.pods.state" in runtime["required_scripts"]
    assert "mongodb.collect.dns.coredns" in runtime["missing_or_failed"]
    assert "mongodb.collect.pods.state" in runtime["script_statuses"]
    assert "skill_evidence_check" not in collection_report


def test_resolve_skill_runtime_merges_unresolved_candidate_scenarios(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "collection_report.yaml", {"collection_actions": [], "successful_items": [], "failed_items": [], "blank_items": []})
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))

    runtime = phase3_skill_runtime.resolve_skill_runtime(
        {
            "middleware": "mongodb",
            "scenario": "kubernetes-runtime",
            "scenario_inference": {
                "unresolved": True,
                "candidates": [
                    {"scenario": "kubernetes-runtime", "score": 1.0},
                    {"scenario": "replica-inconsistency", "score": 0.95},
                ],
            },
        },
        output_dir,
        collection_report,
    )

    skill_ids = {skill["id"] for skill in runtime["skills"]}
    assert "mongodb-triage-kubernetes-runtime-failure" in skill_ids
    assert "mongodb-triage-replica-member-not-healthy" in skill_ids
    assert "mongodb.collect.replicaset.rs_status" in runtime["required_scripts"]
    assert "mongodb.collect.dns.coredns" in runtime["skill_pool"]


def test_signal_governance_groups_multilayer_signals_and_correlates_pods_to_nodes(tmp_path):
    output_dir = tmp_path / "incident"
    structured_record = {
        "details": {
            "pods": [
                {
                    "name": "mongo-0",
                    "namespace": "psmdb-test",
                    "node_ref": "node-a",
                    "phase": "Running",
                    "ready": False,
                }
            ],
            "nodes": [
                {
                    "name": "node-a",
                    "status_hint": "pressure",
                    "conditions": [{"type": "MemoryPressure", "status": "True"}],
                }
            ],
            "replica_members": [
                {
                    "replica_set_id": "shard-01-rs",
                    "source_pod_ref": "mongo-0",
                    "self_member": {"state_str": "RECOVERING", "health": 1},
                }
            ],
        }
    }
    signal_bundle = {
        "abnormal_signals": [
            {"signal_id": "node-memory-pressure", "severity": "high", "object_ref": "node/node-a"},
            {"signal_id": "pod-not-ready", "severity": "high", "object_ref": "pod/mongo-0"},
            {"signal_id": "replica-member-recovering", "severity": "high", "object_ref": "replicaset/shard-01-rs"},
        ]
    }

    governance = phase3_signal_governance.build_signal_governance(structured_record, signal_bundle)

    assert {item["layer"] for item in governance["signal_groups"]} == {"node", "pod", "service"}
    assert {
        (item["type"], item["from"], item["to"])
        for item in governance["correlations"]
    } >= {
        ("co_location", "pod/mongo-0", "node/node-a"),
        ("service_pod_source", "replicaset/shard-01-rs", "pod/mongo-0"),
    }


def test_signal_governance_adds_resource_pressure_context():
    structured_record = {
        "details": {
            "pods": [
                {
                    "name": "mongo-0",
                    "namespace": "psmdb-test",
                    "node_ref": "worker-1",
                    "resource_profile": {
                        "requests": {"cpu_millicores": 500, "memory_mi": 1024},
                        "limits": {"cpu_millicores": 2000, "memory_mi": 4096},
                    },
                }
            ],
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
                        "namespace": "psmdb-test",
                        "cpu_millicores": 1200,
                        "memory_mi": 2048,
                    }
                ],
            },
        }
    }
    signal_bundle = {
        "abnormal_signals": [
            {"signal_id": "node-resource-pressure", "severity": "medium", "object_ref": "node/worker-1"},
            {"signal_id": "pod-resource-pressure", "severity": "medium", "object_ref": "pod/mongo-0"},
        ]
    }

    governance = phase3_signal_governance.build_signal_governance(structured_record, signal_bundle)

    contexts = {item["object_ref"]: item for item in governance["signal_contexts"]}
    assert contexts["node/worker-1"]["resource_pressure"]["cpu_percent"] == 91
    assert contexts["pod/mongo-0"]["resource_pressure"]["usage"]["cpu_millicores"] == 1200
    assert contexts["pod/mongo-0"]["resource_pressure"]["requests"]["cpu_millicores"] == 500
    assert contexts["pod/mongo-0"]["resource_pressure"]["usage_to_request"]["cpu_ratio"] == 2.4
    assert contexts["pod/mongo-0"]["resource_pressure"]["usage_to_limit"]["memory_ratio"] == 0.5


def test_write_signal_governance_updates_signal_bundle_without_replacing_signals(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(
        output_dir / "structured_record.yaml",
        {
            "details": {
                "pods": [
                    {
                        "name": "mongo-0",
                        "namespace": "psmdb-test",
                        "node_ref": "node-a",
                    }
                ],
                "replica_members": [
                    {
                        "replica_set_id": "shard-01-rs",
                        "source_pod_ref": "mongo-0",
                    }
                ],
            }
        },
    )
    write_yaml(
        output_dir / "signal_bundle.yaml",
        {
            "abnormal_signals": [
                {"signal_id": "pod-not-ready", "severity": "high", "object_ref": "pod/mongo-0"},
                {
                    "signal_id": "statefulset-replicas-not-ready",
                    "severity": "high",
                    "object_ref": "statefulset/mongo",
                },
                {"signal_id": "replica-member-recovering", "severity": "critical", "object_ref": "replicaset/shard-01-rs"},
            ],
        },
    )

    governance = phase3_signal_governance.write_signal_governance(output_dir)
    signal_bundle = yaml.safe_load((output_dir / "signal_bundle.yaml").read_text(encoding="utf-8"))

    assert signal_bundle["abnormal_signals"] == [
        {"signal_id": "pod-not-ready", "severity": "high", "object_ref": "pod/mongo-0"},
        {
            "signal_id": "statefulset-replicas-not-ready",
            "severity": "high",
            "object_ref": "statefulset/mongo",
        },
        {"signal_id": "replica-member-recovering", "severity": "critical", "object_ref": "replicaset/shard-01-rs"},
    ]
    assert signal_bundle["signal_groups"] == governance["signal_groups"]
    assert {item["layer"] for item in signal_bundle["signal_groups"]} == {"orchestration", "pod", "service"}
    assert {
        (item["type"], item["from"], item["to"])
        for item in signal_bundle["correlations"]
    } >= {
        ("co_location", "pod/mongo-0", "node/node-a"),
        ("service_pod_source", "replicaset/shard-01-rs", "pod/mongo-0"),
    }


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

    selected = phase3_recollection.directed_recollection_script_ids(
        output_dir,
        skill_pool={
            phase3_recollection.SCRIPT_DNS_COREDNS,
            phase3_recollection.SCRIPT_NETWORK_OVERLAY,
        },
    )

    assert selected == [
        phase3_recollection.SCRIPT_DNS_COREDNS,
        phase3_recollection.SCRIPT_NETWORK_OVERLAY,
    ]


def test_select_directed_recollection_script_ids_is_pure_dns_path():
    structured_record = {"details": {"raw_logs": []}}
    signal_bundle = {
        "abnormal_signals": [
            {"signal_id": "dns-resolution-failed"},
            {"signal_id": "pod-crashloop", "object_ref": "pod/bnmongo-shard0-data-0"},
        ]
    }
    collection_report = {
        "evidence_gaps": [
            {"gap": "lookup on 10.96.0.10:53 read udp connection refused"},
        ]
    }

    selected = phase3_recollection.select_directed_recollection_script_ids(
        structured_record,
        signal_bundle,
        collection_report,
    )

    assert selected == [
        phase3_recollection.SCRIPT_DNS_COREDNS,
        phase3_recollection.SCRIPT_NETWORK_OVERLAY,
        phase3_recollection.SCRIPT_LOG_NODE_FILE_TAIL,
    ]


def test_filter_recollection_scripts_by_skill_pool_marks_miss_when_empty_overlap():
    selected, miss = phase3_recollection.filter_recollection_scripts_by_skill_pool(
        [
            phase3_recollection.SCRIPT_DNS_COREDNS,
            phase3_recollection.SCRIPT_NETWORK_OVERLAY,
        ],
        {"mongodb.collect.pods.state"},
    )

    assert selected == [
        phase3_recollection.SCRIPT_DNS_COREDNS,
        phase3_recollection.SCRIPT_NETWORK_OVERLAY,
    ]
    assert miss is True


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

    selected = phase3_recollection.directed_recollection_script_ids(output_dir, skill_pool={"mongodb.collect.pods.state"})

    assert phase3_recollection.SCRIPT_LOG_SINK_DISCOVER in selected
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

    monkeypatch.setattr(phase3_remote_collection.subprocess, "run", fake_run)
    args = SimpleNamespace(
        remote_config=str(remote_config),
        remote_output_dir=str(remote_output_dir),
        remote_namespace="",
        object_inventory="",
    )

    result = phase3_remote_collection.run_remote_collection(args, output_dir)

    assert result == remote_run_dir
    assert captured["command"][:3] == [sys.executable, "-m", "execution.remote.executor"]
    assert "--transport" not in captured["command"]
    assert str(ROOT / "src") in captured["env"]["PYTHONPATH"].split(":")[0]


def test_run_local_collection_invokes_execution_module_with_local_transport(tmp_path, monkeypatch):
    output_dir = tmp_path / "incident"
    remote_output_dir = tmp_path / "remote-runs"
    remote_run_dir = remote_output_dir / "mongodb-local-run-20260619-000000"
    remote_run_dir.mkdir(parents=True, exist_ok=True)
    local_config = tmp_path / "local.yaml"
    local_config.write_text("access:\n  execution_mode: local\n", encoding="utf-8")
    captured = {}

    def fake_run(command, env, stdout, stderr, universal_newlines, timeout):
        captured["command"] = command

        class Result:
            returncode = 0
            stdout = "local_dir=%s\n" % remote_run_dir
            stderr = ""

        return Result()

    monkeypatch.setattr(phase3_remote_collection.subprocess, "run", fake_run)
    args = SimpleNamespace(
        local_config=str(local_config),
        remote_output_dir=str(remote_output_dir),
        remote_namespace="psmdb-test",
        object_inventory="",
    )

    result = phase3_remote_collection.run_local_collection(args, output_dir)

    assert result == remote_run_dir
    assert captured["command"][:3] == [sys.executable, "-m", "execution.remote.executor"]
    assert captured["command"][captured["command"].index("--config") + 1] == str(local_config)
    assert captured["command"][captured["command"].index("--transport") + 1] == "local"
    assert "--namespace" in captured["command"]


def test_directed_recollection_uses_execution_mode_to_select_local_runner(tmp_path, monkeypatch):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "structured_record.yaml", {"details": {"raw_logs": []}})
    write_yaml(
        output_dir / "signal_bundle.yaml",
        {"abnormal_signals": [{"signal_id": "dns-resolution-failed"}]},
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {"collection_actions": [], "evidence_gaps": [{"gap": "lookup on 10.96.0.10:53 connection refused"}]},
    )
    remote_run_dir = tmp_path / "local-run"
    remote_run_dir.mkdir()
    calls = []

    def fail_remote(*_args, **_kwargs):
        raise AssertionError("local directed recollection must not use the remote runner")

    def fake_local(args, trace_dir, script_ids):
        calls.append((args.local_config, trace_dir, script_ids))
        return remote_run_dir

    monkeypatch.setattr(phase3_recollection_run, "run_remote_collection", fail_remote)
    monkeypatch.setattr(phase3_recollection_run, "run_local_collection", fake_local)
    monkeypatch.setattr(phase3_recollection_run, "merge_remote_run_outputs", lambda *_args, **_kwargs: None)

    args = SimpleNamespace(
        execution_mode="local",
        remote_config=str(tmp_path / "stale-remote.yaml"),
        local_config=str(tmp_path / "local.yaml"),
    )

    assert phase3_recollection_run.run_directed_recollection_if_needed(args, output_dir) is True

    assert calls
    assert calls[0][0] == str(tmp_path / "local.yaml")
    assert calls[0][1] == output_dir / "directed-recollection"
    assert phase3_recollection.SCRIPT_DNS_COREDNS in calls[0][2]


def test_directed_recollection_runs_auto_allowed_first_class_verification_requests(tmp_path, monkeypatch):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "structured_record.yaml", {"details": {}})
    write_yaml(output_dir / "signal_bundle.yaml", {"abnormal_signals": []})
    write_yaml(output_dir / "collection_report.yaml", {"collection_actions": [], "evidence_gaps": []})
    write_yaml(
        output_dir / "analysis.yaml",
        {
            "verification_requests": [
                {
                    "request_id": "vr-mongodb-election-logs",
                    "asset_tier": "first_class",
                    "execution_policy": "auto_allowed",
                    "risk_level": "read-only",
                    "asset": {"type": "script", "id": "kubernetes.collect.logs.previous"},
                },
                {
                    "request_id": "vr-mongodb-rs-conf-compare",
                    "asset_tier": "first_class",
                    "execution_policy": "auto_allowed",
                    "risk_level": "read-only",
                    "asset": {"type": "script", "id": "mongodb.collect.replicaset.rs_conf"},
                },
            ]
        },
    )
    remote_run_dir = tmp_path / "remote-run"
    remote_run_dir.mkdir()
    calls = []

    def fake_remote(args, trace_dir, script_ids):
        calls.append((args.remote_config, trace_dir, script_ids))
        return remote_run_dir

    monkeypatch.setattr(phase3_recollection_run, "run_remote_collection", fake_remote)
    monkeypatch.setattr(phase3_recollection_run, "merge_remote_run_outputs", lambda *_args, **_kwargs: None)

    args = SimpleNamespace(
        execution_mode="remote",
        remote_config=str(tmp_path / "remote.yaml"),
        local_config="",
    )

    assert phase3_recollection_run.run_directed_recollection_if_needed(args, output_dir) is True

    assert calls == [
        (
            str(tmp_path / "remote.yaml"),
            output_dir / "directed-recollection",
            [
                "kubernetes.collect.logs.previous",
                "mongodb.normalize.logs.highlights",
                "mongodb.collect.replicaset.rs_conf",
            ],
        )
    ]


def test_auto_allowed_log_verification_requests_include_domain_log_normalizer(tmp_path):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "input.yaml", {"middleware": "mongodb"})
    write_yaml(
        output_dir / "analysis.yaml",
        {
            "verification_requests": [
                {
                    "request_id": "vr-mongodb-election-logs",
                    "asset_tier": "first_class",
                    "execution_policy": "auto_allowed",
                    "risk_level": "read-only",
                    "asset": {"type": "script", "id": "kubernetes.collect.logs.previous"},
                }
            ]
        },
    )

    selected = phase3_recollection.auto_allowed_verification_script_ids(output_dir)

    assert selected == ["kubernetes.collect.logs.previous", "mongodb.normalize.logs.highlights"]


def test_directed_recollection_offline_mode_does_not_execute_collection(tmp_path, monkeypatch):
    output_dir = tmp_path / "incident"
    write_yaml(output_dir / "structured_record.yaml", {"details": {"raw_logs": []}})
    write_yaml(
        output_dir / "signal_bundle.yaml",
        {"abnormal_signals": [{"signal_id": "dns-resolution-failed"}]},
    )
    write_yaml(
        output_dir / "collection_report.yaml",
        {"collection_actions": [], "evidence_gaps": [{"gap": "lookup on 10.96.0.10:53 connection refused"}]},
    )

    def fail_collection(*_args, **_kwargs):
        raise AssertionError("offline directed recollection must not execute collection")

    monkeypatch.setattr(phase3_recollection_run, "run_remote_collection", fail_collection)
    monkeypatch.setattr(phase3_recollection_run, "run_local_collection", fail_collection)

    args = SimpleNamespace(
        execution_mode="offline",
        remote_config=str(tmp_path / "remote.yaml"),
        local_config=str(tmp_path / "local.yaml"),
    )

    assert phase3_recollection_run.run_directed_recollection_if_needed(args, output_dir) is False


def test_remote_run_report_method_reflects_local_transport():
    collection_report = {
        "collection_actions": [],
        "successful_items": [],
        "failed_items": [],
        "evidence_gaps": [],
    }

    phase3_remote_run.merge_remote_executor_run_result(
        collection_report,
        {
            "status": "blocked",
            "selected_ip": "local",
            "transport": "local",
            "error": {"message": "local kubectl unavailable"},
        },
        has_script_outputs=False,
    )
    phase3_remote_run.merge_remote_executor_result(
        collection_report,
        "mongodb.collect.pods.state",
        {
            "script_id": "mongodb.collect.pods.state",
            "status": "success",
            "selected_ip": "local",
            "transport": "local",
            "process": {"exit_code": 0},
        },
    )

    methods = [item["method"] for item in collection_report["collection_actions"]]
    assert methods == [
        "local transport + staged packaged scripts",
        "local transport + staged packaged script",
    ]


def test_build_incident_from_remote_run_merges_and_copies_outputs(tmp_path):
    remote_run_dir = tmp_path / "remote-run"
    item_dir = remote_run_dir / "mongodb-collect-pods"
    artifact_dir = item_dir / "artifacts"
    artifact_dir.mkdir(parents=True)
    write_yaml(
        item_dir / "context.yaml",
        {
            "incident_id": "mongodb-remote-run",
            "middleware": "mongodb",
            "scenario": "kubernetes-runtime",
            "namespace": "psmdb-test",
            "cluster_id": "cluster-a",
            "topology_type": "sharded",
        },
    )
    write_yaml(
        remote_run_dir / "remote-executor-run.yaml",
        {
            "incident_id": "mongodb-remote-run",
            "namespace": "psmdb-test",
            "status": "success",
            "selected_ip": "192.168.154.251",
        },
    )
    write_yaml(
        item_dir / "remote-executor-result.yaml",
        {
            "script_id": "mongodb.collect.pods.state",
            "status": "success",
            "selected_ip": "192.168.154.251",
            "process": {"exit_code": 0},
        },
    )
    write_yaml(
        item_dir / "output.yaml",
        {
            "script_id": "mongodb.collect.pods.state",
            "structured_record_patch": {
                "details": {
                    "pods": [
                        {
                            "name": "bnmongo-shard0-data-0",
                            "namespace": "psmdb-test",
                            "status": "Running",
                        }
                    ]
                }
            },
            "signal_bundle_patch": {
                "abnormal_signals": [
                    {
                        "signal_id": "pod-not-ready",
                        "object_ref": "pod/bnmongo-shard0-data-0",
                    }
                ]
            },
            "collection_report_patch": {
                "successful_items": [
                    {
                        "item": "pods/state",
                        "source": "kubectl",
                    }
                ]
            },
        },
    )
    (item_dir / "remote.stdout.txt").write_text("ok\n", encoding="utf-8")
    (artifact_dir / "pods.json").write_text("{}\n", encoding="utf-8")
    output_dir = tmp_path / "incident"
    args = SimpleNamespace(scenario="", customer_clue="", incident_input={})

    phase3_incident_build.build_incident_from_remote_run(remote_run_dir, output_dir, args)

    input_data = yaml.safe_load((output_dir / "input.yaml").read_text(encoding="utf-8"))
    structured_record = yaml.safe_load((output_dir / "structured_record.yaml").read_text(encoding="utf-8"))
    signal_bundle = yaml.safe_load((output_dir / "signal_bundle.yaml").read_text(encoding="utf-8"))
    collection_report = yaml.safe_load((output_dir / "collection_report.yaml").read_text(encoding="utf-8"))

    assert input_data["incident_id"] == "mongodb-remote-run"
    assert input_data["namespace"] == "psmdb-test"
    assert structured_record["summary"]["topology_type"] == "sharded"
    assert structured_record["details"]["pods"][0]["name"] == "bnmongo-shard0-data-0"
    assert signal_bundle["abnormal_signals"][0]["signal_id"] == "pod-not-ready"
    assert any(item["item"] == "remote-executor/mongodb.collect.pods.state" for item in collection_report["successful_items"])
    assert (output_dir / "remote-executor-run.yaml").exists()
    assert (output_dir / "script_outputs" / "mongodb.collect.pods.state" / "remote.stdout.txt").exists()
    assert (output_dir / "script_outputs" / "mongodb.collect.pods.state" / "artifacts" / "pods.json").exists()
