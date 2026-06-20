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
    assert "`deepening_findings`" in content
    assert "must stay present" in content
    assert "must not become direct supporting evidence" in content
    assert "ordering alone" in content
    assert "enabling/root cause" in content


def test_agent_reasoning_task_requires_guarded_ad_hoc_verification_requests(tmp_path):
    task_file = write_agent_reasoning_task(
        tmp_path,
        {
            "incident_id": "demo",
            "middleware": "mongodb",
            "scenario": "kubernetes-runtime",
        },
        tmp_path / "analysis.yaml",
        tmp_path / "analysis.rules-fallback.yaml",
        tmp_path / "report.md",
        matched_skills=[],
    )

    content = task_file.read_text(encoding="utf-8")

    assert "first-class repository read-only assets" in content
    assert "top-level `verification_requests`" in content
    assert "`asset_tier: ad_hoc_readonly`" in content
    assert "`asset.type: ad_hoc_command`" in content
    assert "structured `asset.argv`" in content
    assert "`execution_policy: approval_required`" in content
    assert "`execution_policy: blocked`" in content
    assert "does not authorize auto-executing ad hoc commands" in content
