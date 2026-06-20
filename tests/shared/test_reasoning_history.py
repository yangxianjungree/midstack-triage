from pathlib import Path

import sys
import yaml


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.reasoning_history import write_reasoning_segment


def _analysis(statement: str):
    return {
        "conclusion_summary": {
            "statement": statement,
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replica_set_split_brain",
            "impact_scope": "shard0",
            "evidence": ["rs.status views diverge"],
        },
        "hypotheses": [
            {
                "hypothesis_id": "H1",
                "statement": "replica set members have divergent views",
                "supporting_evidence": ["data-0 reports itself primary", "data-1 reports data-0 unreachable"],
                "counter_evidence": ["node resources are healthy"],
                "evidence_gaps": [{"gap": "missing rs.conf from all members", "gap_type": "critical_gap"}],
                "validation_actions": [{"action": "compare rs.conf from all members", "status": "planned"}],
                "validation_result": "supported",
            },
            {
                "hypothesis_id": "H2",
                "statement": "node resource pressure caused elections",
                "supporting_evidence": [],
                "counter_evidence": ["CPU and memory are below threshold"],
                "validation_actions": [{"action": "check node pressure", "status": "done"}],
                "validation_result": "refuted",
            },
        ],
        "verification_requests": [
            {
                "request_id": "VR1",
                "hypothesis_id": "H1",
                "summary": "Read-only rs.conf comparison",
                "execution_policy": "planned",
            }
        ],
    }


def _analysis_with_agent_gate():
    analysis = _analysis("agent draft was evaluated")
    analysis["agent_conclusion_gate"] = {
        "schema_version": "agent-conclusion-gate.v1",
        "decision": "blocked",
        "override_applied": False,
        "selected_candidate": {
            "hypothesis_id": "h1",
            "statement": "Agent split-brain candidate",
            "confidence": 0.91,
        },
        "blockers": [
            {
                "code": "unresolved_critical_gap",
                "message": "critical evidence gaps remain unresolved",
            }
        ],
    }
    return analysis


def _write_incident_inputs(incident_dir: Path) -> None:
    for name in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml"):
        (incident_dir / name).parent.mkdir(parents=True, exist_ok=True)
        (incident_dir / name).write_text("generated_at: test\n", encoding="utf-8")


def test_write_reasoning_segment_creates_manifest_and_isolated_hypothesis_records(tmp_path):
    incident_dir = tmp_path / "incident"
    _write_incident_inputs(incident_dir)

    segment_path = write_reasoning_segment(
        incident_dir,
        "rules_fallback",
        _analysis("split brain detected"),
        summary="rules fallback seeded the first analysis",
        output_refs={"analysis": "analysis.yaml", "report": "report.md"},
        executed_validations=[
            {
                "request_id": "VR1",
                "hypothesis_id": "H1",
                "asset": {"type": "script", "id": "mongodb.collect.replicaset.rs_conf"},
                "status": "success",
                "output_ref": "script_outputs/mongodb.collect.replicaset.rs_conf/output.yaml",
            }
        ],
    )

    manifest = yaml.safe_load((incident_dir / "reasoning-manifest.yaml").read_text(encoding="utf-8"))
    segment = yaml.safe_load(segment_path.read_text(encoding="utf-8"))
    segment_text = segment_path.read_text(encoding="utf-8")

    assert segment_path == incident_dir / "reasoning" / "0001-rules-fallback.yaml"
    assert manifest["schema_version"] == "reasoning-history.v1"
    assert manifest["current_head"] == "reasoning/0001-rules-fallback.yaml"
    assert manifest["segments"][0]["segment_id"] == "0001-rules-fallback"
    assert manifest["materialized_outputs"]["analysis"] == "analysis.yaml"
    assert manifest["shared_evidence_pool"]["access"] == "read_only"
    assert {item["path"] for item in manifest["shared_evidence_pool"]["refs"]} >= {
        "input.yaml",
        "structured_record.yaml",
        "signal_bundle.yaml",
        "collection_report.yaml",
    }

    assert segment["schema_version"] == "reasoning-segment.v1"
    assert segment["source"] == "rules_fallback"
    assert segment["shared_evidence_pool"]["access"] == "read_only"
    assert segment["executed_validations"][0]["request_id"] == "VR1"
    assert segment["executed_validations"][0]["status"] == "success"
    validations = segment["hypothesis_validations"]
    assert [item["hypothesis_id"] for item in validations] == ["H1", "H2"]
    assert all(item["isolation"]["scope"] == "hypothesis_validation" for item in validations)
    assert all(item["isolation"]["shared_read_refs"] for item in validations)
    assert validations[0]["isolation"]["private_write_ref"] == "reasoning/0001-rules-fallback.yaml#hypothesis_validations[H1]"
    assert validations[0]["verification_requests"][0]["request_id"] == "VR1"
    assert validations[1]["result"]["validation_result"] == "refuted"
    assert "&id" not in segment_text
    assert "*id" not in segment_text


def test_write_reasoning_segment_appends_without_modifying_previous_segment(tmp_path):
    incident_dir = tmp_path / "incident"
    _write_incident_inputs(incident_dir)

    first_path = write_reasoning_segment(
        incident_dir,
        "rules_fallback",
        _analysis("initial split brain hypothesis"),
        summary="initial draft",
    )
    first_content = first_path.read_text(encoding="utf-8")

    second_path = write_reasoning_segment(
        incident_dir,
        "agent_refinement",
        _analysis("split brain confirmed by divergent member views"),
        summary="agent refined the mechanism",
        depends_on=["0001-rules-fallback"],
        supersedes=["0001-rules-fallback"],
    )

    manifest = yaml.safe_load((incident_dir / "reasoning-manifest.yaml").read_text(encoding="utf-8"))

    assert first_path.read_text(encoding="utf-8") == first_content
    assert second_path == incident_dir / "reasoning" / "0002-agent-refinement.yaml"
    assert manifest["current_head"] == "reasoning/0002-agent-refinement.yaml"
    assert [item["segment_id"] for item in manifest["segments"]] == [
        "0001-rules-fallback",
        "0002-agent-refinement",
    ]
    assert manifest["segments"][1]["depends_on"] == ["0001-rules-fallback"]
    assert manifest["segments"][1]["supersedes"] == ["0001-rules-fallback"]


def test_write_reasoning_segment_records_agent_conclusion_gate(tmp_path):
    incident_dir = tmp_path / "incident"
    _write_incident_inputs(incident_dir)

    segment_path = write_reasoning_segment(
        incident_dir,
        "agent_multitrack",
        _analysis_with_agent_gate(),
        summary="agent draft evaluated",
    )

    manifest = yaml.safe_load((incident_dir / "reasoning-manifest.yaml").read_text(encoding="utf-8"))
    segment = yaml.safe_load(segment_path.read_text(encoding="utf-8"))

    assert segment["agent_conclusion_gate"]["decision"] == "blocked"
    assert segment["agent_conclusion_gate"]["override_applied"] is False
    assert segment["agent_conclusion_gate"]["blockers"][0]["code"] == "unresolved_critical_gap"
    assert manifest["segments"][0]["agent_conclusion_gate"]["decision"] == "blocked"
    assert manifest["segments"][0]["agent_conclusion_gate"]["blocker_count"] == 1
