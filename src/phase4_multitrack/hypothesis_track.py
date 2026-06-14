"""HypothesisTrack - 单条假设推理轨"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from pathlib import Path

from .data_structures import (
    HypothesisVersion,
    ReasoningEntry,
    CausalChain,
    CausalNode,
    CausalEdge
)
from .reasoning_board import ReasoningBoard
from .agent_interface import ReasoningAgent, MockAgent


class HypothesisTrack:
    """单条假设推理轨（隔离上下文）"""

    def __init__(
        self,
        track_id: str,
        hypothesis_id: str,
        initial_hypothesis: str,
        board: ReasoningBoard,
        agent: Optional[ReasoningAgent] = None,
        incident_dir: Optional[Path] = None
    ):
        self.track_id = track_id
        self.hypothesis_id = hypothesis_id
        self.board = board
        self.incident_dir = incident_dir

        # 如果没提供agent，创建默认MockAgent
        if agent is None:
            agent = MockAgent()
        # 如果agent是ClaudeAgent，设置incident_dir
        elif hasattr(agent, 'incident_dir') and incident_dir:
            agent.incident_dir = str(incident_dir)

        self.agent = agent

        # 隔离上下文
        self.hypothesis_evolution: List[HypothesisVersion] = []
        self.reasoning_log: List[ReasoningEntry] = []
        self.causal_chain: Optional[CausalChain] = None
        self.current_round = 0
        self.is_active = True

        # 初始假设
        self._add_hypothesis_version(
            round_num=0,
            text=initial_hypothesis,
            status="pending",
            reasoning="初始假设",
            evidence=[]
        )

    # ==================== 三相位推理主流程 ====================

    def run_phase_r1(self, round_num: int) -> None:
        """Phase R1: 基于已有证据推理，请求验证（不写status）"""
        self.current_round = round_num

        if not self.is_active:
            return

        # 读取共享层（不含当轮新验证）
        observations = self._observe(include_current_round_validations=False)

        # 推理（调用Agent）
        reasoning_result = self._reason(observations)

        # 写入发现 + 请求验证（不写status）
        self._take_actions_phase_r1(reasoning_result)

        # 暂存结果，待R2使用
        self._pending_reasoning_result = reasoning_result

    def run_phase_r2(self, round_num: int) -> None:
        """Phase R2: 读取当轮验证结果，更新假设状态"""
        if not self.is_active:
            return

        # 读取当轮新验证结果
        new_validations = self._get_current_round_validation_results()

        if not new_validations:
            self._update_hypothesis_status(self._pending_reasoning_result)
            return

        # 处理新验证结果
        for val_result in new_validations:
            self._process_validation_result(val_result)

        # R2状态推导：验证结果优先于R1结果
        final_status, final_confidence = self._derive_final_status_in_r2(
            self._pending_reasoning_result,
            new_validations
        )

        # 更新R1结果
        self._pending_reasoning_result["hypothesis_status"] = final_status
        self._pending_reasoning_result["confidence"] = final_confidence

        # 更新到共享层
        self._update_hypothesis_status(self._pending_reasoning_result)

    def _derive_final_status_in_r2(
        self,
        r1_result: Dict,
        validation_results: List[Dict]
    ) -> Tuple[str, float]:
        """R2阶段根据验证结果推导最终状态

        优先级：验证 refutation/support > R1结果
        """
        has_refutation = any(
            v.get("evidence_type") == "refutation" for v in validation_results
        )
        has_support = any(
            v.get("evidence_type") == "support" for v in validation_results
        )

        if has_refutation:
            return ("refuted", 0.9)

        if has_support:
            r1_status = r1_result.get("hypothesis_status", "pending")
            r1_confidence = r1_result.get("confidence", 0.5)

            if r1_status == "supported":
                return (r1_status, min(r1_confidence + 0.1, 1.0))
            else:
                return ("supported", max(r1_confidence, 0.7))

        # 无关键验证结果，保持R1
        return (
            r1_result.get("hypothesis_status", "pending"),
            r1_result.get("confidence", 0.5)
        )

    # ==================== 观察与推理 ====================

    def _observe(self, include_current_round_validations: bool = True) -> Dict:
        """读取共享层（防止同轮污染）"""
        max_round = (
            self.current_round - 1
            if not include_current_round_validations
            else self.current_round
        )

        return {
            "base_evidence": {},  # TODO: 从board读取
            "hypothesis_status": self.board.get_all_hypothesis_status(),
            "recent_findings": self.board.get_findings_up_to_round(max_round),
            "my_validations": self._get_my_validation_results(
                include_current_round_validations
            ),
            "refutations_against_me": self.board.get_refutations_for_hypothesis(
                self.hypothesis_id
            )
        }

    def _reason(self, observations: Dict) -> Dict:
        """推理：调用Agent"""
        return self.agent.reason(observations)

    def _get_my_validation_results(
        self, include_current_round: bool = True
    ) -> List[Dict]:
        """获取我请求的验证结果（使用封装方法）"""
        return self.board.get_completed_validations_for_track(
            track_id=self.track_id,
            up_to_round=self.current_round,
            include_current_round=include_current_round
        )

    def _get_current_round_validation_results(self) -> List[Dict]:
        """获取当轮新完成的验证结果（Phase R2用）"""
        return self.board.get_completed_validations_for_track(
            track_id=self.track_id,
            up_to_round=self.current_round,
            include_current_round=True,
            current_round_only=True
        )

    # ==================== 行动与状态更新 ====================

    def _take_actions_phase_r1(self, reasoning_result: Dict) -> None:
        """Phase R1: 写入发现 + 请求验证"""
        # 请求验证
        for action in reasoning_result.get("validation_actions", []):
            self.board.request_validation(
                action=action["action"],
                track_id=self.track_id,
                round_num=self.current_round
            )

        # 写入发现
        for finding in reasoning_result.get("findings", []):
            gap_detail = finding.get("gap_detail")

            # 确保gap_detail包含criticality
            if gap_detail and "criticality" not in gap_detail:
                gap_detail["criticality"] = "medium"

            self.board.add_finding(
                track_id=self.track_id,
                round_num=self.current_round,
                finding_type=finding["type"],
                content=finding["content"],
                evidence=finding["evidence"],
                affects=finding["affects"],
                gap_detail=gap_detail
            )

        # 写入跨轨反证
        for refutation in reasoning_result.get("cross_refutations", []):
            self.board.add_cross_refutation(
                from_track=self.track_id,
                to_hypothesis=refutation["to_hypothesis"],
                from_finding="",
                reason=refutation["reason"],
                confidence=refutation["confidence"]
            )

        # 更新因果链
        if reasoning_result.get("causal_chain_update"):
            self.causal_chain = reasoning_result["causal_chain_update"]

    def _process_validation_result(self, val_result: Dict) -> None:
        """处理单个验证结果，生成finding"""
        evidence_type = val_result.get("evidence_type", "observation")

        if evidence_type == "refutation":
            impact = "refute"
        elif evidence_type == "support":
            impact = "support"
        else:
            impact = "observation"

        # 确保evidence_id存在
        evidence_id = val_result.get("evidence_id")
        if not evidence_id:
            evidence_id = self.board.find_validation_result_id_by_action(
                val_result.get("action")
            )

        self.board.add_finding(
            track_id=self.track_id,
            round_num=self.current_round,
            finding_type=evidence_type,
            content=val_result["result"],
            evidence=[evidence_id] if evidence_id else [],
            affects=[{
                "hypothesis": self.hypothesis_id,
                "impact": impact,
                "confidence": 0.8
            }]
        )

    def _update_hypothesis_status(self, reasoning_result: Dict) -> None:
        """更新假设状态到共享层"""
        status = reasoning_result.get("hypothesis_status", "pending")
        confidence = reasoning_result.get("confidence", 0.0)

        self.board.update_hypothesis_status(
            hypothesis_id=self.hypothesis_id,
            status=status,
            confidence=confidence,
            round_num=self.current_round,
            track_id=self.track_id
        )

        # 更新隔离上下文
        self._add_hypothesis_version(
            round_num=self.current_round,
            text=reasoning_result.get(
                "hypothesis_text", self.get_current_hypothesis()
            ),
            status=status,
            reasoning=reasoning_result.get("reasoning", ""),
            evidence=reasoning_result.get("evidence_considered", [])
        )

        # 判断是否继续
        self.is_active = self._should_track_continue(status)

    # ==================== 停止条件判断 ====================

    def _should_track_continue(self, status: str) -> bool:
        """判断轨是否应继续下一轮"""
        if status == "refuted":
            return False

        if status == "supported":
            chain_complete = False
            if self.causal_chain:
                chain_complete = self.causal_chain.check_completeness()

            has_critical_gap = self._has_critical_gap()

            if chain_complete and not has_critical_gap:
                return False

            return True

        # insufficient + 不可解决gap + 无pending验证 → 停止
        if status == "insufficient":
            critical_gaps = self.board.get_critical_gaps_for_track(self.track_id)
            unresolvable = [g for g in critical_gaps if not g.get("can_resolve", True)]
            pending_vals = self.board.get_pending_validations()

            if unresolvable and not any(
                self.track_id in v.get("requested_by", []) for v in pending_vals
            ):
                return False

        return True

    def _has_critical_gap(self) -> bool:
        """检查是否存在关键证据缺口"""
        recent_findings = self.board.get_findings_up_to_round(self.current_round)
        for f in recent_findings:
            if (f.get("track") == self.track_id
                    and f.get("type") == "gap"
                    and f.get("gap_detail", {}).get("criticality") == "high"):
                return True

        critical_gaps = self.board.get_critical_gaps_for_track(self.track_id)
        return len(critical_gaps) > 0

    # ==================== 隔离上下文管理 ====================

    def _add_hypothesis_version(
        self,
        round_num: int,
        text: str,
        status: str,
        reasoning: str,
        evidence: List[str]
    ) -> None:
        """添加假设版本到演化历史"""
        self.hypothesis_evolution.append(HypothesisVersion(
            round=round_num,
            hypothesis_text=text,
            status=status,
            reasoning=reasoning,
            evidence_considered=evidence
        ))

    def get_current_hypothesis(self) -> str:
        """获取当前假设文本"""
        return (
            self.hypothesis_evolution[-1].hypothesis_text
            if self.hypothesis_evolution else ""
        )

    def get_private_context(self) -> Dict:
        """导出隔离上下文（供Lead合并使用）"""
        return {
            "track_id": self.track_id,
            "hypothesis_id": self.hypothesis_id,
            "hypothesis_evolution": [
                {
                    "round": v.round,
                    "text": v.hypothesis_text,
                    "status": v.status,
                    "reasoning": v.reasoning,
                    "evidence": v.evidence_considered
                }
                for v in self.hypothesis_evolution
            ],
            "reasoning_log": [
                {
                    "round": e.round,
                    "timestamp": e.timestamp,
                    "thought": e.thought,
                    "action": e.action,
                    "result": e.result
                }
                for e in self.reasoning_log
            ],
            "causal_chain": self._serialize_causal_chain(),
            "is_active": self.is_active
        }

    def _serialize_causal_chain(self) -> Optional[Dict]:
        """序列化因果链"""
        if not self.causal_chain:
            return None
        return {
            "nodes": [
                {
                    "id": n.id,
                    "event": n.event,
                    "time": n.time,
                    "evidence": n.evidence
                }
                for n in self.causal_chain.nodes
            ],
            "edges": [
                {
                    "from": e.from_node,
                    "to": e.to_node,
                    "relationship": e.relationship,
                    "confidence": e.confidence
                }
                for e in self.causal_chain.edges
            ],
            "confidence": self.causal_chain.confidence
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
