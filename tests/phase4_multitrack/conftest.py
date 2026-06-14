"""测试fixtures和mock"""

import pytest
from pathlib import Path
from typing import Dict, List


@pytest.fixture
def incident_dir(tmp_path):
    """临时incident目录"""
    return tmp_path / "test_incident"


@pytest.fixture
def sample_hypotheses():
    """示例假设列表"""
    return [
        "MongoDB复制集状态异常",
        "网络分区导致连接失败",
        "资源配额限制"
    ]


@pytest.fixture
def sample_l1_output():
    """示例L1输出"""
    return {
        "primary_symptom": "connection refused",
        "affected_component": "mongodb",
        "timestamp": "2026-06-13T04:00:00Z"
    }


class MockReasoningAgent:
    """Mock推理Agent"""

    def __init__(self, responses: List[Dict]):
        self.responses = responses
        self.call_count = 0

    def reason(self, observations: Dict) -> Dict:
        """返回预设响应"""
        if self.call_count >= len(self.responses):
            return self.responses[-1]

        response = self.responses[self.call_count]
        self.call_count += 1
        return response


@pytest.fixture
def mock_agent_supported():
    """返回supported状态的mock agent"""
    return MockReasoningAgent([{
        "hypothesis_status": "supported",
        "confidence": 0.9,
        "reasoning": "证据充分支持假设",
        "validation_actions": [],
        "findings": [{
            "type": "support",
            "content": "发现支持证据",
            "evidence": ["E001"],
            "affects": []
        }],
        "causal_chain_update": None
    }])


@pytest.fixture
def mock_agent_refuted():
    """返回refuted状态的mock agent"""
    return MockReasoningAgent([{
        "hypothesis_status": "refuted",
        "confidence": 0.9,
        "reasoning": "证据反驳假设",
        "validation_actions": [],
        "findings": [{
            "type": "refutation",
            "content": "发现反驳证据",
            "evidence": ["E002"],
            "affects": []
        }],
        "causal_chain_update": None
    }])


@pytest.fixture
def mock_agent_iterative():
    """多轮迭代的mock agent"""
    return MockReasoningAgent([
        {
            "hypothesis_status": "pending",
            "confidence": 0.3,
            "reasoning": "需要更多证据",
            "validation_actions": [{"action": "check_logs"}],
            "findings": [],
            "causal_chain_update": None
        },
        {
            "hypothesis_status": "pending",
            "confidence": 0.6,
            "reasoning": "发现部分证据",
            "validation_actions": [{"action": "check_metrics"}],
            "findings": [],
            "causal_chain_update": None
        },
        {
            "hypothesis_status": "supported",
            "confidence": 0.85,
            "reasoning": "证据汇总支持假设",
            "validation_actions": [],
            "findings": [],
            "causal_chain_update": None
        }
    ])
