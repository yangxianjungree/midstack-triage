"""Phase 4 reasoning package."""

from .multitrack import (
    AgentFactory,
    CausalChain,
    CausalEdge,
    CausalNode,
    ClaudeAgent,
    HypothesisTrack,
    HypothesisVersion,
    L1TemplateMapper,
    LeadOrchestrator,
    MockAgent,
    ReasoningAgent,
    ReasoningBoard,
    ReasoningEntry,
)
from .reasoning import run_phase4_analysis

__all__ = [
    "AgentFactory",
    "CausalChain",
    "CausalEdge",
    "CausalNode",
    "ClaudeAgent",
    "HypothesisTrack",
    "HypothesisVersion",
    "L1TemplateMapper",
    "LeadOrchestrator",
    "MockAgent",
    "ReasoningAgent",
    "ReasoningBoard",
    "ReasoningEntry",
    "run_phase4_analysis",
]
