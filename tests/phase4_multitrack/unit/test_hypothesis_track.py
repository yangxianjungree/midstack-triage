"""HypothesisTrack单元测试"""

import pytest
from phase4_multitrack import HypothesisTrack, ReasoningBoard


def test_track_initialization(tmp_path):
    """测试轨初始化"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    assert track.track_id == "track_h1"
    assert track.hypothesis_id == "h1"
    assert track.current_round == 0
    assert track.is_active is True
    assert len(track.hypothesis_evolution) == 1
    assert track.get_current_hypothesis() == "DNS配置错误"


def test_phase_r1_requests_validation(tmp_path):
    """测试Phase R1请求验证"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    # Mock推理结果
    track._reason = lambda obs: {
        "hypothesis_status": "pending",
        "confidence": 0.6,
        "reasoning": "需要验证DNS",
        "validation_actions": [{"action": "check_dns"}],
        "findings": [],
        "causal_chain_update": None
    }

    track.run_phase_r1(round_num=1)

    # 验证请求已添加
    pending = board.get_pending_validations()
    assert len(pending) == 1
    assert pending[0]["action"] == "check_dns"


def test_phase_r2_processes_validation_results(tmp_path):
    """测试Phase R2处理验证结果"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    # 模拟R1
    track.current_round = 1
    track._pending_reasoning_result = {
        "hypothesis_status": "pending",
        "confidence": 0.5,
        "reasoning": "等待验证"
    }

    # 添加验证结果
    val_id = board.request_validation("check_dns", "track_h1", 1)
    board.add_validation_result(
        "E_dns_001",
        "check_dns",
        "DNS正常",
        "refutation",
        {},
        ["track_h1"]
    )
    board.mark_validation_completed(val_id, "E_dns_001")

    track.run_phase_r2(round_num=1)

    # 验证状态更新为refuted
    status = board.get_hypothesis_status("h1")
    assert status["status"] == "refuted"
    assert status["confidence"] == 0.9


def test_track_stops_when_refuted(tmp_path):
    """测试轨在refuted时停止"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    track._pending_reasoning_result = {
        "hypothesis_status": "refuted",
        "confidence": 0.9,
        "reasoning": "证据反驳"
    }
    track.run_phase_r2(round_num=1)

    assert track.is_active is False


def test_cross_refutation_written_to_board(tmp_path):
    """测试跨轨反证写入黑板"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    track._reason = lambda obs: {
        "hypothesis_status": "pending",
        "confidence": 0.5,
        "reasoning": "",
        "validation_actions": [],
        "findings": [],
        "cross_refutations": [{
            "to_hypothesis": "h2",
            "reason": "DNS正常，排除网络层问题",
            "confidence": 0.8
        }],
        "causal_chain_update": None
    }

    track.run_phase_r1(round_num=1)

    refutations = board.get_refutations_for_hypothesis("h2")
    assert len(refutations) == 1
    assert refutations[0]["from_track"] == "track_h1"


def test_private_context_export(tmp_path):
    """测试隔离上下文导出"""
    board = ReasoningBoard(tmp_path)
    track = HypothesisTrack("track_h1", "h1", "DNS配置错误", board)

    context = track.get_private_context()

    assert context["track_id"] == "track_h1"
    assert context["hypothesis_id"] == "h1"
    assert len(context["hypothesis_evolution"]) == 1
    assert context["is_active"] is True
