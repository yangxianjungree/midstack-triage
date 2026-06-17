from pathlib import Path
from types import SimpleNamespace

import sys
import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase5.finalize import finalize_analysis
from phases.phase5.review import build_review_block, run_review


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_finalize_analysis_writes_adapter_output_and_report(tmp_path):
    incident_dir = tmp_path / "incident"
    write_yaml(
        incident_dir / "input.yaml",
        {
            "incident_id": "demo-incident",
            "middleware": "mongodb",
            "namespace": "psmdb-test",
            "customer_clue": "mongo down",
        },
    )
    write_yaml(
        incident_dir / "analysis.yaml",
        {
            "conclusion_summary": {
                "statement": "MongoDB pod restart loop detected",
                "confidence": "medium",
                "deepest_supported_level": "impact",
                "primary_cause_category": "kubernetes-runtime",
                "impact_scope": "shard0",
                "evidence": ["pod crashloop observed"],
            },
            "hypotheses": [],
            "next_actions": [{"action": "check pod events"}],
        },
    )
    (incident_dir / "report.md").write_text("# draft\n", encoding="utf-8")
    write_yaml(incident_dir / "collection_report.yaml", {"evidence_gaps": []})
    write_yaml(incident_dir / "signal_bundle.yaml", {"abnormal_signals": []})
    write_yaml(
        incident_dir / "meta.yaml",
        {
            "incident_id": "demo-incident",
            "middleware": "mongodb",
            "status": "analysing",
            "current_command": "analyse",
        },
    )

    args = SimpleNamespace(output_root=str(tmp_path), incident_dir=str(incident_dir))
    rc = finalize_analysis(args, lambda report: None)

    assert rc == 0
    adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
    assert adapter["status"] == "completed"
    assert adapter["next_actions"] == ["check pod events"]
    meta = yaml.safe_load((incident_dir / "meta.yaml").read_text(encoding="utf-8"))
    assert meta["status"] == "analysed"


def test_finalize_analysis_completed_output_includes_expected_refs(tmp_path):
    incident_dir = tmp_path / "incident"
    write_yaml(
        incident_dir / "input.yaml",
        {
            "incident_id": "demo-incident",
            "middleware": "mongodb",
            "namespace": "psmdb-test",
            "customer_clue": "mongo down",
        },
    )
    write_yaml(
        incident_dir / "analysis.yaml",
        {
            "conclusion_summary": {
                "statement": "MongoDB pod restart loop detected",
                "confidence": "medium",
                "deepest_supported_level": "impact",
                "primary_cause_category": "kubernetes-runtime",
                "impact_scope": "shard0",
                "evidence": ["pod crashloop observed"],
            },
            "hypotheses": [],
            "next_actions": [{"action": "check pod events"}],
        },
    )
    (incident_dir / "report.md").write_text("# draft\n", encoding="utf-8")
    write_yaml(incident_dir / "collection_report.yaml", {"evidence_gaps": []})
    write_yaml(incident_dir / "signal_bundle.yaml", {"abnormal_signals": []})
    write_yaml(
        incident_dir / "meta.yaml",
        {
            "incident_id": "demo-incident",
            "middleware": "mongodb",
            "status": "analysing",
            "current_command": "analyse",
        },
    )

    args = SimpleNamespace(output_root=str(tmp_path), incident_dir=str(incident_dir))
    rc = finalize_analysis(args, lambda report: None)

    assert rc == 0
    adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
    record_ref_names = {item["name"] for item in adapter["record_refs"]}
    assert "analysis" in record_ref_names
    assert "report" in record_ref_names
    assert "analysis_rules_fallback" not in record_ref_names
    assert adapter["status"] == "completed"
    assert adapter["next_actions"] == ["check pod events"]


def test_build_review_block_scores_supported_analysis():
    review = build_review_block(
        {
            "conclusion_summary": {
                "statement": "impact confirmed",
                "confidence": "medium",
                "deepest_supported_level": "impact",
                "primary_cause_category": "kubernetes-runtime",
                "evidence": ["probe failures"],
            },
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "status": "supported",
                    "validation_actions": ["checked pod events"],
                }
            ],
            "knowledge_candidates": [],
            "next_actions": [{"action": "inspect coredns"}],
        }
    )

    assert review["overall"]["level"] in ("medium", "high")
    assert "evidence_completeness" in review["score"]
    assert isinstance(review["improvement_suggestions"], list)
    assert isinstance(review["regression_risks"], list)


def test_run_review_writes_review_block_and_adapter_output(tmp_path):
    incident_dir = tmp_path / "incident"
    write_yaml(
        incident_dir / "input.yaml",
        {
            "incident_id": "review-incident",
            "middleware": "mongodb",
        },
    )
    write_yaml(
        incident_dir / "analysis.yaml",
        {
            "conclusion_summary": {
                "statement": "impact confirmed",
                "confidence": "medium",
                "deepest_supported_level": "impact",
                "primary_cause_category": "kubernetes-runtime",
                "evidence": ["probe failures"],
            },
            "hypotheses": [
                {
                    "hypothesis_id": "H1",
                    "status": "supported",
                    "validation_actions": ["checked pod events"],
                }
            ],
            "knowledge_candidates": [],
            "next_actions": [{"action": "inspect coredns"}],
        },
    )
    write_yaml(
        incident_dir / "meta.yaml",
        {
            "incident_id": "review-incident",
            "middleware": "mongodb",
            "status": "analysed",
            "current_command": "analyse",
        },
    )

    args = SimpleNamespace(output_root=str(tmp_path), incident_dir=str(incident_dir))
    rc = run_review(args)

    assert rc == 0
    analysis = yaml.safe_load((incident_dir / "analysis.yaml").read_text(encoding="utf-8"))
    assert analysis["review"]["overall"]["level"] in ("medium", "high")
    adapter = yaml.safe_load((incident_dir / "review-adapter-output.yaml").read_text(encoding="utf-8"))
    assert adapter["status"] == "completed"
    meta = yaml.safe_load((incident_dir / "meta.yaml").read_text(encoding="utf-8"))
    assert meta["status"] == "reviewed"
