"""Factory for Phase 4 reasoning agents."""

import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from .base import ReasoningAgent
from .claude import ClaudeAgent
from .mock import MockAgent


DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"


def bind_incident_dir(agent: ReasoningAgent, incident_dir: Optional[Path | str]) -> ReasoningAgent:
    """Attach the incident directory to agents that support file-backed reasoning."""
    if incident_dir and hasattr(agent, "incident_dir"):
        setattr(agent, "incident_dir", str(incident_dir))
    return agent


def anthropic_sdk_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


class AgentFactory:
    """Agent工厂 - 统一创建入口"""

    @staticmethod
    def create(agent_type: str = "mock", **kwargs) -> ReasoningAgent:
        """Create a reasoning agent for the requested type."""
        agent, _runtime = AgentFactory.create_with_runtime(agent_type, **kwargs)
        return agent

    @staticmethod
    def create_with_runtime(agent_type: str = "mock", **kwargs) -> Tuple[ReasoningAgent, Dict[str, str]]:
        """Create a reasoning agent and return the selected runtime metadata."""
        incident_dir = kwargs.get("incident_dir")
        requested_type = str(agent_type or "mock").strip().lower()
        selected_type = requested_type
        fallback_reason = ""

        if requested_type == "auto":
            if not (kwargs.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")):
                selected_type = "mock"
                fallback_reason = "ANTHROPIC_API_KEY is not set; falling back to mock Phase 4 agent"
            elif not anthropic_sdk_available():
                selected_type = "mock"
                fallback_reason = "anthropic package is not installed; falling back to mock Phase 4 agent"
            else:
                selected_type = "claude"

        runtime = {
            "requested_type": requested_type,
            "selected_type": selected_type,
            "fallback_reason": fallback_reason,
            "model": str(kwargs.get("model") or DEFAULT_CLAUDE_MODEL),
        }

        if selected_type == "mock":
            return bind_incident_dir(MockAgent(kwargs.get("preset_response")), incident_dir), runtime
        if selected_type == "claude":
            agent = ClaudeAgent(
                api_key=kwargs.get("api_key"),
                model=runtime["model"],
                incident_dir=str(incident_dir) if incident_dir else None,
            )
            return agent, runtime
        raise ValueError(f"未知Agent类型: {agent_type}")
