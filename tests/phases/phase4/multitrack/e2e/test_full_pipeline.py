"""E2E完整流程测试"""

import pytest
from phases.phase4.multitrack import LeadOrchestrator, L1TemplateMapper


def test_e2e_single_hypothesis_supported(tmp_path, mock_agent_supported):
    """E2E: 单假设被支持"""
    hypotheses = ["MongoDB复制集状态异常"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    for track in orch.tracks.values():
        track._reason = lambda obs: mock_agent_supported.reason(obs)

    result = orch.run()

    assert result["total_rounds"] >= 1
    assert len(result["hypotheses"]) == 1
    assert result["hypotheses"][0]["status"]["status"] == "supported"


def test_e2e_multi_hypothesis_convergence(tmp_path, mock_agent_supported, mock_agent_refuted):
    """E2E: 多假设收敛"""
    hypotheses = ["假设A", "假设B"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    tracks = list(orch.tracks.values())
    tracks[0]._reason = lambda obs: mock_agent_supported.reason(obs)
    tracks[1]._reason = lambda obs: mock_agent_refuted.reason(obs)

    result = orch.run()

    assert len(result["hypotheses"]) == 2
    statuses = [h["status"]["status"] for h in result["hypotheses"]]
    assert "supported" in statuses
    assert "refuted" in statuses


def test_e2e_l1_to_phase4_pipeline(tmp_path, sample_l1_output, mock_agent_iterative):
    """E2E: L1输出 → Phase4推理"""
    mapper = L1TemplateMapper()
    hypotheses = mapper.map_from_l1_output(sample_l1_output)

    orch = LeadOrchestrator(tmp_path, hypotheses)

    for track in orch.tracks.values():
        track._reason = lambda obs: mock_agent_iterative.reason(obs)

    result = orch.run()

    assert result["total_rounds"] >= 1
    assert len(result["hypotheses"]) > 0


def test_e2e_validation_flow(tmp_path):
    """E2E: 验证流程"""
    hypotheses = ["测试假设"]
    orch = LeadOrchestrator(tmp_path, hypotheses)

    for track in orch.tracks.values():
        track._reason = lambda obs: {
            "hypothesis_status": "pending",
            "confidence": 0.5,
            "reasoning": "需要验证",
            "validation_actions": [{"action": "test_action"}],
            "findings": [],
            "causal_chain_update": None
        }

    orch.current_round = 1
    active = [t for t in orch.tracks.values() if t.is_active]
    orch._run_phase_r1(active)

    pending = orch.board.get_pending_validations()
    assert len(pending) == 1

    orch._run_phase_v()

    completed = orch.board._data["executed_validations"]
    assert len(completed) > 0
