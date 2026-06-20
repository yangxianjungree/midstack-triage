import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from commands.analyse import _agent_reasoning_summary


def test_agent_reasoning_summary_preserves_conclusion_candidate():
    summary = _agent_reasoning_summary(
        {
            "agent_runtime": {"selected_type": "claude", "model": "claude-sonnet-4-6"},
            "total_rounds": 1,
            "hypotheses": [
                {
                    "id": "h1",
                    "final_text": "Replica set split-brain candidate",
                    "status": {"status": "supported", "confidence": 0.91},
                    "private_context": {
                        "hypothesis_evolution": [
                            {
                                "evidence": ["structured_record.details.replica_members"],
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
                        ]
                    },
                }
            ],
        }
    )

    candidate = summary["hypotheses"][0]["conclusion_candidate"]
    assert candidate["statement"] == "Replica set rs0 has a split-brain mechanism."
    assert candidate["primary_cause_category"] == "replica_set_split_brain"
