"""Factory for Phase 4 reasoning agents."""

from .base import ReasoningAgent
from .claude import ClaudeAgent
from .mock import MockAgent


class AgentFactory:
    """Agent工厂 - 统一创建入口"""

    @staticmethod
    def create(agent_type: str = "mock", **kwargs) -> ReasoningAgent:
        """Create a reasoning agent for the requested type."""
        if agent_type == "mock":
            return MockAgent(kwargs.get("preset_response"))
        if agent_type == "claude":
            return ClaudeAgent(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "claude-sonnet-4-6"),
            )
        raise ValueError(f"未知Agent类型: {agent_type}")
