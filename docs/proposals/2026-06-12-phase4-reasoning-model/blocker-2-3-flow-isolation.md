---
status: critical-fix
last_updated: 2026-06-13
purpose: 修复阻塞点2（双流程冲突）和阻塞点3（同轮隔离）
---

# 阻塞点2：双流程冲突修复

**问题**：design-execution-flow.md 前半段用旧流程，后半段用新流程

**修复方案**：删除旧流程伪代码，只保留新流程（§9 的 run_phase4_multitrack）

---

# 阻塞点3：同轮隔离修复

**问题**：
- `HypothesisTrack._observe()` 在 R1 读取 `get_findings_by_round(self.current_round)`
- Lead 顺序执行各轨 R1
- 后执行的轨会看到先执行轨刚写的 finding → 违反隔离原则

**根因**：轮次概念混淆
- `self.current_round` 是当前正在执行的轮次
- R1 阶段应该只读**上一轮完成的** findings

**修复方案**：

```python
# 修复前（错误）
class HypothesisTrack:
    def _observe(self, include_current_round_validations: bool = True) -> Dict:
        return {
            "recent_findings": self.board.get_findings_by_round(self.current_round),  # ❌ 读当前轮
            # ...
        }

# 修复后（正确）
class HypothesisTrack:
    def _observe(self, include_current_round_validations: bool = True) -> Dict:
        # Phase R1: 只读上一轮的 findings（防止同轮污染）
        # Phase R2: 可以读当前轮的 findings（因为所有轨 R1 已完成）
        max_round = self.current_round - 1 if not include_current_round_validations else self.current_round
        
        return {
            "recent_findings": self.board.get_findings_up_to_round(max_round),  # ✅ 读截至某轮
            "my_validations": self._get_my_validation_results(include_current_round_validations),
            # ...
        }
```

**ReasoningBoard 新增方法**：

```python
class ReasoningBoard:
    def get_findings_up_to_round(self, round_num: int) -> List[Dict]:
        """获取截至某轮的所有 findings（不含当前轮未完成的）"""
        return [
            f for f in self._data["findings"]
            if f["round"] <= round_num
        ]
```

**执行顺序保证**：

```python
# LeadOrchestrator.run() - 三相位执行

for round_num in range(1, self.max_rounds + 1):
    # Phase R1: 所有轨基于**上一轮**数据推理（隔离）
    for track in self.tracks:
        if track.is_active:
            track.run_phase_r1(round_num)  # 内部读 get_findings_up_to_round(round_num - 1)
    
    # Phase E: 执行验证
    self._execute_pending_validations()
    
    # Phase R2: 所有轨基于**当前轮**新验证更新（共享）
    for track in self.tracks:
        if track.is_active:
            track.run_phase_r2(round_num)  # 可读 get_findings_up_to_round(round_num)
```

**关键修复点**：
1. `_observe()` 在 R1 时用 `round - 1`，R2 时用 `round`
2. 新增 `get_findings_up_to_round()` 替代 `get_findings_by_round()`
3. 明确注释"同轮隔离、轮间共享"语义

---

# 完整修复代码

```python
# design-interfaces.md 修复

class HypothesisTrack:
    def run_phase_r1(self, round_num: int):
        """Phase R1: 基于上一轮数据推理（隔离）"""
        self.current_round = round_num
        
        if not self.is_active:
            return
        
        # ✅ 修复阻塞点3：只读上一轮数据
        observations = self._observe(include_current_round_validations=False)
        
        reasoning_result = self._reason(observations)
        self._take_actions_phase_r1(reasoning_result)
        self._pending_reasoning_result = reasoning_result
    
    def run_phase_r2(self, round_num: int):
        """Phase R2: 基于当前轮新验证更新（共享）"""
        if not self.is_active:
            return
        
        new_validations = self._get_current_round_validation_results()
        
        if new_validations:
            for val_result in new_validations:
                self._process_validation_result(val_result)
        
        self._update_hypothesis_status(self._pending_reasoning_result)
    
    def _observe(self, include_current_round_validations: bool = True) -> Dict:
        """读取共享层（修复阻塞点3：防止同轮污染）
        
        Args:
            include_current_round_validations: 
                False (R1): 只读上一轮完成的数据
                True (R2): 读包含当前轮的数据
        """
        # 关键修复：R1 读 round-1，R2 读 round
        max_round = self.current_round - 1 if not include_current_round_validations else self.current_round
        
        return {
            "base_evidence": self.board.get_base_evidence(),
            "hypothesis_status": self.board.get_all_hypothesis_status(),
            "recent_findings": self.board.get_findings_up_to_round(max_round),  # ✅ 修复
            "my_validations": self._get_my_validation_results(include_current_round_validations),
            "refutations_against_me": self.board.get_refutations_for_hypothesis(self.hypothesis_id)
        }

class ReasoningBoard:
    # 新增方法
    def get_findings_up_to_round(self, round_num: int) -> List[Dict]:
        """获取截至某轮的所有 findings（修复阻塞点3）"""
        return [
            f for f in self._data["findings"]
            if f["round"] <= round_num
        ]
    
    def get_base_evidence(self) -> Dict:
        """获取基础证据（修复封装，避免直接访问 _data）"""
        return self._data["base_evidence"]
```
