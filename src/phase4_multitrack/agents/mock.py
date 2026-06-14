"""Mock reasoning agent used by tests and default local flows."""

from typing import Dict, Optional


class MockAgent:
    """Mock Agent - 用于测试"""

    def __init__(self, preset_response: Optional[Dict] = None):
        self.preset_response = preset_response or {
            "hypothesis_status": "pending",
            "confidence": 0.5,
            "reasoning": "Mock推理中",
            "validation_actions": [],
            "findings": [],
            "causal_chain_update": None,
        }
        self.call_count = 0
        self.last_observations = None

    def reason(self, observations: Dict) -> Dict:
        """返回预设响应"""
        self.call_count += 1
        self.last_observations = observations
        return self.preset_response
