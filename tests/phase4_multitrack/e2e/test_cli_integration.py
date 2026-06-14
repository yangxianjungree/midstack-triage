"""端到端集成测试 - 验证完整工作流程"""

import subprocess
import sys
from pathlib import Path

import yaml


def test_e2e_cli_integration(tmp_path):
    """测试CLI完整集成：从incident到analysis输出"""

    fixture_dir = Path("tests/fixtures/mongodb/kubernetes-readiness-failure-sample")
    incident_dir = tmp_path / "phase4-cli-output"

    # 运行CLI分析
    result = subprocess.run(
        [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "analyse",
            "--input-dir",
            str(fixture_dir),
            "--output-dir",
            str(incident_dir),
        ],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, result.stderr

    # 验证Phase 4输出
    analysis_file = incident_dir / "analysis.yaml"
    board_file = incident_dir / "reasoning-board.yaml"

    assert analysis_file.exists(), "缺少analysis.yaml"
    assert board_file.exists(), "缺少reasoning-board.yaml"

    # 验证analysis.yaml格式
    with open(analysis_file) as f:
        analysis = yaml.safe_load(f)

    assert "conclusion_summary" in analysis
    assert "statement" in analysis["conclusion_summary"]
    assert "confidence" in analysis["conclusion_summary"]

    # 验证reasoning-board.yaml格式
    with open(board_file) as f:
        board = yaml.safe_load(f)

    assert "hypothesis_status" in board
    assert "findings" in board
    assert "version" in board

    print("\n=== 验证通过 ===")
    print(f"Analysis: {analysis['conclusion_summary']['statement']}")
    print(f"Confidence: {analysis['conclusion_summary']['confidence']}")
    print(f"Hypotheses: {len(board['hypothesis_status'])}")
