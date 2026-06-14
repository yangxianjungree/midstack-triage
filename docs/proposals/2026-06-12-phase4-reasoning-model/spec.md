---
status: draft
last_updated: 2026-06-12
supersedes: none
superseded_by: none
---

# Spec: 第 4 段推理模型统一与并行假设流水线预研

## Objective

统一 midstack-triage 第 4 段（`推理诊断与深入验证`）在文档、合同与运行时中的概念模型，消除「多假设并行」「多轮论证」「深入验证」「多路线」等术语混用带来的理解偏差。

预研目标：评估「多条假设推理流水线可并行执行、且流水线间共享信息、互相补强」是否应成为第 4 段的标准执行模型；若是，明确与现有已收敛决策的边界、最小可行路径和验证方式。

**不在本 spec 范围内：** 立即实现并行编排器；修改 L1 模板或 taxonomy（除非预研结论要求）。

## ASSUMPTIONS I'M MAKING

1. 五段式主流程名称保持不变，第 4 段对外仍叫 `推理诊断与深入验证`。
2. 「并行」指**执行层**可并发（多 Agent / 多推理轨），而非仅在 `analysis.yaml` 里并列多条假设记录。
3. 用户侧主路径仍为单次 `/midstack:analyse`（与 2026-06-11 已收敛决策一致）。
4. 定向补采仍遵守只读 + catalog 白名单 + 轮次/动作上限。
5. 历史案例 / runbook / skill 仍只做假设来源与验证路径来源，不做现场证据。
6. Cursor 是当前主要 Agent 宿主；并行能力预研以 Cursor Task / 子 Agent 能力为基线，不假设 Claude Code Agent Teams 可用。

→ 若以上有误，请在 Plan 阶段前纠正。

## 现状审计：术语与实现的三层错位

当前仓库里，「第 4 段」至少混用了三个不同层级的概念，且文档与代码未显式分层：

| 层级 | 常见说法 | 实际含义 | 文档位置 | 代码/运行时 |
|------|----------|----------|----------|-------------|
| **L0 段名** | 推理诊断与深入验证 | 五段式第 4 段用户可见名称 | `triage-workflow.spec.md` §5 | `agent-reasoning-task.md` 称 stage-4 |
| **L1 数据模型** | 多假设并行维护 | 同一 `analysis.yaml` 内并列多条 `hypotheses[]` | `discussions.md` 已收敛 | `mongodb-analyse.py` 规则草稿；Agent 合同要求 multi-hypothesis |
| **L2 时间循环** | 多轮猜想论证 / 定向补采小循环 | 证据不足时：推理 → 补采 → 再推理 | `presentation.md` §5.4；`discussions.md` | `run_directed_recollection_if_needed()` 存在，但触发在 **规则 runner 阶段、Agent 推理之前**，非「Agent 识别 gap 后再补采再推理」 |
| **L3 条件分支** | 深入验证 / 代码级分析 / 专家级分支 | 证据指向平台/源码问题时才进入 | `presentation.md` §5.4 | `triage-workflow.spec.md` 明确**当前不纳入** |
| **L4 执行编排**（用户设想） | 多路线、并行假设流水线、信息共享 | 每条假设独立推理轨，可并发、可互传反证 | `references/orchestration-patterns.md` 有类比（competing-hypothesis debugging） | **未实现**；当前为单次 Agent 读 task → 写 `analysis.yaml` |

### 关键不一致（需统一）

1. **「并行」一词多义**
   - 已落地：假设**数据结构**并行（多条 hypothesis 共存）。
   - 文档愿景：推理**过程**多轮（时间上的循环）。
   - 用户设想：推理**执行**并行（空间上的多轨 + 共享黑板）。

2. **「深入验证」一词多义**
   - 段名的一部分（与「推理诊断」并列）。
   - `presentation.md` 中的条件分支（代码级 / 专家级深入分析）。
   - `validation_actions` / `validation_result` 字段语义（每条假设的验证状态）。

3. **Phase 4 / 5 边界在运行时模糊**
   - `write_agent_reasoning_task()` 将 stage-4 reasoning 与 stage-5 summarization 写在同一 task。
   - 规范上第 5 段是「结论整合与知识沉淀」，但 Agent 一次写完 `conclusion_summary` + `knowledge_candidates`。

4. **已决策的「Agent 主导定向补采」与代码顺序不完全一致**
   - 讨论结论：Agent 从 gap / `validation_actions` 选补采 → runner 执行 → 再推理。
   - 当前代码：`远程采集 → 规则定向补采 → 规则 analyse 草稿 → Agent 单次推理`。

## 提议：统一概念模型（四层）

建议在 L1 规范与所有对外文档中，固定使用以下分层词汇，避免再用模糊词「多路线」：

```
第 4 段（段名不变）
├── 4.1 假设组合（Hypothesis Portfolio）     ← 原「多假设并行维护」
├── 4.2 证据循环（Evidence Loop）            ← 原「多轮论证 / 定向补采小循环」
├── 4.3 深入分支（Deep Analysis Branches）   ← 原「深入验证」中条件触发的子路径
└── 4.4 编排模式（Orchestration Mode）       ← 新增：单轨 vs 多轨并行（预研项）
```

### 4.1 假设组合（Hypothesis Portfolio）

- **定义：** 基于第 3 段证据包，同时维护多条可比较的候选假设。
- **产物：** `analysis.yaml` → `hypotheses[]`（字段以 `analysis.template.yaml` 为准）。
- **原则：** 不急于单一结论；每条假设带支持证据、反证、缺口、验证动作、`validation_result`。
- **与「并行」关系：** 这是**逻辑并行**（并存），不隐含**执行并行**。

### 4.2 证据循环（Evidence Loop）

- **定义：** 当存在 `critical_gap` 且白名单内有增益明确的只读动作时，在单次 `/midstack:analyse` 内闭合「推理 ↔ 补采」循环。
- **第一版上限（已收敛）：** 最多 1 轮；每轮 2–3 个动作；只读；可阶段性收尾。
- **与「多轮」关系：** 「多轮」应明确写作 **Evidence Loop 的轮次**，默认上限 1，后续可扩展，不与 4.4 混淆。

### 4.3 深入分支（Deep Analysis Branches）

- **定义：** 常规对象/日志/拓扑/指标证据不足以解释时，可选进入的子路径（如代码路径、Operator 逻辑、专家排查路径）。
- **触发：** 条件式，非默认必经。
- **当前范围：** 规范层保留；MVP 运行时未实现自动触发。

### 4.4 编排模式（Orchestration Mode）— 预研焦点

- **定义：** 第 4 段推理**如何执行**——单 Agent 单遍 vs 多假设多轨并行。
- **用户设想对齐：** 多条假设各自成轨（pipeline），轨间通过**共享证据黑板**交换支持/反证/新 gap，避免单 Agent 早停于第一个 plausible 解释。

## Reframed Success Criteria（统一后如何算「做对」）

| # | 可测试条件 |
|---|-----------|
| SC-1 | 任意文档描述第 4 段时，不再混用「并行」；必须标明是 Portfolio / Loop / Branch / Orchestration 之一 |
| SC-2 | `triage-workflow.spec.md` §5 增加上述四层子结构（段名不变） |
| SC-3 | `agent-reasoning-task.md` 与 `midstack:analyse` 命令文案使用同一词汇表 |
| SC-4 | 预研产出：至少 2 种 Orchestration 候选方案，含成本、信息共享机制、与 Evidence Loop 的衔接 |
| SC-5 | 预研产出：明确当前实现与「Agent 主导补采闭环」的差距及是否纳入下一迭代 |

## Tech Stack（预研基线）

- 宿主：Cursor Agent + `midstack-local.py` analyse 链路
- 合同：`agent-reasoning-task.md` → `analysis.yaml` / `report.md`
- 参考：`references/orchestration-patterns.md`（Pattern 3 并行 fan-out；Agent Teams 竞争假设调试范例）
- 数据面：`structured_record` / `signal_bundle` / `collection_report` + 可选 `directed-recollection/`

## Commands

```bash
# 基线 replay（规则草稿 + 合同）
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py analyse \
  --input-dir tests/fixtures/mongodb/connection-failure-sample \
  --output-dir .local/incidents/phase4-spec-smoke

# 合同与结构校验
cd "/abs/path/to/midstack-triage" && python3 plugins/cursor/cli_smoke.py

# Review 过程偏差
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py review \
  --incident-dir .local/incidents/phase4-spec-smoke
```

## Project Structure（本预研触及范围）

```
docs/specs/triage-workflow.spec.md          → L1 第 4 段规范（术语统一目标）
docs/presentation.md                        → 对外叙事（§5.4 与段名对齐）
tools/plugin/midstack-local.py              → analyse 编排顺序、agent task 生成
plugins/cursor/commands/midstack:analyse.md → Agent 侧合同
references/orchestration-patterns.md        → 并行编排参考
docs/proposals/2026-06-12-phase4-reasoning-model/  → 本预研目录
```

## Orchestration 预研方案（待评审）

### 方案 A：单轨增强（基线，已接近现状）

```
证据包 → [规则补采] → 规则多假设草稿 → 单 Agent 全量推理 → analysis.yaml
```

- **信息共享：** 单上下文内天然共享。
- **优点：** 成本最低；与现有 finalize/review 完全兼容。
- **缺点：** 易「第一个 plausible 假设」锚定；无法真正并行探索互斥根因。

### 方案 B：Portfolio 内分轨 + 黑板合并（推荐作为第一版并行实验）

```
证据包 + rule-draft
    ├─ Track H1（子 Agent，只负责证伪/支持 H1）
    ├─ Track H2（子 Agent，只负责证伪/支持 H2）
    └─ Track H3（…）
         ↓ 写入共享 incident 内 reasoning-board.yaml（或 hypotheses 草稿分区）
    Lead Agent 合并 → analysis.yaml + report.md
```

- **信息共享：** 结构化黑板（建议新 artifact，不污染 `input.yaml`）：
  - `shared_findings[]`：带来源假设 id、证据引用、影响范围（support / refute / gap）
  - `cross_hypothesis_notes[]`：轨间显式反驳记录
- **与 Evidence Loop：** 各轨可提出 `validation_actions`；Lead 或 runner 统一门禁后执行**一轮**补采，再 fan-out 第二轮（仍受 1 轮上限约束）。
- **优点：** 对齐用户「并行 + 互补」设想；可比方案 A 做 A/B 案例回归。
- **缺点：** Token 成本上升；需定义合并冲突策略（两轨对同一证据相反解读）。

### 方案 C：对抗式竞争假设（Agent Teams 类，宿主受限）

- 多 investigator 互发 message，主动 disprove 彼此（见 `orchestration-patterns.md` 范例）。
- **优点：** 反锚定最强。
- **缺点：** Cursor 侧无 Agent Teams 等价物；成本高；难嵌入无人值守 `/midstack:analyse`。

### 预研建议优先级

1. **先统一术语（4.1–4.3 + 文档）** — 低成本，立即减少沟通损耗。
2. **用 fixture 做 A vs B 质量对比** — 选 2–3 个已有多假设案例（如 k8s-253、rs.status gap）。
3. **再决定是否调整 Evidence Loop 顺序** — Agent 前 vs 规则前补采，与 Orchestration 正交但应一并记录。

## Testing Strategy

- **术语统一：** 文档 grep 检查 + 人工 review（无自动化）。
- **Orchestration 预研：** 固定 fixture，对比单轨 vs 分轨的：
  - `hypothesis_coverage` / `validation_depth`（review 五维）
  - 过程偏差：`answer_led_bias`、`critical_gap_ignored`、`overconfident_conclusion`
  - 是否出现「互斥假设均被充分反驳/支持」的结构性改善
- **不新增** 仅为并行而并行的单元测试；以 golden-path replay + review 为主。

## Boundaries

- **Always：** 段名保持五段式；单次 analyse 对用户透明；只读补采白名单；结论 ceiling；来源边界。
- **Ask first：** 新增 artifact（如 `reasoning-board.yaml`）；L1 模板字段升级；多轮 Evidence Loop 上限 > 1；Deep Analysis Branch 自动化。
- **Never：** 并行轨各自写冲突的 `analysis.yaml` 终态；历史案例当现场证据；未门禁的任意 shell 补采。

## Open Questions

1. **Orchestration 第一版目标：** 仅文档统一，还是要在 Cursor 内落地方案 B 的最小实验？
2. **黑板形态：** 新 artifact vs 扩展 `analysis.rule-draft.yaml` 的 `hypotheses` 草稿区？
3. **Evidence Loop 顺序：** 是否将「Agent 识别 critical_gap → 补采 → 再推理」设为与规则预补采并存的第二阶段（仍共 1 轮上限）？
4. **深入分支：** 「深入验证」在段名中保留，但是否在规范里改名为「深入分支」以避免与 `validation_result` 混淆？
5. **Phase 5 拆分：** Agent task 是否拆成「4 推理」与「5 沉淀」两次调用，还是维持合并 task 仅在文档中逻辑分段？

## Success Criteria（本 Spec 完成标准）

- [ ] 本 spec 经人工 review 并确认 ASSUMPTIONS
- [ ] 选定 Orchestration 预研方案（A/B/C 或组合）
- [ ] `triage-workflow.spec.md` 术语统一 PR 范围确认
- [ ] 若有 B 方案实验：fixture 列表与对比指标签字
