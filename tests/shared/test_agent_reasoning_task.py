from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.analysis_runtime import write_agent_reasoning_task


def test_agent_reasoning_task_preserves_experience_retrieval_contract(tmp_path):
    task_file = write_agent_reasoning_task(
        tmp_path,
        {
            "incident_id": "demo",
            "middleware": "mongodb",
            "scenario": "kubernetes-runtime",
            "customer_clue": "mongo was down yesterday",
        },
        tmp_path / "analysis.yaml",
        tmp_path / "analysis.rules-fallback.yaml",
        tmp_path / "report.md",
        matched_skills=[],
    )

    content = task_file.read_text(encoding="utf-8")

    assert "`retrieval_context`" in content
    assert "`experience_matches`" in content
    assert "`source_boundaries`" in content
    assert "`reasoning_timeline`" in content
    assert "`verification_requests`" in content
    assert "must stay present" in content
    assert "must not become direct supporting evidence" in content
    assert "ordering alone" in content
