"""LeadOrchestrator - 多轨推理协调器"""

from typing import List, Dict, Optional
from pathlib import Path
import time

from .reasoning_board import ReasoningBoard
from .hypothesis_track import HypothesisTrack
from .agent_interface import ReasoningAgent, AgentFactory


class LeadOrchestrator:
    """协调多条假设轨的并行推理"""

    def __init__(
        self,
        incident_dir: Path,
        initial_hypotheses: List[str],
        agent_type: str = "mock",
        agent_kwargs: Optional[Dict] = None
    ):
        self.incident_dir = Path(incident_dir)
        self.board = ReasoningBoard(incident_dir)

        self.tracks: Dict[str, HypothesisTrack] = {}
        self.current_round = 0
        self.max_rounds = 10

        agent_kwargs = agent_kwargs or {}

        for i, hyp_text in enumerate(initial_hypotheses, 1):
            hyp_id = f"h{i}"
            track_id = f"track_{hyp_id}"
            agent = AgentFactory.create(agent_type, **agent_kwargs)
            self.tracks[track_id] = HypothesisTrack(
                track_id=track_id,
                hypothesis_id=hyp_id,
                initial_hypothesis=hyp_text,
                board=self.board,
                agent=agent,
                incident_dir=self.incident_dir
            )

    def run(self) -> Dict:
        """运行多轮推理循环"""
        while self.current_round < self.max_rounds:
            self.current_round += 1

            active_tracks = [t for t in self.tracks.values() if t.is_active]
            if not active_tracks:
                self.board.end_round(
                    self.current_round - 1,
                    "所有轨已终止"
                )
                break

            self.board.start_round(
                self.current_round,
                [t.track_id for t in active_tracks]
            )

            # Phase R1: 并行推理
            self._run_phase_r1(active_tracks)

            # Phase V: 执行验证
            validation_results = self._run_phase_v()

            # Phase R2: 更新状态
            self._run_phase_r2(active_tracks)

            self.board.end_round(self.current_round)

            if self._check_termination():
                break

        return self._generate_final_report()

    def _run_phase_r1(self, tracks: List[HypothesisTrack]) -> None:
        """Phase R1: 各轨并行推理"""
        for track in tracks:
            track.run_phase_r1(self.current_round)

    def _run_phase_v(self) -> List[Dict]:
        """Phase V: 执行验证队列"""
        pending = self.board.get_pending_validations()
        results = []

        for val_req in pending:
            result = self._execute_validation(val_req)
            results.append(result)

        return results

    def _execute_validation(self, val_req: Dict) -> Dict:
        """执行单个验证动作（mock实现）"""
        action = val_req["action"]
        val_id = val_req["id"]

        # TODO: 调用真实验证Agent
        result_id = f"E_{val_id}"
        mock_result = {
            "action": action,
            "result": f"Mock result for {action}",
            "evidence_type": "observation",
            "raw_data": {}
        }

        self.board.add_validation_result(
            result_id=result_id,
            action=action,
            result=mock_result["result"],
            evidence_type=mock_result["evidence_type"],
            raw_data=mock_result["raw_data"],
            shared_to=val_req["requested_by"]
        )

        self.board.mark_validation_completed(val_id, result_id)

        return mock_result

    def _run_phase_r2(self, tracks: List[HypothesisTrack]) -> None:
        """Phase R2: 各轨更新状态"""
        for track in tracks:
            track.run_phase_r2(self.current_round)

    def _check_termination(self) -> bool:
        """检查是否应终止循环"""
        active_count = sum(1 for t in self.tracks.values() if t.is_active)

        if active_count == 0:
            return True

        # 至少1个轨得到高置信度结论
        for track in self.tracks.values():
            status = self.board.get_hypothesis_status(track.hypothesis_id)
            if status and status.get("confidence", 0) >= 0.8:
                if status["status"] in ["supported", "refuted"]:
                    return True

        return False

    def _generate_final_report(self) -> Dict:
        """生成最终报告"""
        return {
            "incident_id": self.board._data["incident_id"],
            "total_rounds": self.current_round,
            "hypotheses": [
                {
                    "id": track.hypothesis_id,
                    "final_text": track.get_current_hypothesis(),
                    "status": self.board.get_hypothesis_status(track.hypothesis_id),
                    "private_context": track.get_private_context()
                }
                for track in self.tracks.values()
            ],
            "all_findings": self.board.get_all_findings(),
            "cross_refutations": self.board._data["cross_refutations"]
        }
