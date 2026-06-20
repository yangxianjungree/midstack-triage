"""LeadOrchestrator单元测试"""

import pytest
from phases.phase4.multitrack import LeadOrchestrator, ReasoningBoard


def test_orchestrator_initialization(tmp_path):
    """测试协调器初始化"""
    hypotheses = ["DNS配置错误", "网络分区", "服务过载"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    assert len(orch.tracks) == 3
    assert orch.current_round == 0
    assert all(t.is_active for t in orch.tracks.values())


def test_orchestrator_records_agent_runtime_fallback(tmp_path, monkeypatch):
    """测试auto模式降级信息落入result和reasoning-board"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    hypotheses = ["DNS配置错误"]

    orch = LeadOrchestrator(tmp_path, hypotheses, agent_type="auto")
    result = orch.run()

    assert result["agent_runtime"]["requested_type"] == "auto"
    assert result["agent_runtime"]["selected_type"] == "mock"
    assert "ANTHROPIC_API_KEY" in result["agent_runtime"]["fallback_reason"]

    board = ReasoningBoard(tmp_path)
    assert board.get_agent_runtime()["selected_type"] == "mock"


def test_single_round_execution(tmp_path):
    """测试单轮执行"""
    hypotheses = ["DNS配置错误"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    # Mock推理结果
    for track in orch.tracks.values():
        track._reason = lambda obs: {
            "hypothesis_status": "supported",
            "confidence": 0.9,
            "reasoning": "证据充分",
            "validation_actions": [],
            "findings": [],
            "causal_chain_update": None
        }

    result = orch.run()

    assert orch.current_round >= 1
    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["status"]["status"] == "supported"


def test_termination_on_high_confidence(tmp_path):
    """测试高置信度时提前终止"""
    hypotheses = ["DNS配置错误"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    for track in orch.tracks.values():
        track._reason = lambda obs: {
            "hypothesis_status": "supported",
            "confidence": 0.9,
            "reasoning": "证据充分",
            "validation_actions": [],
            "findings": [],
            "causal_chain_update": None
        }

    result = orch.run()

    assert orch.current_round < orch.max_rounds


def test_validation_queue_execution(tmp_path):
    """测试验证队列执行"""
    hypotheses = ["DNS配置错误"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    for track in orch.tracks.values():
        track._reason = lambda obs: {
            "hypothesis_status": "pending",
            "confidence": 0.5,
            "reasoning": "需要验证",
            "validation_actions": [{"action": "check_dns"}],
            "findings": [],
            "causal_chain_update": None
        }

    orch.current_round = 1
    active_tracks = [t for t in orch.tracks.values() if t.is_active]
    orch._run_phase_r1(active_tracks)

    pending = orch.board.get_pending_validations()
    assert len(pending) == 1

    results = orch._run_phase_v()
    assert len(results) == 1
