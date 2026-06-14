---
status: fix
last_updated: 2026-06-13
purpose: 响应 review 意见，修复 P0 级设计矛盾
---

# Design Review 修复清单

## P0 问题修复（必须在实现前完成）

### P0-4: supported 轨是否继续 — 核心逻辑矛盾

**问题**：
- `design-interfaces.md`: supported → is_active = False（立即停止）
- `design-execution-flow.md`: H3 Round 1 supported，Round 2 继续深入慢查询
- `isolation-sharing-design.md`: refuted 轨完成当轮、下轮停

**修复决策**：
```python
# 新规则：区分 validation_result（客观判定）与 is_active（是否继续）

def should_track_continue(hypothesis_status, private_context):
    """判断轨是否应继续下一轮"""
    
    # refuted → 停止
    if hypothesis_status.status == "refuted":
        return False
    
    # supported 但因果链未闭合或存在 critical_gap → 继续
    if hypothesis_status.status == "supported":
        causal_chain = private_context.causal_chain
        has_critical_gap = private_context.has_critical_gap()
        
        # 因果链完整 且 无关键缺口 → 停止
        if causal_chain and causal_chain.is_complete() and not has_critical_gap:
            return False
        
        # 否则继续深入
        return True
    
    # insufficient 或 pending → 继续
    return True
```

**修改点**：
1. `design-interfaces.md` §2: `_update_hypothesis_status` 改为调用 `should_track_continue`
2. `design-execution-flow.md` §3: 补充"supported 但因果链未完整"的判断逻辑
3. `design-execution-flow.md` §7: 时序图 Round 2 标注"H3 虽 supported 但因果链未完整，继续"

---

### P0-5: 单轮 O-R-A 与 Runner 执行时机冲突

**问题**：
- `HypothesisTrack.run_round()` 只 request_validation，不等 Runner 执行
- Agent 在当轮 `_reason()` 时看不到当轮请求的验证结果
- `execution-flow` 说 Lead step 8 执行验证，但 interfaces 没这一步

**修复决策**：单轮拆为**三相位**

```
Phase R1（推理基于已有证据）:
  各轨读共享层 → Agent 推理 → 写 findings（基于已有证据） + 请求 validation

Phase E（执行验证）:
  Lead/Runner 执行 pending validations → 写 executed_validations

Phase R2（推理基于新证据，可选）:
  各轨读新验证结果 → 更新 findings / hypothesis_status / causal_chain
```

**关键**：
- Phase R1 的 findings 只能基于 `base_evidence + 上一轮的 executed_validations`
- 当轮新验证结果在 Phase R2 才可见
- Phase R2 可简化为"静默更新"，不再调用 Agent（MVP）

**修改点**：
1. `design-interfaces.md` §2: `HypothesisTrack.run_round` 拆为 `run_phase_r1()` + `run_phase_r2()`
2. `design-interfaces.md` §3: `LeadOrchestrator.run` 补充 Phase E 执行验证
3. `design-execution-flow.md` §3: 伪代码标注三相位
4. `design-execution-flow.md` §7: 时序图改为三相位

---

### P0-1: analysis.yaml 映射与 L1 模板对齐

**问题**：
- 设计用 `id`, `description`, `status`, `confidence: 0.85`, `causal_chain: {nodes, edges}`
- 模板要求 `hypothesis_id`, `statement`, `validation_result`, `confidence: high/medium/low`, `causal_path: [...]`

**修复决策**：补充映射表

```yaml
# Board/Track → analysis.yaml 映射规则

# 1. 假设 ID
track.hypothesis_id → hypothesis_id  # 直接映射

# 2. 假设描述
track.get_current_hypothesis() → statement  # 直接映射

# 3. 状态
board.hypothesis_status[h].status → validation_result
  映射规则:
    refuted → refuted
    supported → supported
    insufficient → insufficient
    pending → pending（不应出现在终稿）

# 4. 置信度（转换）
board.hypothesis_status[h].confidence (float 0-1) → confidence (enum)
  转换规则:
    >= 0.7 → high
    >= 0.4 → medium
    < 0.4  → low

# 5. 因果链（转换）
track.causal_chain (CausalChain object) → causal_path (List[str])
  转换规则:
    nodes 按拓扑序排列 → 提取 event 文本 → 列表
    示例: [{"event": "慢查询"}, {"event": "连接池满"}] → ["慢查询突增", "连接池积压"]

# 6. 新增字段（软扩展，review/finalize 不依赖）
evolution_summary, key_reasoning_steps 写入，但标为可选
reasoning_metadata 写入 analysis，不影响现有流程
```

**修改点**：
1. `design-data-structures.md` §3: 补充映射表章节
2. `design-interfaces.md` §3: `_merge_results` 使用映射规则
3. `design-execution-flow.md` §6: 合并伪代码改用映射

---

### P0-2: 枚举用词统一

**修复决策**：
- **状态枚举**：统一用 `refuted` / `supported` / `insufficient` / `pending`
- **影响动作**：统一用 `refute` / `support` / `gap`（动词，表示该 finding 的作用）
- **置信度**：
  - 内部存储：`float 0-1`
  - 对外输出（analysis.yaml）：`high / medium / low`（按 P0-1 映射）
  - cross_refutations.confidence: 统一用 `high / medium / low`（字符串）

**修改点**：
1. `design-data-structures.md` §1: 在 schema 注释标注类型
2. 所有文档：检查并统一用词

---

### P0-3: MVP 黑板落盘策略

**修复决策**：**第一版落盘**

**理由**：
- review 强调追溯性很重要
- 落盘成本低（就是写 YAML）
- 已有 technical-debt.md 需修改

**修改点**：
1. `technical-debt.md`: TD-XXX 删除"阶段1不落盘"
2. `design-data-structures.md`: 确认 MVP 落盘
3. `design-interfaces.md`: 保持 `_save()` 实现

---

### P0-6: 时序图因果倒置

**问题**：H1 在 Runner 执行 check_dns 之前就 add_finding(F001: DNS正常)

**修复决策**：标注 finding 来源

```yaml
findings:
  - id: F001
    source: "from_existing_evidence"  # 新增字段
    content: "DNS解析正常（来自 structured_record.dns_checks）"
    evidence: ["structured_record:dns_checks"]
```

**或**：时序图改为先 Runner 执行，再轨写 finding

**修改点**：
1. `design-data-structures.md` §1: findings 增加 `source` 字段
2. `design-execution-flow.md` §7: 时序图调整顺序或标注来源

---

### P0-7: 提前终止 vs 固定 3 轮

**修复决策**：**MVP 固定 3 轮**，智能终止标为 TD-002

**修改点**：
1. `design-execution-flow.md` §5: 注释掉智能终止代码
2. `design-execution-flow.md` §7: 时序图改为"达到 max_rounds"或"all_inactive"

---

### P0-8: conclusion_summary 形态

**修复决策**：输出结构化对象

```python
conclusion_summary = {
    "statement": "根因：慢查询导致连接池耗尽",
    "confidence": "high",  # 映射自 float
    "impact_scope": {
        "affected_components": ["mongodb", "connection-pool"],
        "onset_time": "2026-06-12T14:23:05Z"
    },
    "limitations": [
        "未验证代码层面是否存在查询优化空间"
    ],
    "deepest_supported_level": "platform"  # infra/platform/app/code
}
```

**修改点**：
1. `design-execution-flow.md` §6: 合并伪代码改用结构化
2. `design-interfaces.md` §3: `_merge_results` 补充字段

---

### P0-9: 与现有 analyse 链路对接

**修复决策**：明确嵌入点

```python
# tools/plugin/midstack-local.py

def analyse(args):
    incident_dir = Path(args.incident_dir)
    
    # 第1段：信号发现（保持不变）
    # 第2段：远程采集（保持不变）
    # 第3段：信号治理（保持不变）
    # ... 现有代码 ...
    
    # 规则预补采（保持不变）
    recollection_needed = run_directed_recollection_if_needed(incident_dir)
    
    # 规则 analyse 草稿（保持，作为初始假设来源）
    draft = analyse_with_rules(incident_dir)  # 生成 analysis.rule-draft.yaml
    
    # 【新】第4段：多轨推理（替代原 write_agent_reasoning_task + Cursor Agent）
    from .phase4_multitrack import run_phase4_multitrack
    analysis = run_phase4_multitrack(incident_dir, rule_draft=draft)
    
    # 第5段：finalize + review（保持不变）
    finalize_analysis(incident_dir, analysis)
    review_if_needed(incident_dir)
```

**关键**：
- `analysis.rule-draft.yaml` 作为初始假设来源（不废弃）
- Cursor Agent 合同 `agent-reasoning-task.md` **被替代**（多轨内部调 Agent API）
- `finalize-analysis` 和 `review` 依赖的 `analysis.yaml` 格式必须对齐模板

**修改点**：
1. `design-execution-flow.md` §9: 改用真实函数名
2. 补充章节：说明与 rule-draft、directed_recollection 关系

---

## 修复后的文档结构

```
docs/proposals/2026-06-12-phase4-reasoning-model/
├── design-data-structures.md        [修改] 补 P0-1 映射表、P0-2 枚举、P0-6 source
├── design-interfaces.md             [修改] P0-4 继续规则、P0-5 三相位
├── design-execution-flow.md         [修改] P0-5/7/8/9 全面修订
├── design-review-fixes.md           [新增] 本文件
└── technical-debt.md                [修改] 删除"阶段1不落盘"
```

---

## 下一步

修复完 P0 后，逐个修复 P1 问题（不阻塞实现，但影响质量）：
- P1-5: 封装破坏
- P1-7: cross_refutations 接入
- P1-8: 线程安全模型
- P1-9: 原子写
- ... 等

修复完成后，重新 review 三份设计文档的一致性。
