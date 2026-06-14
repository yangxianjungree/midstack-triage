---
status: fixing
purpose: P0/P1剩余问题修复清单
---

# P0/P1 剩余问题修复

## P0-A: 时序图和鸟瞰图更新 ✅

### §1 鸟瞰图
- 修复前: O→R→A
- 修复后: R1→E→R2（三相位）

### §7 时序图需修复
1. R1里不应有 update_hypothesis_status
2. 终止条件改为轮次开头 all_inactive
3. H2 insufficient继续运行（不跳过）

## P0-B: R2状态推导规则

在 HypothesisTrack 补充：

```python
def _derive_final_status_in_r2(
    self, 
    r1_result: Dict, 
    validation_results: List[Dict]
) -> Tuple[str, float]:
    """R2阶段根据验证结果推导最终状态
    
    优先级：
    1. 验证结果有 refutation → refuted (高置信)
    2. 验证结果有 support → 保留或提升到 supported
    3. 无验证结果 → 保持 R1 结果
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
    
    # 无关键验证结果，保持 R1
    return (
        r1_result.get("hypothesis_status", "pending"),
        r1_result.get("confidence", 0.5)
    )
```

## P1-1: insufficient停止规则

在 _should_track_continue 补充：

```python
if status == "insufficient":
    # 不可解决的高关键gap → 停止
    critical_gaps = self.board.get_critical_gaps_for_track(self.track_id)
    unresolvable_gaps = [g for g in critical_gaps if not g.get("can_resolve", True)]
    
    pending_vals = self.board.get_pending_validations_for_track(self.track_id)
    
    if unresolvable_gaps and not pending_vals:
        return False
    
    return True
```

## P1-2: add_evidence_gap 补充 criticality

```python
def add_evidence_gap(
    self,
    gap: str,
    track_id: str,
    status: str,
    reason: str,
    can_resolve: bool,
    criticality: str = "medium",  # 新增
    alternative: Optional[str] = None
):
```

## P1-3: 映射层bug修复

| 函数 | 问题 | 修复 |
|------|------|------|
| causal_chain_to_path | 按对象写 | 改为 `chain.get("nodes", [])` |
| map_hypothesis_to_l1 | 用 hypothesis["status"] | 改为 `board.get_hypothesis_status(hypothesis_id)["status"]` |
| extract_validation_actions | 用 v.get("result") | 改为 `board.get_validation_result_data(v["result_id"])` |
| update_hypothesis_status | 覆盖 desc | 删除 desc 参数 |
| _has_critical_gap | 末尾不可达 return | 删除重复 return False |

## P2: 文档碎片

1. design-data-structures.md:463 多余```
2. design-execution-flow.md:98-100 空code fence
3. reasoning_metadata.termination_reason 示例改为 all_hypotheses_conclusive
