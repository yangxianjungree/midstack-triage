import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.renderer import format_analysis_output


def test_format_analysis_output_selects_highest_confidence_hypothesis():
    phase4_result = {
        "total_rounds": 3,
        "hypotheses": [
            {
                "final_text": "DNS evidence is insufficient",
                "status": {"status": "insufficient", "confidence": 0.4},
            },
            {
                "final_text": "Pod storage pressure caused restarts",
                "status": {"status": "supported", "confidence": 0.9},
            },
        ],
    }

    analysis = format_analysis_output(phase4_result, {"middleware": "mongodb"})

    assert analysis["conclusion_summary"]["statement"] == "Pod storage pressure caused restarts"
    assert analysis["conclusion_summary"]["confidence"] == "high"
    assert analysis["conclusion_summary"]["impact_scope"] == "mongodb availability"
    assert analysis["reasoning_process"]["total_rounds"] == 3
    assert analysis["reasoning_process"]["hypotheses_evaluated"] == 2
