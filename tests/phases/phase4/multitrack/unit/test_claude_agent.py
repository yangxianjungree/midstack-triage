"""ClaudeAgent测试"""

import pytest
from unittest.mock import Mock, patch
from phases.phase4.multitrack.agents import ClaudeAgent


def test_claude_agent_requires_api_key():
    """测试必须提供API key"""
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        ClaudeAgent(api_key=None)


def test_claude_agent_prompt_building():
    """测试prompt构建"""
    agent = ClaudeAgent(api_key="test-key")

    observations = {
        "hypothesis_status": {
            "h1": {"status": "supported", "confidence": 0.8}
        },
        "recent_findings": [
            {"type": "support", "content": "发现支持证据"}
        ],
        "my_validations": [],
        "refutations_against_me": []
    }

    prompt = agent._build_prompt(observations)

    assert "故障根因分析" in prompt
    assert "hypothesis_status" in prompt
    assert "JSON" in prompt


def test_claude_agent_response_parsing():
    """测试响应解析"""
    agent = ClaudeAgent(api_key="test-key")

    response_text = """{
        "hypothesis_status": "supported",
        "confidence": 0.85,
        "reasoning": "证据充分",
        "validation_actions": [],
        "findings": []
    }"""

    result = agent._parse_response(response_text)

    assert result["hypothesis_status"] == "supported"
    assert result["confidence"] == 0.85
    assert "causal_chain_update" in result


def test_claude_agent_response_parsing_preserves_evidence_refs():
    """测试响应解析会保留当前incident证据引用"""
    agent = ClaudeAgent(api_key="test-key")

    response_text = """{
        "hypothesis_status": "supported",
        "confidence": 0.91,
        "reasoning": "证据充分",
        "evidence_refs": [
            "structured_record.details.replica_members",
            "signal_bundle.topology.replica_sets.rs0"
        ],
        "validation_actions": [],
        "findings": []
    }"""

    result = agent._parse_response(response_text)

    assert result["evidence_refs"] == [
        "structured_record.details.replica_members",
        "signal_bundle.topology.replica_sets.rs0",
    ]


def test_claude_agent_response_parsing_preserves_conclusion_candidate():
    """测试响应解析会保留结构化结论候选"""
    agent = ClaudeAgent(api_key="test-key")

    response_text = """{
        "hypothesis_status": "supported",
        "confidence": 0.91,
        "reasoning": "证据充分",
        "evidence_refs": ["structured_record.details.replica_members"],
        "conclusion_candidate": {
            "statement": "Replica set rs0 has a split-brain mechanism.",
            "confidence": "medium",
            "deepest_supported_level": "mechanism",
            "primary_cause_category": "replica_set_split_brain",
            "impact_scope": "rs0 availability",
            "evidence": ["structured_record.details.replica_members"],
            "limitations": []
        },
        "validation_actions": [],
        "findings": []
    }"""

    result = agent._parse_response(response_text)

    assert result["conclusion_candidate"]["statement"] == "Replica set rs0 has a split-brain mechanism."
    assert result["conclusion_candidate"]["deepest_supported_level"] == "mechanism"


@pytest.mark.skipif(True, reason="需要anthropic包才能mock")
@patch('anthropic.Anthropic')
def test_claude_agent_api_call(mock_anthropic):
    """测试API调用（mock）"""
    # Mock API响应
    mock_client = Mock()
    mock_response = Mock()
    mock_response.content = [Mock(text='{"hypothesis_status": "supported", "confidence": 0.8, "reasoning": "测试"}')]
    mock_client.messages.create.return_value = mock_response
    mock_anthropic.return_value = mock_client

    agent = ClaudeAgent(api_key="test-key")
    agent.client = mock_client

    observations = {
        "hypothesis_status": {},
        "recent_findings": [],
        "my_validations": [],
        "refutations_against_me": []
    }

    result = agent.reason(observations)

    assert result["hypothesis_status"] == "supported"
    assert mock_client.messages.create.called


def test_claude_agent_error_fallback():
    """测试错误时的fallback"""
    agent = ClaudeAgent(api_key="test-key")
    agent.client = Mock()
    agent.client.messages.create.side_effect = Exception("API错误")

    result = agent.reason({})

    assert result["hypothesis_status"] == "insufficient"
    assert "Agent调用失败" in result["reasoning"]
