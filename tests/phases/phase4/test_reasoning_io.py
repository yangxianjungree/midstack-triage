import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from phases.phase4.reasoning import MULTITRACK_ANALYSIS_FILENAME, write_analysis  # noqa: E402


def test_write_analysis_preserves_unicode_text_in_multitrack_artifact(tmp_path):
    write_analysis(tmp_path, {"summary": "诊断完成"})

    content = (tmp_path / MULTITRACK_ANALYSIS_FILENAME).read_text(encoding="utf-8")
    assert "诊断完成" in content
    assert yaml.safe_load(content) == {"summary": "诊断完成"}
    assert not (tmp_path / "analysis.yaml").exists()
