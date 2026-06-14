"""基础数据结构定义"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class CausalNode:
    """因果链节点"""
    id: str
    event: str
    time: Optional[str] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class CausalEdge:
    """因果链边"""
    from_node: str
    to_node: str
    relationship: str
    confidence: float


@dataclass
class CausalChain:
    """因果链"""
    nodes: List[CausalNode]
    edges: List[CausalEdge]
    confidence: float
    is_complete: bool = False

    def check_completeness(self) -> bool:
        """判断因果链是否完整

        规则：
        - 至少3个节点
        - 最后一个节点是故障现象
        - 所有edges置信度 >= 0.5
        """
        if len(self.nodes) < 3:
            return False

        last_node = self.nodes[-1]
        if not any(k in last_node.event.lower()
                   for k in ["失败", "故障", "超时", "错误", "failure", "error"]):
            return False

        if any(e.confidence < 0.5 for e in self.edges):
            return False

        self.is_complete = True
        return True


@dataclass
class HypothesisVersion:
    """假设版本（演化历史）"""
    round: int
    hypothesis_text: str
    status: str
    reasoning: str
    evidence_considered: List[str]


@dataclass
class ReasoningEntry:
    """推理思考记录"""
    round: int
    timestamp: str
    thought: str
    action: Optional[str] = None
    result: Optional[str] = None
