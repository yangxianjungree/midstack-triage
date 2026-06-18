"""ReasoningBoard - 共享推理黑板"""

from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from shared.io import load_yaml_object, write_yaml_object


class ReasoningBoard:
    """共享推理黑板，所有轨通过它读写共享数据"""

    def __init__(self, incident_dir: Path):
        self.incident_dir = Path(incident_dir)
        self.board_path = self.incident_dir / "reasoning-board.yaml"
        self._lock = Lock()
        self._data: Dict[str, Any] = {}

        if self.board_path.exists():
            self._load()
        else:
            self._initialize()

    def _initialize(self) -> None:
        """初始化空黑板"""
        self._data = {
            "version": "1.0",
            "created_at": self._now(),
            "incident_id": self.incident_dir.name,
            "base_evidence": {},
            "hypothesis_status": {},
            "validation_queue": [],
            "executed_validations": {},
            "findings": [],
            "cross_refutations": [],
            "evidence_gaps": [],
            "rounds": []
        }
        self._save()

    def _load(self) -> None:
        """从文件加载"""
        self._data = load_yaml_object(self.board_path)

    def _save(self) -> None:
        """保存到文件（线程安全）"""
        write_yaml_object(self.board_path, self._data, allow_unicode=True)

    def _now(self) -> str:
        """当前时间戳"""
        return datetime.now(timezone.utc).isoformat()

    # ==================== 假设状态 ====================

    def update_hypothesis_status(
        self,
        hypothesis_id: str,
        status: str,
        confidence: float,
        round_num: int,
        track_id: str
    ) -> None:
        """更新假设状态"""
        with self._lock:
            self._data["hypothesis_status"][hypothesis_id] = {
                "status": status,
                "confidence": confidence,
                "last_updated_round": round_num,
                "last_updated_by": track_id
            }
            self._save()

    def get_hypothesis_status(self, hypothesis_id: str) -> Optional[Dict]:
        """读取假设状态"""
        return self._data["hypothesis_status"].get(hypothesis_id)

    def get_all_hypothesis_status(self) -> Dict[str, Dict]:
        """获取所有假设状态"""
        return self._data["hypothesis_status"].copy()

    def get_incident_id(self) -> str:
        """获取incident ID"""
        return str(self._data.get("incident_id") or "")

    # ==================== 验证队列 ====================

    def request_validation(
        self,
        action: str,
        track_id: str,
        round_num: int
    ) -> str:
        """请求验证动作，返回validation_id"""
        with self._lock:
            # 检查是否已有相同请求
            for v in self._data["validation_queue"]:
                if v["action"] == action and v["status"] in ["pending", "executing"]:
                    if track_id not in v["requested_by"]:
                        v["requested_by"].append(track_id)
                        self._save()
                    return v["id"]

            # 创建新请求
            val_id = f"val_{len(self._data['validation_queue']) + 1:03d}"
            self._data["validation_queue"].append({
                "id": val_id,
                "action": action,
                "requested_by": [track_id],
                "requested_at_round": round_num,
                "status": "pending",
                "result_id": None,
                "completed_at": None
            })
            self._save()
            return val_id

    def mark_validation_completed(self, val_id: str, result_id: str) -> None:
        """标记验证完成"""
        with self._lock:
            for v in self._data["validation_queue"]:
                if v["id"] == val_id:
                    v["status"] = "completed"
                    v["result_id"] = result_id
                    v["completed_at"] = self._now()
                    break
            self._save()

    def add_validation_result(
        self,
        result_id: str,
        action: str,
        result: str,
        evidence_type: str,
        raw_data: Dict,
        shared_to: List[str]
    ) -> None:
        """添加验证结果"""
        with self._lock:
            self._data["executed_validations"][result_id] = {
                "evidence_id": result_id,
                "action": action,
                "result": result,
                "evidence_type": evidence_type,
                "raw_data": raw_data,
                "shared_to": shared_to,
                "executed_at": self._now()
            }
            self._save()

    def get_validation_result_data(self, result_id: str) -> Optional[Dict]:
        """读取验证结果"""
        return self._data["executed_validations"].get(result_id)

    # ==================== 发现 ====================

    def add_finding(
        self,
        track_id: str,
        round_num: int,
        finding_type: str,
        content: str,
        evidence: List[str],
        affects: List[Dict],
        gap_detail: Optional[Dict] = None
    ) -> str:
        """添加发现，返回finding_id"""
        with self._lock:
            finding_id = f"F{len(self._data['findings']) + 1:03d}"
            self._data["findings"].append({
                "id": finding_id,
                "track": track_id,
                "round": round_num,
                "type": finding_type,
                "content": content,
                "evidence": evidence,
                "affects": affects,
                "gap_detail": gap_detail,
                "created_at": self._now()
            })
            self._save()
            return finding_id

    def get_all_findings(self) -> List[Dict]:
        """获取所有发现"""
        return self._data["findings"].copy()

    def get_findings_up_to_round(self, round_num: int) -> List[Dict]:
        """获取截至某轮的所有发现"""
        return [f for f in self._data["findings"] if f["round"] <= round_num]

    def get_findings_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取某假设相关的所有findings"""
        return [
            f for f in self._data["findings"]
            if any(a["hypothesis"] == hypothesis_id for a in f.get("affects", []))
        ]

    # ==================== 跨轨反证 ====================

    def add_cross_refutation(
        self,
        from_track: str,
        to_hypothesis: str,
        from_finding: str,
        reason: str,
        confidence: str
    ) -> str:
        """添加跨轨反证"""
        with self._lock:
            cr_id = f"CR{len(self._data['cross_refutations']) + 1:03d}"
            self._data["cross_refutations"].append({
                "id": cr_id,
                "from_track": from_track,
                "to_hypothesis": to_hypothesis,
                "from_finding": from_finding,
                "reason": reason,
                "confidence": confidence,
                "created_at": self._now()
            })
            self._save()
            return cr_id

    def get_refutations_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取针对某假设的所有反证"""
        return [
            cr for cr in self._data["cross_refutations"]
            if cr["to_hypothesis"] == hypothesis_id
        ]

    # ==================== 轮次管理 ====================

    def start_round(self, round_num: int, tracks_active: List[str]) -> None:
        """开始新一轮"""
        with self._lock:
            self._data["rounds"].append({
                "round": round_num,
                "started_at": self._now(),
                "completed_at": None,
                "tracks_active": tracks_active,
                "validations_executed": [],
                "findings_added": []
            })
            self._save()

    def end_round(self, round_num: int, termination_reason: Optional[str] = None) -> None:
        """结束当前轮"""
        with self._lock:
            for r in self._data["rounds"]:
                if r["round"] == round_num:
                    r["completed_at"] = self._now()
                    if termination_reason:
                        r["termination_reason"] = termination_reason
                    break
            self._save()

    # ==================== 封装方法（避免_data直接访问）====================

    def get_pending_validations(self) -> List[Dict]:
        """获取待执行的验证"""
        return [
            v for v in self._data["validation_queue"]
            if v["status"] == "pending"
        ]

    def get_validation_queue(self) -> List[Dict]:
        """获取验证队列快照"""
        return self._data["validation_queue"].copy()

    def get_executed_validations(self) -> Dict[str, Dict]:
        """获取已执行验证快照"""
        return self._data["executed_validations"].copy()

    def get_cross_refutations(self) -> List[Dict]:
        """获取跨轨反证快照"""
        return self._data["cross_refutations"].copy()

    def get_critical_gaps_for_track(self, track_id: str) -> List[Dict]:
        """获取某轨的关键证据缺口"""
        return [
            gap for gap in self._data.get("evidence_gaps", [])
            if track_id in gap.get("requested_by", [])
            and gap.get("criticality") == "high"
        ]

    def get_completed_validations_for_track(
        self,
        track_id: str,
        up_to_round: int,
        include_current_round: bool = True,
        current_round_only: bool = False
    ) -> List[Dict]:
        """获取某轨的已完成验证结果"""
        results = []
        for v in self._data["validation_queue"]:
            if track_id not in v.get("requested_by", []):
                continue
            if v["status"] != "completed":
                continue

            req_round = v.get("requested_at_round", 0)

            if current_round_only:
                if req_round != up_to_round:
                    continue
            else:
                if not include_current_round and req_round >= up_to_round:
                    continue
                if req_round > up_to_round:
                    continue

            result_data = self.get_validation_result_data(v.get("result_id"))
            if result_data:
                results.append(result_data)

        return results

    def find_validation_result_id_by_action(self, action: str) -> Optional[str]:
        """根据action查找验证结果ID"""
        for key, val in self._data["executed_validations"].items():
            if val.get("action") == action:
                return key
        return None
