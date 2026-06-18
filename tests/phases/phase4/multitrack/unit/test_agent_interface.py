"""Agent接口单元测试"""

import pytest
from phases.phase4.multitrack.agents import MockAgent, AgentFactory, ClaudeAgent


def test_mock_agent_basic():
    """测试MockAgent基础功能"""
    agent = MockAgent()
    obs = {"base_evidence": {}}
    result = agent.reason(obs)

    assert result["hypothesis_status"] == "pending"
    assert agent.call_count == 1
    assert agent.last_observations == obs


def test_mock_agent_with_preset():
    """测试MockAgent使用预设响应"""
    preset = {
        "hypothesis_status": "supported",
        "confidence": 0.9,
        "reasoning": "测试",
        "validation_actions": [],
        "findings": [],
        "causal_chain_update": None
    }
    agent = MockAgent(preset)
    result = agent.reason({})

    assert result["hypothesis_status"] == "supported"
    assert result["confidence"] == 0.9


def test_agent_factory_mock():
    """测试AgentFactory创建MockAgent"""
    agent = AgentFactory.create("mock")
    assert isinstance(agent, MockAgent)


def test_agent_factory_claude():
    """测试AgentFactory创建ClaudeAgent"""
    agent = AgentFactory.create("claude", api_key="test_key", incident_dir="/tmp/midstack-phase4")
    assert isinstance(agent, ClaudeAgent)
    assert agent.incident_dir == "/tmp/midstack-phase4"


def test_agent_factory_invalid():
    """测试无效Agent类型"""
    with pytest.raises(ValueError, match="未知Agent类型"):
        AgentFactory.create("invalid")
