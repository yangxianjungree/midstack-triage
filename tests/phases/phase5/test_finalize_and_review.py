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
from shared.reasoning_history import write_reasoning_segment


def write_yaml(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def assert_analyse_completed_user_message_table(adapter, incident_dir: Path, *, incident_id: str, statement: str, confidence: str, supported_level: str, primary_cause: str, next_step: str) -> None:
    assert adapter["user_message"] == "\n".join(
        [
            "| Field | Value |",
            "| --- | --- |",
            "| Status | `completed` |",
            "| Incident | `%s` |" % incident_id,
            "| Middleware | `mongodb` |",
            "| Conclusion | %s |" % statement,
            "| Confidence | `%s` |" % confidence,
            "| Supported level | `%s` |" % supported_level,
            "| Primary cause | `%s` |" % primary_cause,
            "| Report | `%s` |" % (incident_dir / "report.md"),
            "| Analysis | `%s` |" % (incident_dir / "analysis.yaml"),
            "| Next | `%s` |" % next_step,
        ]
    )


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
    assert_analyse_completed_user_message_table(
        adapter,
        incident_dir,
        incident_id="demo-incident",
        statement="MongoDB pod restart loop detected",
        confidence="medium",
        supported_level="impact",
        primary_cause="kubernetes-runtime",
        next_step="check pod events",
    )
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


def test_finalize_analysis_appends_agent_refinement_reasoning_segment(tmp_path):
    incident_dir = tmp_path / "incident"
    input_data = {
        "incident_id": "demo-incident",
        "middleware": "mongodb",
        "namespace": "psmdb-test",
        "customer_clue": "mongo split brain",
    }
    rules_analysis = {
        "conclusion_summary": {
            "statement": "Replica member health issue suspected",
            "confidence": "low",
            "deepest_supported_level": "phenomenon",
            "primary_cause_category": "unknown",
            "impact_scope": "shard0",
            "evidence": ["one replica member looks unhealthy"],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "statement": "A replica member health issue caused inconsistency symptoms",
                "supporting_evidence": ["member unhealthy"],
                "validation_result": "insufficient",
            }
        ],
        "next_actions": [{"action": "compare replica member views"}],
    }
    refined_analysis = {
        "conclusion_summary": {
            "statement": "Replica set split brain is confirmed by divergent member views",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replica_set_split_brain",
            "impact_scope": "shard0",
            "evidence": ["data-0 and data-1 both report primary paths"],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "statement": "Replica set members have divergent primary views",
                "supporting_evidence": ["data-0 primary", "data-1 primary"],
                "counter_evidence": [],
                "validation_actions": [{"action": "compare rs.status views", "status": "done"}],
                "validation_result": "supported",
            }
        ],
        "next_actions": [{"action": "compare rs.conf from all members"}],
    }
    write_yaml(incident_dir / "input.yaml", input_data)
    write_yaml(incident_dir / "analysis.rules-fallback.yaml", rules_analysis)
    write_yaml(incident_dir / "analysis.yaml", refined_analysis)
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
    first_segment = write_reasoning_segment(
        incident_dir,
        "rules_fallback",
        rules_analysis,
        summary="rules fallback seeded the first analysis",
        output_refs={"analysis": "analysis.yaml", "report": "report.md", "rules_fallback": "analysis.rules-fallback.yaml"},
    )
    first_content = first_segment.read_text(encoding="utf-8")

    args = SimpleNamespace(output_root=str(tmp_path), incident_dir=str(incident_dir))
    rc = finalize_analysis(args, lambda report: None)

    assert rc == 0
    manifest = yaml.safe_load((incident_dir / "reasoning-manifest.yaml").read_text(encoding="utf-8"))
    adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
    record_ref_names = {item["name"] for item in adapter["record_refs"]}
    second_segment = incident_dir / "reasoning" / "0002-agent-refinement.yaml"
    second = yaml.safe_load(second_segment.read_text(encoding="utf-8"))

    assert first_segment.read_text(encoding="utf-8") == first_content
    assert second_segment.exists()
    assert manifest["current_head"] == "reasoning/0002-agent-refinement.yaml"
    assert [item["source"] for item in manifest["segments"]] == ["rules_fallback", "agent_refinement"]
    assert manifest["segments"][1]["depends_on"] == ["0001-rules-fallback"]
    assert manifest["segments"][1]["supersedes"] == ["0001-rules-fallback"]
    assert second["hypothesis_validations"][0]["isolation"]["private_write_ref"] == "reasoning/0002-agent-refinement.yaml#hypothesis_validations[H1]"
    assert "reasoning_manifest" in record_ref_names
    assert "reasoning_current_segment" in record_ref_names


def test_finalize_demotes_unverified_split_brain_enabling_cause(tmp_path):
    incident_dir = tmp_path / "incident"
    input_data = {
        "incident_id": "demo-incident",
        "middleware": "mongodb",
        "namespace": "psmdb-test",
        "customer_clue": "mongo split brain",
    }
    analysis = {
        "conclusion_summary": {
            "statement": "Split-brain is confirmed; config drift caused divergent decision views.",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replica_set_config_divergence",
            "impact_scope": "shard0",
            "evidence": ["two primary members", "divergent config_version views"],
            "limitations": [],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H3",
                "statement": "Replica set configuration or member metadata drift created divergent decision views.",
                "supporting_evidence": ["divergent config_version views"],
                "counter_evidence": [],
                "validation_actions": [
                    {
                        "action": "Compare read-only rs.conf() output from all affected members.",
                        "status": "planned",
                        "risk_level": "read-only",
                    }
                ],
                "evidence_gaps": [
                    {
                        "gap": "rs.conf() comparison across all affected members is not available",
                        "gap_type": "critical_gap",
                    }
                ],
                "validation_result": "supported",
                "status": "supported",
            }
        ],
        "next_actions": [{"action": "compare rs.conf from all members"}],
    }
    write_yaml(incident_dir / "input.yaml", input_data)
    write_yaml(incident_dir / "analysis.yaml", analysis)
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
    assert finalize_analysis(args, lambda report: None) == 0

    finalized = yaml.safe_load((incident_dir / "analysis.yaml").read_text(encoding="utf-8"))
    report = (incident_dir / "report.md").read_text(encoding="utf-8")

    assert finalized["hypotheses"][0]["status"] == "insufficient"
    assert finalized["hypotheses"][0]["validation_result"] == "insufficient"
    assert finalized["conclusion_summary"]["primary_cause_category"] == "split_brain_enabling_cause_unproven"
    assert "split_brain_enabling_cause_unproven" in report


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
