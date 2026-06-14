---
status: tracking
last_updated: 2026-06-13
purpose: 追踪第4段多轨推理实现中为MVP快速而妥协的部分，确保后续优化
---

# 技术债与后续优化清单

## Phase 1 MVP 妥协点（2周交付）

### TD-001: 假设轨数量 - 固定 vs 动态

**当前实现（MVP）**：
- 固定轨数上限（如5轨）
- 简单质量评分：有证据=0.8，无=0.4

**待优化**：
- 实现完整的 `calculate_hypothesis_score()` 算法
- 考虑假设间差异度（避免启动重复假设轨）
- 考虑Token成本预算（如用户设置最大成本）

**优先级**: P1（影响效果）
**预计工作量**: 2天
**触发条件**: MVP验证有效后立即优化

---

### TD-002: 轮次终止 - 固定 vs 智能

**当前实现（MVP）**：
- 固定3轮终止
- 或所有轨 inactive

**待优化**：
```python
def should_continue(board, round_num):
    # 智能终止条件
    has_supported = any(h.status == "supported" for h in board.hypotheses)
    has_critical_gap = any(f.type == "gap" and f.criticality == "high" 
                           for f in board.findings)
    
    # 有支持假设 且 无关键缺口 → 可以终止
    if has_supported and not has_critical_gap:
        return False
    
    # 所有假设都已结论 → 终止
    all_conclusive = all(h.status in ["refuted", "supported"] 
                         for h in board.hypotheses)
    return not all_conclusive
```

**优先级**: P1
**预计工作量**: 1天
**触发条件**: MVP验证后

---

### TD-003: Agent主导补采循环

**当前实现（MVP）**：
- 只用规则预补采（在Agent推理之前）
- Agent不能识别gap后触发补采

**待优化**：
- Agent/轨识别 `critical_gap` → 写入共享层
- Lead门禁判断是否补采
- Runner执行 → 新证据写回共享层
- 轨继续下一轮推理

**优先级**: P2（功能完整性）
**预计工作量**: 3-4天
**触发条件**: MVP验证有效 + 发现gap场景频繁

---

### TD-004: 深入分支（代码/专家路径）

**当前实现（MVP）**：
- 不实现自动触发
- 只在合同中提及，作为 `next_actions`

**待优化**：
- 条件触发规则：何时进入深入分支
- 代码路径分析集成（Git/源码检索）
- 专家路径集成（runbook深步骤）

**优先级**: P3（增强功能）
**预计工作量**: 1周
**触发条件**: 基础推理覆盖率达标后

---

### TD-005: 历史案例检索

**当前实现（MVP）**：
- 数据库未实现
- 历史案例接口预留但不调用

**待优化**：
- 实现案例数据库（向量检索或规则匹配）
- 集成到假设生成阶段
- 验证历史案例对假设质量的提升

**优先级**: P2
**预计工作量**: 1-2周（含数据库设计）
**触发条件**: 积累足够案例数据后（如>50个incident）

---

### TD-006: 假设演化路径可视化

**当前实现（MVP）**：
- 只记录在隔离层 YAML
- 无可视化

**待优化**：
- 生成假设演化图（Mermaid或可交互）
- 展示：h0 → h1(refuted) → h2(supported)
- 便于人工审计和调试

**优先级**: P3
**预计工作量**: 2-3天
**触发条件**: 用户反馈"难以理解推理过程"

---

### TD-007: 因果链冲突解决策略

**当前实现（MVP）**：
- Lead简单选择最高置信度因果链
- 其他链丢弃

**待优化**：
```python
def merge_causal_chains(tracks):
    # 不只是选一条，而是：
    # 1. 尝试合并兼容的链
    # 2. 标记互斥的分支
    # 3. 输出因果图（DAG），而非单链
    pass
```

**优先级**: P2
**预计工作量**: 3天
**触发条件**: 发现多条高置信度互斥链的case

---

## Phase 2: 性能优化（MVP+4周）

### TD-101: 并行执行真实并行

**当前实现（MVP）**：
- 可能是顺序调用3个Agent（取决于Cursor实现）

**待优化**：
- 确保真正并行（如果Cursor支持）
- 或利用异步API

**优先级**: P2
**预计工作量**: 视宿主能力而定

---

### TD-102: Token成本优化

**当前实现（MVP）**：
- 3轨完整上下文，可能重复

**待优化**：
- 共享层做上下文复用
- 隔离层压缩冗余信息

**优先级**: P2
**预计工作量**: 1周

---

## Phase 3: 产品化（MVP+8周）

### TD-201: reasoning-board UI

**当前实现（MVP）**：
- 只有YAML文件

**待优化**：
- Web UI展示推理过程
- 交互式探索（展开/收起轨）
- 时间线对齐视图

**优先级**: P3
**预计工作量**: 2周

---

## 追踪机制

**每次迭代后更新此文档**：
- 标记已完成项：`status: done`
- 添加新发现的技术债
- 调整优先级

**Review节奏**：
- MVP完成后：Review P1项，决定立即优化还是延后
- 每月：Review全部技术债，调整优先级

**代码中关联**：
```python
# TODO(TD-003): Agent主导补采循环未实现
# 见 docs/proposals/2026-06-12-phase4-reasoning-model/technical-debt.md
```
