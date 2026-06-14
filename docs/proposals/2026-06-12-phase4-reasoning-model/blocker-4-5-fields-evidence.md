---
status: critical-fix
last_updated: 2026-06-13
purpose: 修复阻塞点4（停止条件字段缺失）和阻塞点5（证据链断裂）
---

# 阻塞点4：supported 停止条件字段缺失

**问题1**：`_should_track_continue()` 依赖 `CausalChain.is_complete`，但该字段不存在

**问题2**：`_has_critical_gap()` 检查 `gap_detail.criticality`，但 schema 里没有该字段

**修复方案**：

## 1. CausalChain 增加 is_complete 属性

```python
# design-data-structures.md 和 design-interfaces.md

@dataclass
class CausalChain:
    nodes: List['CausalNode']
    edges: List['CausalEdge']
    confidence: float
    is_complete: bool = False  # ✅ 新增字段
    
    def check_completeness(self) -> bool:
        """判断因果链是否完整
        
        规则：
        - 至少3个节点
        - 最后一个节点是"故障现象"（与 timeline 对齐）
        - 所有 edges 置信度 >= 0.5
        """
        if len(self.nodes) < 3:
            return False
        
        # 检查最后一个节点是否是故障现象
        last_node = self.nodes[-1]
        if not any(k in last_node.event.lower() for k in ["失败", "故障", "超时", "错误", "failure", "error"]):
            return False
        
        # 检查 edges 置信度
        if any(e.confidence < 0.5 for e in self.edges):
            return False
        
        self.is_complete = True
        return True
```

## 2. gap_detail 增加 criticality 字段

```yaml
# design-data-structures.md - reasoning-board.yaml schema

evidence_gaps:
  - gap: "overlay_network_topology"
    requested_by: ["track_h2"]
    status: "unavailable"
    reason: "CNI插件未启用拓扑导出"
    can_resolve: false
    criticality: "high"  # ✅ 新增：high/medium/low
    alternative: "可通过 ping/traceroute 间接验证"
```

```python
# design-interfaces.md - ReasoningBoard.add_evidence_gap

def add_evidence_gap(
    self,
    gap: str,
    track_id: str,
    status: str,
    reason: str,
    can_resolve: bool,
    criticality: str = "medium",  # ✅ 新增参数
    alternative: Optional[str] = None
):
    """添加证据缺口"""
    with self._lock:
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
            "criticality": criticality,  # ✅ 新增
            "alternative": alternative,
            "created_at": self._now()
        })
        self._save()
```

## 3. Agent 推理结果需返回 criticality

```python
# design-interfaces.md - HypothesisTrack._take_actions_phase_r1

def _take_actions_phase_r1(self, reasoning_result: Dict):
    """Phase R1: 基于已有证据采取动作"""
    # ... 现有代码
    
    # 写入发现（gap 需包含 criticality）
    for finding in reasoning_result.get("findings", []):
        gap_detail = finding.get("gap_detail")
        
        # ✅ 修复阻塞点4：确保 gap_detail 包含 criticality
        if gap_detail and "criticality" not in gap_detail:
            gap_detail["criticality"] = "medium"  # 默认值
        
        self.board.add_finding(
            track_id=self.track_id,
            round_num=self.current_round,
            finding_type=finding["type"],
            content=finding["content"],
            evidence=finding["evidence"],
            affects=finding["affects"],
            gap_detail=gap_detail
        )
```

## 4. 修正后的停止条件逻辑

```python
# design-interfaces.md - HypothesisTrack._should_track_continue

def _should_track_continue(self, status: str) -> bool:
    """判断轨是否应继续下一轮（修复阻塞点4）"""
    if status == "refuted":
        return False
    
    if status == "supported":
        # ✅ 修复：check_completeness() 而不是直接读 is_complete
        chain_complete = False
        if self.causal_chain:
            chain_complete = self.causal_chain.check_completeness()
        
        has_critical_gap = self._has_critical_gap()
        
        # 因果链完整 且 无关键缺口 → 停止
        if chain_complete and not has_critical_gap:
            return False
        
        # 否则继续深入
        return True
    
    return True

def _has_critical_gap(self) -> bool:
    """检查是否存在关键证据缺口（修复阻塞点4）"""
    # 方法1：从最近的 findings 检查
    recent_findings = self.board.get_findings_up_to_round(self.current_round)
    for f in recent_findings:
        if (f.get("track") == self.track_id 
            and f.get("type") == "gap"
            and f.get("gap_detail", {}).get("criticality") == "high"):  # ✅ 字段存在
            return True
    
    # 方法2：从 board.evidence_gaps 检查
    for gap in self.board._data.get("evidence_gaps", []):
        if (self.track_id in gap.get("requested_by", [])
            and gap.get("criticality") == "high"):
            return True
    
    return False
```

---

# 阻塞点5：证据链断裂

**问题**：
- `add_validation_result()` 写入时没有 `evidence_id` 字段
- `_process_validation_result()` 却读取 `val_result["evidence_id"]`
- 导致 finding.evidence 为空引用

**修复方案**：

## 1. add_validation_result 补充 evidence_id

```python
# design-interfaces.md - ReasoningBoard.add_validation_result

def add_validation_result(
    self,
    result_id: str,  # 这就是 evidence_id
    action: str,
    result: str,
    evidence_type: str,
    raw_data: Dict,
    shared_to: List[str]
):
    """添加验证结果（修复阻塞点5：补充 evidence_id）"""
    with self._lock:
        self._data["executed_validations"][result_id] = {
            "evidence_id": result_id,  # ✅ 新增：显式写入 evidence_id
            "action": action,
            "result": result,
            "evidence_type": evidence_type,
            "raw_data": raw_data,
            "shared_to": shared_to,
            "executed_at": self._now()
        }
        self._save()
```

## 2. _process_validation_result 确保字段存在

```python
# design-interfaces.md - HypothesisTrack._process_validation_result

def _process_validation_result(self, val_result: Dict):
    """处理单个验证结果，生成 finding（修复阻塞点5）"""
    evidence_type = val_result.get("evidence_type", "observation")
    
    if evidence_type == "refutation":
        impact = "refute"
    elif evidence_type == "support":
        impact = "support"
    else:
        impact = "observation"
    
    # ✅ 修复阻塞点5：确保 evidence_id 存在
    evidence_id = val_result.get("evidence_id")
    if not evidence_id:
        # 兜底：从 executed_validations 的 key 获取
        for key, val in self.board._data["executed_validations"].items():
            if val.get("action") == val_result.get("action"):
                evidence_id = key
                break
    
    self.board.add_finding(
        track_id=self.track_id,
        round_num=self.current_round,
        finding_type=evidence_type,
        content=val_result["result"],
        evidence=[evidence_id] if evidence_id else [],  # ✅ 确保有值
        affects=[{
            "hypothesis": self.hypothesis_id,
            "impact": impact,
            "confidence": 0.8
        }]
    )
```

## 3. 完整的证据追踪链

```
[验证请求]
validation_queue[val_001]:
  action: "check_dns_resolution"
  requested_by: ["track_h1"]
  result_id: "E_dns_001"  ← 指向 evidence

↓

[验证结果]
executed_validations["E_dns_001"]:
  evidence_id: "E_dns_001"  ✅ 显式记录
  action: "check_dns_resolution"
  result: "DNS正常"
  evidence_type: "refutation"

↓

[发现]
findings[F001]:
  content: "DNS正常，h1被反证"
  evidence: ["E_dns_001"]  ✅ 引用完整

↓

[分析输出]
hypotheses[h1]:
  counter_evidence:
    - source: "check_dns_resolution"  ← 从 E_dns_001.action
      detail: "DNS正常"                ← 从 E_dns_001.result
```

## 4. 封装成 ReasoningBoard 方法

```python
class ReasoningBoard:
    def link_validation_to_finding(self, validation_id: str, finding_id: str):
        """建立验证结果与 finding 的双向链接（可选，增强追溯性）"""
        # 在 validation 里记录它影响了哪个 finding
        for v in self._data["validation_queue"]:
            if v["id"] == validation_id:
                if "linked_findings" not in v:
                    v["linked_findings"] = []
                v["linked_findings"].append(finding_id)
                self._save()
                break
```

---

# 修复总结

| 阻塞点 | 修复内容 | 受影响文件 |
|--------|---------|-----------|
| 4.1 | CausalChain 增加 `is_complete` 和 `check_completeness()` | design-data-structures.md, design-interfaces.md |
| 4.2 | evidence_gaps 增加 `criticality` 字段 | design-data-structures.md, design-interfaces.md |
| 4.3 | gap_detail 确保包含 `criticality` | design-interfaces.md |
| 4.4 | _has_critical_gap() 使用正确字段 | design-interfaces.md |
| 5.1 | executed_validations 增加 `evidence_id` 字段 | design-interfaces.md |
| 5.2 | _process_validation_result() 兜底逻辑 | design-interfaces.md |

这些修复后，停止条件和证据链将完整可用。
