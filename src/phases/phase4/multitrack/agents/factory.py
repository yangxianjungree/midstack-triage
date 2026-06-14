"""Factory for Phase 4 reasoning agents."""

from pathlib import Path
from typing import Optional

from .base import ReasoningAgent
from .claude import ClaudeAgent
from .mock import MockAgent


def bind_incident_dir(agent: ReasoningAgent, incident_dir: Optional[Path | str]) -> ReasoningAgent:
    """Attach the incident directory to agents that support file-backed reasoning."""
    if incident_dir and hasattr(agent, "incident_dir"):
        setattr(agent, "incident_dir", str(incident_dir))
    return agent


class AgentFactory:
    """Agent工厂 - 统一创建入口"""

    @staticmethod
    def create(agent_type: str = "mock", **kwargs) -> ReasoningAgent:
        """Create a reasoning agent for the requested type."""
        incident_dir = kwargs.get("incident_dir")
        if agent_type == "mock":
            return bind_incident_dir(MockAgent(kwargs.get("preset_response")), incident_dir)
        if agent_type == "claude":
            return ClaudeAgent(
                api_key=kwargs.get("api_key"),
                model=kwargs.get("model", "claude-sonnet-4-6"),
                incident_dir=str(incident_dir) if incident_dir else None,
            )
        raise ValueError(f"未知Agent类型: {agent_type}")
