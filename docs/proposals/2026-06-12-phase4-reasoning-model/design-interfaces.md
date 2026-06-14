---
status: design
last_updated: 2026-06-13
purpose: 定义共享层、隔离层、轨、Lead的Python类接口
---

# Python 接口设计

## 1. 共享层：ReasoningBoard 类

**职责**：管理 reasoning-board.yaml 的读写，提供线程安全的追加接口

```python
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from threading import Lock
import yaml

class ReasoningBoard:
    """共享推理黑板，所有轨通过它读写共享数据"""
    
    def __init__(self, incident_dir: Path):
        self.incident_dir = incident_dir
        self.board_path = incident_dir / "reasoning-board.yaml"
        self._lock = Lock()  # 并发写保护
        self._data: Dict[str, Any] = {}
        
        if self.board_path.exists():
            self._load()
        else:
            self._initialize()
    
    # ==================== 初始化 ====================
    
    def _initialize(self):
        """初始化空黑板"""
        self._data = {
            "version": "1.0",
            "created_at": self._now(),
            "incident_id": self.incident_dir.name,
            "base_evidence": self._load_base_evidence(),
            "hypothesis_status": {},
            "validation_queue": [],
            "executed_validations": {},
            "findings": [],
            "cross_refutations": [],
            "evidence_gaps": [],
            "rounds": []
        }
        self._save()
    
    def _load_base_evidence(self) -> Dict:
        """装载第3段证据包"""
        return {
            "structured_record_path": "./structured_record.yaml",
            "signal_bundle_path": "./signal_bundle.yaml",
            "collection_report_path": "./collection_report.yaml",
            "timeline": self._load_timeline(),
            "historical_cases": []  # 第一版为空
        }
    
    def _load_timeline(self) -> List[Dict]:
        """从第3段产物提取时间线"""
        # TODO: 实现从 signal_bundle 提取
        return []
    
    # ==================== 假设状态 ====================
    
    def get_hypothesis_status(self, hypothesis_id: str) -> Optional[Dict]:
        """读取假设状态"""
        return self._data["hypothesis_status"].get(hypothesis_id)
    
    def update_hypothesis_status(
        self,
        hypothesis_id: str,
        status: str,
        confidence: float,
        round_num: int,
        track_id: str
    ):
        """更新假设状态（线程安全）"""
        with self._lock:
            self._data["hypothesis_status"][hypothesis_id] = {
                "status": status,
                "confidence": confidence,
                "last_updated_round": round_num,
                "last_updated_by": track_id
            }
            self._save()
    
    def get_all_hypothesis_status(self) -> Dict[str, Dict]:
        """获取所有假设状态"""
        return self._data["hypothesis_status"].copy()
    
    # ==================== 验证队列 ====================
    
    def request_validation(
        self,
        action: str,
        track_id: str,
        round_num: int
    ) -> str:
        """请求验证动作，返回 validation_id"""
        with self._lock:
            # 检查是否已有相同请求
            existing = self._find_validation_by_action(action)
            if existing:
                # 追加请求者
                if track_id not in existing["requested_by"]:
                    existing["requested_by"].append(track_id)
                    self._save()
                return existing["id"]
            
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
    
    def _find_validation_by_action(self, action: str) -> Optional[Dict]:
        """查找已有验证请求"""
        for v in self._data["validation_queue"]:
            if v["action"] == action and v["status"] in ["pending", "executing"]:
                return v
        return None
    
    def mark_validation_completed(
        self,
        val_id: str,
        result_id: str
    ):
        """标记验证完成"""
        with self._lock:
            for v in self._data["validation_queue"]:
                if v["id"] == val_id:
                    v["status"] = "completed"
                    v["result_id"] = result_id
                    v["completed_at"] = self._now()
                    break
            self._save()
    
    def get_validation_result(self, val_id: str) -> Optional[str]:
        """获取验证结果ID"""
        for v in self._data["validation_queue"]:
            if v["id"] == val_id:
                return v.get("result_id")
        return None
    
    # ==================== 已执行验证 ====================
    
    def add_validation_result(
        self,
        result_id: str,
        action: str,
        result: str,
        evidence_type: str,
        raw_data: Dict,
        shared_to: List[str]
    ):
        """添加验证结果（修复阻塞点5：补充 evidence_id）"""
        with self._lock:
            self._data["executed_validations"][result_id] = {
                "evidence_id": result_id,  # 修复阻塞点5：显式写入
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
        """添加发现，返回 finding_id"""
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
    
    def get_findings_by_round(self, round_num: int) -> List[Dict]:
        """获取某轮的所有发现"""
        return [f for f in self._data["findings"] if f["round"] == round_num]
    
    def get_findings_up_to_round(self, round_num: int) -> List[Dict]:
        """获取截至某轮的所有发现（修复阻塞点3）"""
        return [f for f in self._data["findings"] if f["round"] <= round_num]
    
    def get_all_findings(self) -> List[Dict]:
        """获取所有发现"""
        return self._data["findings"].copy()
    
    def get_base_evidence(self) -> Dict:
        """获取基础证据（修复封装）"""
        return self._data["base_evidence"]
    
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
    
    # ==================== 新增封装方法（修复接口泄漏）====================
    
    def get_findings_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取某假设相关的所有findings"""
        return [
            f for f in self._data["findings"]
            if any(a["hypothesis"] == hypothesis_id for a in f.get("affects", []))
        ]
    
    def get_validations_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取某假设请求的验证动作"""
        track_id = f"track_{hypothesis_id}"
        return [
            v for v in self._data["validation_queue"]
            if track_id in v.get("requested_by", [])
        ]
    
    def get_evidence_gaps_for_hypothesis(self, hypothesis_id: str) -> List[str]:
        """获取某假设的证据缺口"""
        track_id = f"track_{hypothesis_id}"
        gaps = []
        for f in self._data["findings"]:
            if f.get("track") == track_id and f.get("type") == "gap":
                gaps.append(f.get("gap_detail", {}).get("missing", f["content"]))
        return gaps
    
    def get_all_evidence_gaps(self) -> List[Dict]:
        """获取所有证据缺口"""
        return self._data.get("evidence_gaps", []).copy()
    
    def get_pending_validations(self) -> List[Dict]:
        """获取待执行的验证（封装_data访问）"""
        return [
            v for v in self._data["validation_queue"]
            if v["status"] == "pending"
        ]
    
    def find_validation_result_id_by_action(self, action: str) -> Optional[str]:
        """根据action查找验证结果ID（封装_data访问）"""
        for key, val in self._data["executed_validations"].items():
            if val.get("action") == action:
                return key
        return None
    
    def get_critical_gaps_for_track(self, track_id: str) -> List[Dict]:
        """获取某轨的关键证据缺口（封装_data访问）"""
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
        """获取某轨的已完成验证结果（封装_data访问）
        
        Args:
            track_id: 轨ID
            up_to_round: 截至哪一轮
            include_current_round: 是否包含当前轮（R1=False, R2=True）
            current_round_only: 仅返回当前轮（用于R2获取新验证）
        """
        results = []
        for v in self._data["validation_queue"]:
            if track_id not in v.get("requested_by", []):
                continue
            if v["status"] != "completed":
                continue
            
            req_round = v.get("requested_at_round", 0)
            
            # 仅当前轮
            if current_round_only:
                if req_round != up_to_round:
                    continue
            else:
                # 截至某轮
                if not include_current_round and req_round >= up_to_round:
                    continue
                if req_round > up_to_round:
                    continue
            
            result_data = self.get_validation_result_data(v.get("result_id"))
            if result_data:
                results.append(result_data)
        
        return results
    
    # ==================== 证据缺口 ====================
    
    def add_evidence_gap(
        self,
        gap: str,
        track_id: str,
        status: str,
        reason: str,
        can_resolve: bool,
        alternative: Optional[str] = None
    ):
        """添加证据缺口"""
        with self._lock:
            # 检查是否已存在
            existing = next((g for g in self._data["evidence_gaps"] if g["gap"] == gap), None)
            if existing:
                if track_id not in existing["requested_by"]:
                    existing["requested_by"].append(track_id)
                    self._save()
                return
            
            self._data["evidence_gaps"].append({
                "gap": gap,
                "requested_by": [track_id],
                "status": status,
                "reason": reason,
                "can_resolve": can_resolve,
                "alternative": alternative,
                "created_at": self._now()
            })
            self._save()
    
    def has_evidence_gap(self, gap: str) -> bool:
        """检查某缺口是否已标记"""
        return any(g["gap"] == gap for g in self._data["evidence_gaps"])
    
    # ==================== 轮次管理 ====================
    
    def start_round(
        self,
        round_num: int,
        tracks_active: List[str]
    ):
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
    
    def end_round(
        self,
        round_num: int,
        termination_reason: Optional[str] = None
    ):
        """结束当前轮"""
        with self._lock:
            for r in self._data["rounds"]:
                if r["round"] == round_num:
                    r["completed_at"] = self._now()
                    if termination_reason:
                        r["termination_reason"] = termination_reason
                    break
            self._save()
    
    # ==================== 工具方法 ====================
    
    def _load(self):
        """从文件加载"""
        with open(self.board_path) as f:
            self._data = yaml.safe_load(f)
    
    def _save(self):
        """保存到文件"""
        with open(self.board_path, 'w') as f:
            yaml.dump(self._data, f, allow_unicode=True, sort_keys=False)
    
    def _now(self) -> str:
        """当前时间戳"""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
```

---

## 2. 假设轨：HypothesisTrack 类

**职责**：单条假设的独立推理轨，维护隔离上下文，通过黑板读写共享数据

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class HypothesisVersion:
    round: int
    hypothesis_text: str
    status: str
    reasoning: str
    evidence_considered: List[str]

@dataclass
class ReasoningEntry:
    round: int
    timestamp: str
    thought: str
    action: Optional[str] = None
    result: Optional[str] = None

@dataclass
class CausalChain:
    nodes: List['CausalNode']
    edges: List['CausalEdge']
    confidence: float
    is_complete: bool = False  # 修复阻塞点4：新增字段
    
    def check_completeness(self) -> bool:
        """判断因果链是否完整（修复阻塞点4）
        
        规则：
        - 至少3个节点
        - 最后一个节点是故障现象
        - 所有edges置信度 >= 0.5
        """
        if len(self.nodes) < 3:
            return False
        
        # 检查最后一个节点是否是故障现象
        last_node = self.nodes[-1]
        if not any(k in last_node.event.lower() 
                   for k in ["失败", "故障", "超时", "错误", "failure", "error"]):
            return False
        
        # 检查edges置信度
        if any(e.confidence < 0.5 for e in self.edges):
            return False
        
        self.is_complete = True
        return True

@dataclass
class CausalNode:
    id: str
    event: str
    time: Optional[str]
    evidence: List[str]

@dataclass
class CausalEdge:
    from_node: str
    to_node: str
    relationship: str
    confidence: float

class HypothesisTrack:
    """单条假设推理轨"""
    
    def __init__(
        self,
        track_id: str,
        hypothesis_id: str,
        initial_hypothesis: str,
        board: ReasoningBoard
    ):
        self.track_id = track_id
        self.hypothesis_id = hypothesis_id
        self.board = board
        
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
    
    # ==================== 推理主流程（三相位）====================
    
    def run_phase_r1(self, round_num: int):
        """Phase R1: 基于已有证据推理，请求验证"""
        self.current_round = round_num
        
        if not self.is_active:
            return  # 已结论，不再推理
        
        # Observation: 读取共享层（不含当轮新验证）
        observations = self._observe(include_current_round_validations=False)
        
        # Reasoning: 推理（调用Agent）
        reasoning_result = self._reason(observations)
        
        # Action: 写入发现（基于已有证据）+ 请求验证
        self._take_actions_phase_r1(reasoning_result)
        
        # 暂存结果，待 Phase R2 使用
        self._pending_reasoning_result = reasoning_result
    
    def run_phase_r2(self, round_num: int):
        """Phase R2: 读取当轮验证结果，更新假设状态"""
        if not self.is_active:
            return
        
        # 读取当轮新验证结果
        new_validations = self._get_current_round_validation_results()
        
        if not new_validations:
            # 无新验证结果，直接更新状态
            self._update_hypothesis_status(self._pending_reasoning_result)
            return
        
        # 基于新验证结果补充推理
        for val_result in new_validations:
            self._process_validation_result(val_result)
        
        # 修复P0-B：R2状态推导，验证结果优先于R1结果
        final_status, final_confidence = self._derive_final_status_in_r2(
            self._pending_reasoning_result,
            new_validations
        )
        
        # 更新假设状态
        self._pending_reasoning_result["hypothesis_status"] = final_status
        self._pending_reasoning_result["confidence"] = final_confidence
        self._update_hypothesis_status(self._pending_reasoning_result)
    
    def _derive_final_status_in_r2(
        self,
        r1_result: Dict,
        validation_results: List[Dict]
    ) -> Tuple[str, float]:
        """R2阶段根据验证结果推导最终状态（修复P0-B）
        
        优先级：验证 refutation/support > R1结果
        """
        has_refutation = any(v.get("evidence_type") == "refutation" for v in validation_results)
        has_support = any(v.get("evidence_type") == "support" for v in validation_results)
        
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
    
    def _observe(self, include_current_round_validations: bool = True) -> Dict:
        """读取共享层（修复阻塞点3：防止同轮污染）
        
        Args:
            include_current_round_validations: 
                False (R1): 只读上一轮完成的数据
                True (R2): 读包含当轮的数据
        """
        # 修复阻塞点3：R1 读 round-1，R2 读 round
        max_round = self.current_round - 1 if not include_current_round_validations else self.current_round
        
        return {
            "base_evidence": self.board.get_base_evidence(),
            "hypothesis_status": self.board.get_all_hypothesis_status(),
            "recent_findings": self.board.get_findings_up_to_round(max_round),  # 修复阻塞点3
            "my_validations": self._get_my_validation_results(
                include_current_round=include_current_round_validations
            ),
            "refutations_against_me": self.board.get_refutations_for_hypothesis(self.hypothesis_id)
        }
    
    def _get_my_validation_results(self, include_current_round: bool = True) -> List[Dict]:
        """获取我请求的验证结果（使用封装方法）"""
        return self.board.get_completed_validations_for_track(
            track_id=self.track_id,
            up_to_round=self.current_round,
            include_current_round=include_current_round
        )
    
    def _get_current_round_validation_results(self) -> List[Dict]:
        """获取当轮新完成的验证结果（Phase R2 用）"""
        return self.board.get_completed_validations_for_track(
            track_id=self.track_id,
            up_to_round=self.current_round,
            include_current_round=True,
            current_round_only=True
        )
    
    def _process_validation_result(self, val_result: Dict):
        """处理单个验证结果，生成 finding（修复阻塞点5）"""
        evidence_type = val_result.get("evidence_type", "observation")
        
        if evidence_type == "refutation":
            impact = "refute"
        elif evidence_type == "support":
            impact = "support"
        else:
            impact = "observation"
        
        # 修复阻塞点5：确保 evidence_id 存在
        evidence_id = val_result.get("evidence_id")
        if not evidence_id:
            # 兜底：从 board 封装方法获取
            evidence_id = self.board.find_validation_result_id_by_action(val_result.get("action"))
        
        self.board.add_finding(
            track_id=self.track_id,
            round_num=self.current_round,
            finding_type=evidence_type,
            content=val_result["result"],
            evidence=[evidence_id] if evidence_id else [],  # 确保有值
            affects=[{
                "hypothesis": self.hypothesis_id,
                "impact": impact,
                "confidence": 0.8
            }]
        )
    
    def _reason(self, observations: Dict) -> Dict:
        """推理：调用Agent（核心逻辑）"""
        # TODO(TD-XXX): 这里调用Agent API
        # 输入：observations + 当前假设 + 推理历史
        # 输出：新的假设判断、验证动作、发现、因果链
        
        # 第一版mock实现
        return {
            "hypothesis_status": "pending",
            "confidence": 0.5,
            "reasoning": "推理中...",
            "validation_actions": [],
            "findings": [],
            "causal_chain_update": None
        }
    
    def _take_actions_phase_r1(self, reasoning_result: Dict):
        """Phase R1: 基于已有证据采取动作"""
        # 请求验证
        for action in reasoning_result.get("validation_actions", []):
            self.board.request_validation(
                action=action["action"],
                track_id=self.track_id,
                round_num=self.current_round
            )
        
        # 写入发现（基于已有证据）
        for finding in reasoning_result.get("findings", []):
            gap_detail = finding.get("gap_detail")
            
            # 修复阻塞点4：确保 gap_detail 包含 criticality
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
        
        # 写入跨轨反证（修复 P1-7）
        for refutation in reasoning_result.get("cross_refutations", []):
            self.board.add_cross_refutation(
                from_track=self.track_id,
                to_hypothesis=refutation["to_hypothesis"],
                from_finding="",  # 可选：关联最新 finding
                reason=refutation["reason"],
                confidence=refutation["confidence"]
            )
        
        # 更新因果链
        if reasoning_result.get("causal_chain_update"):
            self.causal_chain = reasoning_result["causal_chain_update"]
    
    def _update_hypothesis_status(self, reasoning_result: Dict):
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
            text=reasoning_result.get("hypothesis_text", self.get_current_hypothesis()),
            status=status,
            reasoning=reasoning_result.get("reasoning", ""),
            evidence=reasoning_result.get("evidence_considered", [])
        )
        
        # 修复 P0-4: 判断是否继续
        self.is_active = self._should_track_continue(status)
    
    def _should_track_continue(self, status: str) -> bool:
        """判断轨是否应继续下一轮（修复阻塞点4）
        
        规则：
        - refuted → 停止
        - supported + 因果链完整 + 无critical_gap → 停止
        - supported + (因果链未完整 or 有gap) → 继续深入
        - insufficient + 不可解决的高critical_gap + 无pending验证 → 停止（修复P1-1）
        - insufficient/pending → 继续
        """
        if status == "refuted":
            return False
        
        if status == "supported":
            # 修复阻塞点4：调用 check_completeness()
            chain_complete = False
            if self.causal_chain:
                chain_complete = self.causal_chain.check_completeness()
            
            has_critical_gap = self._has_critical_gap()
            
            # 因果链完整 且 无关键缺口 → 停止
            if chain_complete and not has_critical_gap:
                return False
            
            # 否则继续深入（如 H3 案例：supported 但需找根因）
            return True
        
        # 修复P1-1：insufficient + 不可解决gap + 无pending验证 → 停止
        if status == "insufficient":
            critical_gaps = self.board.get_critical_gaps_for_track(self.track_id)
            unresolvable = [g for g in critical_gaps if not g.get("can_resolve", True)]
            pending_vals = self.board.get_pending_validations_for_track(self.track_id)
            
            if unresolvable and not pending_vals:
                return False
        
        # insufficient 或 pending → 继续
        return True
    
    def _has_critical_gap(self) -> bool:
        """检查是否存在关键证据缺口（修复阻塞点4）"""
        # 方法1：从最近的 findings 检查
        recent_findings = self.board.get_findings_up_to_round(self.current_round)
        for f in recent_findings:
            if (f.get("track") == self.track_id 
                and f.get("type") == "gap"
                and f.get("gap_detail", {}).get("criticality") == "high"):
                return True
        
        # 方法2：从 board.evidence_gaps 检查
        critical_gaps = self.board.get_critical_gaps_for_track(self.track_id)
        return len(critical_gaps) > 0
        
        return False
    
    # ==================== 隔离上下文管理 ====================
    
    def _add_hypothesis_version(
        self,
        round_num: int,
        text: str,
        status: str,
        reasoning: str,
        evidence: List[str]
    ):
        """添加假设版本到演化历史"""
        self.hypothesis_evolution.append(HypothesisVersion(
            round=round_num,
            hypothesis_text=text,
            status=status,
            reasoning=reasoning,
            evidence_considered=evidence
        ))
    
    def add_reasoning_entry(
        self,
        thought: str,
        action: Optional[str] = None,
        result: Optional[str] = None
    ):
        """添加推理思考记录"""
        self.reasoning_log.append(ReasoningEntry(
            round=self.current_round,
            timestamp=self._now(),
            thought=thought,
            action=action,
            result=result
        ))
    
    def get_current_hypothesis(self) -> str:
        """获取当前假设文本"""
        return self.hypothesis_evolution[-1].hypothesis_text if self.hypothesis_evolution else ""
    
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
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()
```

---

## 3. Lead Agent：LeadOrchestrator 类

**职责**：协调多轨、判断终止条件、合并结果

```python
class LeadOrchestrator:
    """Lead Agent，协调多轨推理"""
    
    def __init__(
        self,
        incident_dir: Path,
        max_rounds: int = 3,
        max_tracks: int = 5
    ):
        self.incident_dir = incident_dir
        self.max_rounds = max_rounds
        self.max_tracks = max_tracks
        
        self.board = ReasoningBoard(incident_dir)
        self.tracks: List[HypothesisTrack] = []
        self.current_round = 0
    
    # ==================== 初始化 ====================
    
    def initialize_tracks(self, initial_hypotheses: List[Dict]):
        """初始化假设轨"""
        # 动态选择假设轨
        selected = self._select_hypotheses(initial_hypotheses)
        
        for hyp in selected:
            track = HypothesisTrack(
                track_id=f"track_{hyp['id']}",
                hypothesis_id=hyp["id"],
                initial_hypothesis=hyp["description"],
                board=self.board
            )
            self.tracks.append(track)
            
            # 初始化假设状态到共享层
            self.board.update_hypothesis_status(
                hypothesis_id=hyp["id"],
                status="pending",
                confidence=hyp.get("initial_confidence", 0.5),
                round_num=0,
                track_id=track.track_id
            )
    
    def _select_hypotheses(self, hypotheses: List[Dict]) -> List[Dict]:
        """动态选择假设轨（TD-001）"""
        # 第一版简化：取前N条，最多max_tracks
        scored = []
        for h in hypotheses:
            score = self._score_hypothesis(h)
            scored.append((h, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # 至少2轨，最多max_tracks
        count = max(2, min(len(scored), self.max_tracks))
        return [h for h, _ in scored[:count]]
    
    def _score_hypothesis(self, hypothesis: Dict) -> float:
        """假设质量评分（简化版，TD-001待优化）"""
        score = 0.5  # 基础分
        
        if hypothesis.get("evidence_support"):
            score += 0.3
        
        if hypothesis.get("source") == "historical":
            score += 0.2
        elif hypothesis.get("source") == "rule_based":
            score += 0.1
        
        return min(score, 1.0)
    
    # ==================== 主循环 ====================
    
    def run(self):
        """执行多轮推理主循环（三相位）"""
        termination_reason = None
        
        for round_num in range(1, self.max_rounds + 1):
            # 检查是否所有轨已停止（在开启新轮之前）
            active_tracks = [t.track_id for t in self.tracks if t.is_active]
            if not active_tracks:
                termination_reason = "all_hypotheses_conclusive"
                # 不开启新轮，使用上一轮的round_num
                break
            
            # 开启新轮
            self.current_round = round_num
            self.board.start_round(round_num, active_tracks)
            
            # Phase R1: 各轨基于已有证据推理
            for track in self.tracks:
                if track.is_active:
                    track.run_phase_r1(round_num)
            
            # Phase E: 执行验证
            self._execute_pending_validations()
            
            # Phase R2: 各轨基于新验证结果更新
            for track in self.tracks:
                if track.is_active:
                    track.run_phase_r2(round_num)
            
            # 结束当前轮（写入termination_reason）
            if termination_reason:
                self.board.end_round(round_num, termination_reason)
            else:
                self.board.end_round(round_num)
        
        # 循环正常结束（达到max_rounds）
        if termination_reason is None:
            termination_reason = "max_rounds_reached"
            self.board.end_round(self.current_round, termination_reason)
        
        # 记录最终终止原因
        self._termination_reason = termination_reason
        
        # 合并结果
        return self._merge_results()
    
    def _execute_pending_validations(self):
        """Phase E: 执行待处理的验证动作（修复 P0-5）"""
        pending_validations = self.board.get_pending_validations()  # 修复：使用封装方法
        
        for val in pending_validations:
            # 调用 Runner 执行验证
            result = self._execute_validation_action(val["action"])
            
            # 写入执行结果
            result_id = f"E_{val['id']}"
            self.board.add_validation_result(
                result_id=result_id,
                action=val["action"],
                result=result["text"],
                evidence_type=result["type"],
                raw_data=result.get("data", {}),
                shared_to=val["requested_by"]
            )
            
            # 标记完成
            self.board.mark_validation_completed(val["id"], result_id)
    
    def _get_pending_validations(self) -> List[Dict]:
        """获取待执行的验证（已废弃，使用board.get_pending_validations()）"""
        return self.board.get_pending_validations()
    
    def _execute_validation_action(self, action: str) -> Dict:
        """执行单个验证动作（简化实现，TODO 接入真实 collector）"""
        # TODO: 根据 action 路由到对应的 collector
        # 第一版 mock
        return {
            "text": f"验证结果：{action}",
            "type": "observation",
            "data": {}
        }
    
    # ==================== 合并 ====================
    
    def _merge_results(self) -> Dict:
        """合并所有轨的结果"""
        hypotheses = []
        
        for track in self.tracks:
            private_ctx = track.get_private_context()
            final_status = self.board.get_hypothesis_status(track.hypothesis_id)
            
            hypotheses.append({
                "id": track.hypothesis_id,
                "description": track.get_current_hypothesis(),
                "status": final_status["status"],
                "confidence": final_status["confidence"],
                "evolution_summary": self._summarize_evolution(private_ctx),
                "key_reasoning_steps": self._extract_key_steps(private_ctx),
                "causal_chain": private_ctx.get("causal_chain")
            })
        
        # 选择主导因果链
        leading_chain = self._select_leading_causal_chain(self.tracks)
        
        return {
            "hypotheses": hypotheses,
            "leading_causal_chain": leading_chain,
            "reasoning_metadata": {
                "tracks_count": len(self.tracks),
                "rounds_executed": self.current_round,
                "termination_reason": self._termination_reason,
                "reasoning_board_path": "./reasoning-board.yaml"
            }
        }
    
    def _summarize_evolution(self, private_ctx: Dict) -> str:
        """总结假设演化"""
        evolution = private_ctx["hypothesis_evolution"]
        if len(evolution) <= 1:
            return "无演化"
        
        first = evolution[0]["text"]
        last = evolution[-1]["text"]
        return f"从 {first} 演化到 {last}"
    
    def _extract_key_steps(self, private_ctx: Dict) -> List[Dict]:
        """提取关键推理步骤"""
        log = private_ctx["reasoning_log"]
        # 简化：取有action和result的条目
        return [
            {
                "round": e["round"],
                "thought": e["thought"],
                "conclusion": e["result"]
            }
            for e in log
            if e["action"] and e["result"]
        ]
    
    def _select_leading_causal_chain(self, tracks: List[HypothesisTrack]) -> Optional[Dict]:
        """选择最优因果链（TD-007待优化）"""
        chains = []
        
        for track in tracks:
            if track.causal_chain:
                status = self.board.get_hypothesis_status(track.hypothesis_id)
                if status["status"] == "supported":
                    chains.append((track.causal_chain, status["confidence"]))
        
        if not chains:
            return None
        
        # 简单选择置信度最高的
        chains.sort(key=lambda x: x[1], reverse=True)
        best_chain = chains[0][0]
        
        return {
            "description": self._chain_to_text(best_chain),
            "nodes": [
                {
                    "event": n.event,
                    "time": n.time
                }
                for n in best_chain.nodes
            ],
            "confidence": best_chain.confidence
        }
    
    def _chain_to_text(self, chain: CausalChain) -> str:
        """因果链转文本"""
        events = [n.event for n in chain.nodes]
        return " → ".join(events)
```

---

## 4. 集成入口

```python
def analyse_phase4_multitrack(incident_dir: Path) -> Dict:
    """第4段多轨推理入口"""
    
    # 1. 生成初始假设（规则 + 历史）
    initial_hypotheses = generate_initial_hypotheses(incident_dir)
    
    # 2. 初始化 Lead
    lead = LeadOrchestrator(
        incident_dir=incident_dir,
        max_rounds=3,
        max_tracks=5
    )
    
    # 3. 初始化轨
    lead.initialize_tracks(initial_hypotheses)
    
    # 4. 运行多轮推理
    result = lead.run()
    
    # 5. 写入 analysis.yaml
    write_analysis_yaml(incident_dir, result)
    
    return result
```
