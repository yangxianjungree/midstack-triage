import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.planner import build_l1_output


def test_build_l1_output_uses_first_signal_detail_and_middleware():
    signal_bundle = {
        "middleware": "mongodb",
        "abnormal_signals": [
            {"detail": "dns resolution failed"},
            {"detail": "ignored"},
        ],
    }

    l1_output = build_l1_output(signal_bundle)

    assert l1_output["primary_symptom"] == "dns resolution failed"
    assert l1_output["affected_component"] == "mongodb"
