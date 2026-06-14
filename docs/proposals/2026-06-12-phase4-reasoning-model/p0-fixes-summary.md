---
status: completed
last_updated: 2026-06-13
purpose: P0 问题修复完成总结
---

# P0 问题修复完成总结

## 已完成修复的 P0 问题

### ✅ P0-4: supported 后继续规则
**文件**: `design-interfaces.md`
**修改点**:
- 新增 `_should_track_continue()` 方法
- 规则：refuted→停止；supported但因果链未完整或有critical_gap→继续；supported且完整→停止
- 修改 `_update_hypothesis_status()` 调用新规则

### ✅ P0-5: 单轮 O-R-A 相位
**文件**: `design-interfaces.md`
**修改点**:
- 拆分 `run_round()` 为 `run_phase_r1()` + `run_phase_r2()`
- Phase R1: 基于已有证据推理，请求验证
- Phase E: Lead 执行验证（新增 `_execute_pending_validations()`）
- Phase R2: 基于新验证结果更新
- `LeadOrchestrator.run()` 改为三相位执行

### ✅ P0-1: analysis.yaml 映射
**文件**: `design-data-structures.md`
**修改点**:
- 新增第5节：Board → analysis.yaml 映射表
- 明确字段对应关系（hypothesis_id, statement, validation_result, confidence, causal_path）
- 提供置信度转换函数（float → high/medium/low）
- 提供因果链转换函数（CausalChain → List[str]）

### ✅ P0-2: 枚举用词统一
**文件**: `design-data-structures.md`
**修改点**:
- 新增第7节：枚举用词统一表
- 状态：refuted/supported/insufficient/pending
- 置信度内部：float；对外：high/medium/low
- 发现影响：refute/support/gap/observation

### ⚠️ P0-3: MVP 落盘策略（需确认）
**决策**: 第一版落盘 `reasoning-board.yaml`
**待修改**: `technical-debt.md` 删除"阶段1不落盘"描述

### ⚠️ P0-6: 时序图因果倒置（待修改）
**待修改**: `design-execution-flow.md` §7 时序图
**方案**: 改为三相位顺序，标注 finding 来源

### ⚠️ P0-7: 提前终止 vs 固定 3 轮（待修改）
**待修改**: `design-execution-flow.md` §5 + §7
**方案**: MVP 固定3轮，注释掉智能终止，时序图改为"max_rounds"

### ⚠️ P0-8: conclusion_summary 结构（待修改）
**待修改**: `design-execution-flow.md` §6 + `design-interfaces.md` §3
**方案**: 输出结构化对象（statement, confidence, impact_scope, limitations, deepest_supported_level）

### ⚠️ P0-9: 链路对接（待修改）
**待修改**: `design-execution-flow.md` §9
**方案**: 
```python
def analyse(args):
    # ... 第1-3段保持不变
    
    # 规则预补采（保持）
    run_directed_recollection_if_needed(incident_dir)
    
    # 规则草稿（保持，作为初始假设来源）
    draft = analyse_with_rules(incident_dir)
    
    # 【新】第4段多轨推理（替代 Agent 合同）
    from .phase4_multitrack import run_phase4_multitrack
    analysis = run_phase4_multitrack(incident_dir, rule_draft=draft)
    
    # 第5段 finalize + review（保持）
    finalize_analysis(incident_dir, analysis)
```

---

## 剩余需要修改的文件

由于时间和上下文限制，以下P0问题的修复方案已在 `design-review-fixes.md` 中明确，但文件修改尚未完成：

1. **P0-3**: `technical-debt.md` - 删除"不落盘"描述
2. **P0-6**: `design-execution-flow.md` §7 - 修改时序图为三相位
3. **P0-7**: `design-execution-flow.md` §5 + §7 - 固定3轮，改时序图
4. **P0-8**: `design-execution-flow.md` §6 + `design-interfaces.md` §3 - 结构化 conclusion
5. **P0-9**: `design-execution-flow.md` §9 - 真实函数名对接

---

## 建议后续步骤

**选项A**: 你先review已完成的修复（P0-1/2/4/5），确认方向OK后我继续完成剩余修复

**选项B**: 我现在立即完成剩余的 P0-3/6/7/8/9 修复

**选项C**: 基于当前进度开始实现代码，剩余修复在实现时同步完成

---

## 核心修复已完成

最关键的两个逻辑矛盾已解决：
- ✅ **P0-4**: supported 轨是否继续（H3 案例现在逻辑自洽）
- ✅ **P0-5**: 单轮内验证执行时机（三相位模型清晰）

这两个修复后，设计的核心流程已可自洽，剩余的P0-6/7/8/9主要是文档完整性和对接细节，不影响核心逻辑。
