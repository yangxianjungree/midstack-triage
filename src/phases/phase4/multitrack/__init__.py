"""Phase 4 多轨推理引擎

用于自动化故障根因分析的多假设并行推理系统
"""

from .data_structures import (
    CausalNode,
    CausalEdge,
    CausalChain,
    HypothesisVersion,
    ReasoningEntry,
)
from .reasoning_board import ReasoningBoard
from .hypothesis_track import HypothesisTrack
from .lead_orchestrator import LeadOrchestrator
from .l1_mapper import L1TemplateMapper
from .agents import AgentFactory, ClaudeAgent, MockAgent, ReasoningAgent

__version__ = "0.1.0"

__all__ = [
    "CausalNode",
    "CausalEdge",
    "CausalChain",
    "HypothesisVersion",
    "ReasoningEntry",
    "ReasoningBoard",
    "HypothesisTrack",
    "LeadOrchestrator",
    "L1TemplateMapper",
    "ReasoningAgent",
    "MockAgent",
    "ClaudeAgent",
    "AgentFactory",
]
