"""ReasoningBoard单元测试"""

import pytest
from phases.phase4.multitrack.reasoning_board import ReasoningBoard


def test_board_initialization(tmp_path):
    """测试初始化创建空黑板"""
    board = ReasoningBoard(tmp_path)

    assert board.board_path.exists()
    assert board._data["version"] == "1.0"
    assert board._data["incident_id"] == tmp_path.name
    assert len(board._data["findings"]) == 0


def test_add_finding_returns_id(tmp_path):
    """测试add_finding返回正确ID"""
    board = ReasoningBoard(tmp_path)

    finding_id = board.add_finding(
        track_id="track_h1",
        round_num=1,
        finding_type="refutation",
        content="DNS正常",
        evidence=["E_dns_001"],
        affects=[{"hypothesis": "h1", "impact": "refute"}]
    )

    assert finding_id == "F001"
    findings = board.get_all_findings()
    assert len(findings) == 1
    assert findings[0]["content"] == "DNS正常"


def test_hypothesis_status_update(tmp_path):
    """测试假设状态更新"""
    board = ReasoningBoard(tmp_path)

    board.update_hypothesis_status(
        hypothesis_id="h1",
        status="refuted",
        confidence=0.9,
        round_num=1,
        track_id="track_h1"
    )

    status = board.get_hypothesis_status("h1")
    assert status["status"] == "refuted"
    assert status["confidence"] == 0.9


def test_validation_queue(tmp_path):
    """测试验证队列去重"""
    board = ReasoningBoard(tmp_path)

    val_id1 = board.request_validation("check_dns", "track_h1", 1)
    val_id2 = board.request_validation("check_dns", "track_h2", 1)

    # 相同action应该返回同一个ID
    assert val_id1 == val_id2
    assert len(board._data["validation_queue"]) == 1


def test_findings_up_to_round(tmp_path):
    """测试截至某轮的findings（同轮隔离）"""
    board = ReasoningBoard(tmp_path)

    board.add_finding("track_h1", 1, "refutation", "Round 1", [], [])
    board.add_finding("track_h2", 2, "support", "Round 2", [], [])

    findings_r1 = board.get_findings_up_to_round(1)
    assert len(findings_r1) == 1
    assert findings_r1[0]["content"] == "Round 1"


def test_thread_safety(tmp_path):
    """测试线程安全（基础验证）"""
    board = ReasoningBoard(tmp_path)

    # 连续快速写入
    for i in range(10):
        board.add_finding(f"track_{i}", 1, "observation", f"Finding {i}", [], [])

    findings = board.get_all_findings()
    assert len(findings) == 10
    # ID应该连续
    assert findings[9]["id"] == "F010"
