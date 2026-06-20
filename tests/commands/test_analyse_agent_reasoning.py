import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from commands.analyse import _agent_reasoning_summary


PHASE4_FIXTURE = ROOT / "tests" / "fixtures" / "phase4" / "agent-eligible-phase4-result.yaml"


def test_agent_reasoning_summary_preserves_conclusion_candidate():
    summary = _agent_reasoning_summary(yaml.safe_load(PHASE4_FIXTURE.read_text(encoding="utf-8")))

    candidate = summary["hypotheses"][0]["conclusion_candidate"]
    assert candidate["statement"] == "Replica set rs0 has a split-brain mechanism."
    assert candidate["primary_cause_category"] == "replica_set_split_brain"
