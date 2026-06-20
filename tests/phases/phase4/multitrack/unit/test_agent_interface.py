"""Agent接口单元测试"""

import pytest
from phases.phase4.multitrack.agents import MockAgent, AgentFactory, ClaudeAgent
from phases.phase4.multitrack.agents import factory as agent_factory_module


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


def test_agent_factory_auto_uses_mock_without_api_key(monkeypatch):
    """测试auto模式无API key时安全降级到MockAgent"""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    agent, runtime = AgentFactory.create_with_runtime("auto", incident_dir="/tmp/midstack-phase4")

    assert isinstance(agent, MockAgent)
    assert runtime["requested_type"] == "auto"
    assert runtime["selected_type"] == "mock"
    assert "ANTHROPIC_API_KEY" in runtime["fallback_reason"]


def test_agent_factory_auto_uses_claude_when_api_key_and_sdk_available(monkeypatch):
    """测试auto模式在API key和SDK可用时选择ClaudeAgent"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(agent_factory_module, "anthropic_sdk_available", lambda: True)

    agent, runtime = AgentFactory.create_with_runtime("auto", incident_dir="/tmp/midstack-phase4")

    assert isinstance(agent, ClaudeAgent)
    assert runtime["requested_type"] == "auto"
    assert runtime["selected_type"] == "claude"
    assert runtime["fallback_reason"] == ""


def test_agent_factory_auto_falls_back_when_sdk_missing(monkeypatch):
    """测试auto模式在缺anthropic SDK时安全降级到MockAgent"""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(agent_factory_module, "anthropic_sdk_available", lambda: False)

    agent, runtime = AgentFactory.create_with_runtime("auto", incident_dir="/tmp/midstack-phase4")

    assert isinstance(agent, MockAgent)
    assert runtime["selected_type"] == "mock"
    assert "anthropic package" in runtime["fallback_reason"]


def test_agent_factory_invalid():
    """测试无效Agent类型"""
    with pytest.raises(ValueError, match="未知Agent类型"):
        AgentFactory.create("invalid")
