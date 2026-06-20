import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.analysis_runtime import apply_analysis_guardrails, write_report
from shared.verification_guardrails import ad_hoc_readonly_command_request, apply_verification_request_guardrails


def test_guardrails_do_not_allow_config_drift_hypothesis_supported_without_rs_conf():
    analysis = {
        "conclusion_summary": {
            "statement": "Split-brain is confirmed; config drift caused divergent decision views.",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replica_set_config_divergence",
            "impact_scope": "shard replica set",
            "evidence": ["two PRIMARY members", "divergent config_version views"],
            "limitations": [],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H3",
                "statement": "Replica set configuration or member metadata drift created divergent decision views.",
                "status": "supported",
                "validation_result": "supported",
                "evidence_gaps": [
                    {
                        "gap": "rs.conf() comparison across all affected members is not available",
                        "gap_type": "critical_gap",
                        "related_stage": "reasoning",
                    }
                ],
                "validation_actions": [
                    {
                        "action": "Compare read-only rs.conf() output from all affected members.",
                        "status": "planned",
                        "risk_level": "read-only",
                    }
                ],
            }
        ],
        "next_actions": [],
    }

    changed = apply_analysis_guardrails(analysis, {"evidence_gaps": []}, {"abnormal_signals": []})

    assert changed is True
    hypothesis = analysis["hypotheses"][0]
    assert hypothesis["status"] == "insufficient"
    assert hypothesis["validation_result"] == "insufficient"
    assert analysis["conclusion_summary"]["primary_cause_category"] == "split_brain_enabling_cause_unproven"
    assert any("rs.conf() comparison" in item["gap"] for item in analysis["conclusion_summary"]["limitations"])


def test_ad_hoc_readonly_command_request_requires_approval():
    request = ad_hoc_readonly_command_request(
        "vr-kubectl-get-events",
        "H1",
        "inspect namespace events",
        ["kubectl", "get", "events", "-n", "psmdb-test"],
        ["collection_report.events"],
        "events may explain the transient failure",
    )

    assert request["asset_tier"] == "ad_hoc_readonly"
    assert request["execution_policy"] == "approval_required"
    assert request["risk_level"] == "read-only"
    assert request["status"] == "planned"


def test_verification_request_guardrail_blocks_unstructured_ad_hoc_shell():
    analysis = {
        "verification_requests": [
            {
                "request_id": "vr-shell",
                "asset_tier": "ad_hoc_readonly",
                "asset": {"type": "ad_hoc_command", "id": "vr-shell", "command": "kubectl get pods | xargs delete"},
                "risk_level": "read-only",
                "execution_policy": "approval_required",
                "status": "planned",
            }
        ]
    }

    changed = apply_verification_request_guardrails(analysis)

    request = analysis["verification_requests"][0]
    assert changed is True
    assert request["asset_tier"] == "blocked"
    assert request["execution_policy"] == "blocked"
    assert request["status"] == "blocked"
    assert "structured argv" in request["guardrail_reason"]


def test_analysis_guardrails_normalize_ad_hoc_readonly_commands():
    analysis = {
        "conclusion_summary": {"statement": "needs more evidence", "confidence": "medium"},
        "verification_requests": [
            {
                "request_id": "vr-kubectl-logs",
                "asset_tier": "ad_hoc_readonly",
                "asset": {"type": "ad_hoc_command", "id": "vr-kubectl-logs", "argv": ["kubectl", "logs", "pod/mongo-0"]},
                "risk_level": "low-risk",
                "execution_policy": "auto_allowed",
                "status": "executed",
            }
        ],
    }

    changed = apply_analysis_guardrails(analysis, {}, {})

    request = analysis["verification_requests"][0]
    assert changed is True
    assert request["risk_level"] == "read-only"
    assert request["execution_policy"] == "approval_required"
    assert request["status"] == "planned"


def test_write_report_includes_reasoning_timeline(tmp_path):
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB pod cannot be scheduled",
            "confidence": "high",
            "deepest_supported_level": "impact",
            "primary_cause_category": "kubernetes-scheduling",
            "impact_scope": "shard member unavailable",
            "evidence": ["scheduler rejected pod"],
            "limitations": [],
        },
        "hypotheses": [],
        "next_actions": [],
        "knowledge_candidates": [],
        "reasoning_timeline": {
            "events": [
                {
                    "time": "2026-06-07T00:01:00+08:00",
                    "time_precision": "exact",
                    "layer": "kubernetes",
                    "summary": "FailedScheduling on mongo-0: node selector mismatch",
                    "source": "structured_record.details.events",
                    "confidence": "high",
                },
                {
                    "time": "",
                    "time_precision": "unknown",
                    "layer": "analysis",
                    "summary": "pod scheduling failed before rs.status collection",
                    "source": "signal_bundle.timeline_summary",
                    "confidence": "medium",
                },
            ]
        },
    }

    report = write_report(tmp_path, {"incident_id": "demo", "middleware": "mongodb"}, analysis)

    content = report.read_text(encoding="utf-8")
    assert "## Timeline" in content
    assert "FailedScheduling on mongo-0: node selector mismatch" in content
    assert "pod scheduling failed before rs.status collection" in content


def test_write_report_prioritizes_diagnostic_timeline_events(tmp_path):
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB replica set has split-brain symptoms",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replication",
            "impact_scope": "shard replica set",
            "evidence": ["two members report conflicting PRIMARY views"],
            "limitations": [],
        },
        "hypotheses": [],
        "next_actions": [],
        "knowledge_candidates": [],
        "reasoning_timeline": {
            "events": [
                {
                    "time": "2026-06-07T00:00:00+08:00",
                    "layer": "collection",
                    "summary": "collection action 0",
                    "source": "collection_report.collection_actions",
                },
                {
                    "time": "2026-06-07T00:00:01+08:00",
                    "layer": "collection",
                    "summary": "collection action 1",
                    "source": "collection_report.collection_actions",
                },
                {
                    "time": "",
                    "layer": "diagnostic",
                    "summary": "Replica set rs0 split-brain observed: 2 PRIMARY views and divergent voting quorum counts.",
                    "source": "structured_record.details.replica_members",
                    "confidence": "high",
                },
            ]
        },
    }

    report = write_report(tmp_path, {"incident_id": "demo", "middleware": "mongodb"}, analysis)

    content = report.read_text(encoding="utf-8")
    timeline = content.split("## Timeline", 1)[1].split("## Mechanism Deepening", 1)[0]
    diagnostic_index = timeline.index("Replica set rs0 split-brain observed")
    collection_index = timeline.index("collection action 0")
    assert diagnostic_index < collection_index


def test_write_report_labels_log_local_timeline_time(tmp_path):
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB logs include startup events",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replication",
            "impact_scope": "replica set",
            "evidence": [],
            "limitations": [],
        },
        "hypotheses": [],
        "next_actions": [],
        "knowledge_candidates": [],
        "reasoning_timeline": {
            "events": [
                {
                    "time": "01:32:32.22",
                    "time_precision": "log_local_time",
                    "layer": "diagnostic",
                    "summary": "MongoDB log highlight on bnmongo-shard0-data-0: Setting node as primary",
                    "source": "signal_bundle.log_highlights",
                }
            ]
        },
    }

    report = write_report(tmp_path, {"incident_id": "demo", "middleware": "mongodb"}, analysis)

    content = report.read_text(encoding="utf-8")
    assert "`01:32:32.22` `(log-local)` `diagnostic`" in content


def test_write_report_includes_deepening_findings(tmp_path):
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB replica set has split-brain symptoms",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replication",
            "impact_scope": "shard replica set",
            "evidence": ["two members report conflicting PRIMARY views"],
            "limitations": [],
        },
        "hypotheses": [],
        "next_actions": [],
        "knowledge_candidates": [],
        "reasoning_timeline": {"events": []},
        "deepening_findings": [
            {
                "finding_id": "mongodb.replica_set.config_divergence",
                "statement": "Replica set rs0 has divergent config_version/config_term views.",
                "severity": "high",
                "supports": ["split_brain_enabling_condition"],
                "refutes": [],
            },
            {
                "finding_id": "mongodb.network.current_tcp_reachability",
                "statement": "Current MongoDB TCP probes succeeded for at least one member path.",
                "severity": "medium",
                "supports": [],
                "refutes": ["sustained_network_partition"],
            },
        ],
    }

    report = write_report(tmp_path, {"incident_id": "demo", "middleware": "mongodb"}, analysis)

    content = report.read_text(encoding="utf-8")
    assert "## Mechanism Deepening" in content
    assert "`high` `mongodb.replica_set.config_divergence` Replica set rs0 has divergent config_version/config_term views." in content
    assert "supports=split_brain_enabling_condition" in content
    assert "refutes=sustained_network_partition" in content


def test_write_report_includes_verification_requests(tmp_path):
    analysis = {
        "conclusion_summary": {
            "statement": "MongoDB replica set has split-brain symptoms",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replication",
            "impact_scope": "shard replica set",
            "evidence": ["two members report conflicting PRIMARY views"],
            "limitations": [],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H3",
                "status": "insufficient",
                "statement": "Replica set configuration or member metadata drift created divergent decision views.",
            }
        ],
        "next_actions": [],
        "knowledge_candidates": [],
        "reasoning_timeline": {"events": []},
        "deepening_findings": [],
        "verification_requests": [
            {
                "request_id": "vr-mongodb-rs-conf-compare",
                "hypothesis_id": "H3",
                "purpose": "compare rs.conf from all affected replica set members",
                "asset_tier": "first_class",
                "asset": {
                    "type": "script",
                    "id": "mongodb.collect.replicaset.rs_conf",
                },
                "risk_level": "read-only",
                "execution_policy": "auto_allowed",
                "reason": "Configuration drift is a plausible enabling cause.",
                "status": "planned",
            },
            {
                "request_id": "vr-mongodb-election-logs",
                "hypothesis_id": "H4",
                "purpose": "collect MongoDB heartbeat election and reconfig logs",
                "asset_tier": "first_class",
                "asset": {
                    "type": "script",
                    "id": "kubernetes.collect.logs.previous",
                },
                "risk_level": "read-only",
                "execution_policy": "auto_allowed",
                "reason": "Historical heartbeat evidence is needed.",
                "status": "planned",
            },
        ],
    }

    report = write_report(tmp_path, {"incident_id": "demo", "middleware": "mongodb"}, analysis)

    content = report.read_text(encoding="utf-8")
    assert "## Verification Requests" in content
    assert "`planned` `read-only` `auto_allowed` `first_class` `vr-mongodb-rs-conf-compare` H3" in content
    assert "asset=script/mongodb.collect.replicaset.rs_conf" in content
    assert "Configuration drift is a plausible enabling cause." in content
    assert "`planned` `read-only` `auto_allowed` `first_class` `vr-mongodb-election-logs` H4" in content
    assert "asset=script/kubernetes.collect.logs.previous" in content
