import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.agent_conclusion_gate import evaluate_agent_conclusion_gate


def _analysis(agent_reasoning, limitations=None):
    return {
        "conclusion_summary": {
            "statement": "Rules fallback conclusion",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replication",
            "impact_scope": "replica set",
            "evidence": ["current evidence"],
            "limitations": limitations or [],
        },
        "hypotheses": [],
        "agent_reasoning": agent_reasoning,
    }


def test_gate_blocks_mock_runtime_even_when_candidate_is_supported():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "mock", "model": "mock"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.95,
                        "evidence_refs": ["structured_record.details.replica_members"],
                    }
                ],
            }
        )
    )

    assert gate["decision"] == "blocked"
    assert gate["override_applied"] is False
    assert any(item["code"] == "agent_runtime_not_claude" for item in gate["blockers"])


def test_gate_blocks_candidate_without_current_incident_evidence_refs():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.95,
                    }
                ],
            }
        )
    )

    assert gate["decision"] == "blocked"
    assert any(item["code"] == "missing_current_evidence_refs" for item in gate["blockers"])


def test_gate_blocks_unresolved_critical_gap():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.95,
                        "evidence_refs": ["structured_record.details.replica_members"],
                    }
                ],
            },
            limitations=[
                {
                    "gap": "rs.conf() comparison is missing",
                    "gap_type": "critical_gap",
                }
            ],
        )
    )

    assert gate["decision"] == "blocked"
    assert any(item["code"] == "unresolved_critical_gap" for item in gate["blockers"])


def test_gate_blocks_supported_candidate_without_structured_conclusion_candidate():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.91,
                        "evidence_refs": ["structured_record.details.replica_members"],
                    }
                ],
            }
        )
    )

    assert gate["decision"] == "blocked"
    assert any(item["code"] == "conclusion_candidate_incomplete" for item in gate["blockers"])


def test_gate_marks_high_confidence_claude_candidate_eligible_with_current_evidence_refs():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.91,
                        "evidence_refs": [
                            "structured_record.details.replica_members",
                            "signal_bundle.topology.replica_sets.rs0",
                        ],
                        "conclusion_candidate": {
                            "statement": "Agent candidate",
                            "confidence": "medium",
                            "deepest_supported_level": "mechanism",
                            "primary_cause_category": "replica_set_split_brain",
                            "impact_scope": "replica set",
                            "evidence": ["structured_record.details.replica_members"],
                            "limitations": [],
                        },
                    }
                ],
            }
        )
    )

    assert gate["decision"] == "eligible"
    assert gate["override_applied"] is False
    assert gate["selected_candidate"]["hypothesis_id"] == "h1"
    assert gate["blockers"] == []


def test_gate_preserves_structured_conclusion_candidate_for_future_override():
    gate = evaluate_agent_conclusion_gate(
        _analysis(
            {
                "runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
                "hypotheses": [
                    {
                        "id": "h1",
                        "statement": "Agent candidate",
                        "status": "supported",
                        "confidence": 0.91,
                        "evidence_refs": ["structured_record.details.replica_members"],
                        "conclusion_candidate": {
                            "statement": "Replica set rs0 has a split-brain mechanism.",
                            "confidence": "medium",
                            "deepest_supported_level": "mechanism",
                            "primary_cause_category": "replica_set_split_brain",
                            "impact_scope": "rs0 availability",
                            "evidence": ["structured_record.details.replica_members"],
                            "limitations": [],
                        },
                    }
                ],
            }
        )
    )

    assert gate["decision"] == "eligible"
    candidate = gate["selected_candidate"]["conclusion_summary"]
    assert candidate["statement"] == "Replica set rs0 has a split-brain mechanism."
    assert candidate["primary_cause_category"] == "replica_set_split_brain"
