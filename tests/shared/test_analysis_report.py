import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.analysis_runtime import write_report


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
