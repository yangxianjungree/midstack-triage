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
    assert "`deep_analysis_requests`" in content
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


def test_agent_reasoning_task_describes_deep_analysis_contract(tmp_path):
    task_file = write_agent_reasoning_task(
        tmp_path,
        {
            "incident_id": "demo",
            "middleware": "mongodb",
            "scenario": "replica-inconsistency",
        },
        tmp_path / "analysis.yaml",
        tmp_path / "analysis.rules-fallback.yaml",
        tmp_path / "report.md",
        matched_skills=[],
    )

    content = task_file.read_text(encoding="utf-8")

    assert "`deep_analysis_requests`" in content
    assert "`baseline_scan`" in content
    assert "`code_logic_analysis`" in content
    assert "`code_path_tracing`" in content
    assert "`repro_script_generation`" in content
    assert "plan-only" in content


def test_agent_reasoning_task_surfaces_materialized_deep_analysis_results(tmp_path):
    (tmp_path / "analysis.yaml").write_text(
        """
deep_analysis_results:
  artifact: deep-analysis.yaml
  summary:
    total_requests: 2
    completed_requests: 2
    capabilities:
    - baseline_scan
    - code_path_tracing
  highlights:
  - request_id: deep-baseline
    capability: baseline_scan
    status: completed
    summary: Detected baseline invariant violations.
    violations:
    - multiple_primary_views
    replica_sets:
    - bnmongo-shard-0
  - request_id: deep-path
    capability: code_path_tracing
    status: completed
    summary: Traced evidence path with 1 missing validation edge.
    supports:
    - split_brain_mechanism
    missing_path_edges:
    - request_id: vr-rs-conf
      purpose: compare rs.conf
      status: planned
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "deep-analysis.yaml").write_text("results: []\n", encoding="utf-8")

    task_file = write_agent_reasoning_task(
        tmp_path,
        {
            "incident_id": "demo",
            "middleware": "mongodb",
            "scenario": "replica-inconsistency",
        },
        tmp_path / "analysis.yaml",
        tmp_path / "analysis.rules-fallback.yaml",
        tmp_path / "report.md",
        matched_skills=[],
    )

    content = task_file.read_text(encoding="utf-8")

    assert "- `deep-analysis.yaml`: materialized read-only deep analysis results." in content
    assert "`analysis.yaml.deep_analysis_results`" in content
    assert "completed=2/2" in content
    assert "`deep-baseline` `baseline_scan` `completed`: Detected baseline invariant violations." in content
    assert "violations=multiple_primary_views" in content
    assert "replica_sets=bnmongo-shard-0" in content
    assert "`deep-path` `code_path_tracing` `completed`: Traced evidence path with 1 missing validation edge." in content
    assert "supports=split_brain_mechanism" in content
    assert "missing_edges=vr-rs-conf:planned" in content
