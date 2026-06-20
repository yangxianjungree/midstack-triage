import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.deep_analysis import materialize_deep_analysis


def test_materialize_deep_analysis_outputs_readonly_results_for_split_brain_requests():
    analysis = {
        "deep_analysis_requests": [
            {
                "request_id": "dar-mongodb-rs-baseline-scan",
                "capability": "baseline_scan",
                "purpose": "Compare replica-set invariants.",
                "inputs": ["structured_record.details.replica_members"],
                "expected_output": ["baseline_diff"],
            },
            {
                "request_id": "dar-mongodb-rs-code-logic",
                "capability": "code_logic_analysis",
                "purpose": "Explain decision logic.",
                "inputs": ["structured_record.details.replica_members"],
                "expected_output": ["decision_rule_mapping"],
            },
            {
                "request_id": "dar-mongodb-rs-code-path",
                "capability": "code_path_tracing",
                "purpose": "Trace evidence path.",
                "inputs": ["structured_record.details.replica_members"],
                "expected_output": ["evidence_path_trace"],
            },
            {
                "request_id": "dar-mongodb-rs-repro-script",
                "capability": "repro_script_generation",
                "purpose": "Draft read-only repro plan.",
                "inputs": ["analysis.yaml"],
                "expected_output": ["read_only_repro_plan"],
            },
        ],
        "deepening_findings": [
            {
                "finding_id": "mongodb.replica_set.config_divergence",
                "statement": "Replica set rs0 has divergent config views.",
                "severity": "high",
            }
        ],
    }
    structured_record = {
        "details": {
            "replica_members": [
                {
                    "replica_set_id": "rs0",
                    "source_pod_ref": "mongo-0",
                    "voting_members_count": 1,
                    "self_member": {"state_str": "PRIMARY", "config_version": 2, "config_term": 73},
                    "members": [{"name": "mongo-0:27017", "state_str": "PRIMARY"}],
                },
                {
                    "replica_set_id": "rs0",
                    "source_pod_ref": "mongo-1",
                    "voting_members_count": 3,
                    "self_member": {"state_str": "PRIMARY", "config_version": 8, "config_term": 72},
                    "members": [
                        {"name": "mongo-0:27017", "state_str": "(not reachable/healthy)"},
                        {"name": "mongo-1:27017", "state_str": "PRIMARY"},
                        {"name": "mongo-2:27017", "state_str": "SECONDARY"},
                    ],
                },
            ]
        }
    }

    result = materialize_deep_analysis(analysis, structured_record, {"log_highlights": []})

    assert result["schema_version"] == "deep-analysis.v1"
    assert result["execution_boundary"] == "read_only_materialization"
    assert result["summary"]["total_requests"] == 4
    assert result["summary"]["completed_requests"] == 4
    by_id = {item["request_id"]: item for item in result["results"]}
    assert by_id["dar-mongodb-rs-baseline-scan"]["status"] == "completed"
    assert by_id["dar-mongodb-rs-baseline-scan"]["output"]["baseline_diff"]["replica_set_count"] == 1
    assert by_id["dar-mongodb-rs-code-logic"]["output"]["decision_rule_mapping"]
    assert by_id["dar-mongodb-rs-code-path"]["output"]["evidence_path_trace"]
    assert by_id["dar-mongodb-rs-repro-script"]["output"]["read_only_repro_plan"]
    assert all(item["risk_level"] == "read-only" for item in result["results"])
