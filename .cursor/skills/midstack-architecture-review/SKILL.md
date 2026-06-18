---
name: midstack-architecture-review
description: >-
  Reviews midstack-triage repository structure, architecture proposals, and
  knowledge assets using dual-axis checks (structure compliance vs intent) and
  eight lenses, with confidence-scored findings. Use when reviewing project
  layout, PR/diff, docs/architecture.md, domain or scenario design,
  runbook/skill/command metadata, routing models, or when the user asks to
  检视/评审/审查架构 or structure. Invoke explicitly with
  /midstack-architecture-review when scope must be guaranteed.
---

# Midstack Architecture Review

从「值班能不能用、Agent 能不能跑通、专家愿不愿意贡献、规模涨 10 倍会不会崩」四个结果出发，检视本仓库或相关提案。

## 何时使用 / 何时不用

**使用：**

- 新增或修改 `domains/`、`scenarios/`、`core/`、`interfaces/` 结构
- 触及 `src/commands/`、`src/phases/`、`src/execution/`、`src/shared/` 的 runtime 边界
- 触及 Claude bundled runtime 或 Cursor workspace-local runtime 的安装态合同
- 评审架构提案、资产 metadata、路由模型
- PR 触及 runbook/skill/command 组织方式
- 验证新 domain 是否达到 MongoDB 样例同等完整度

**不用：**

- 纯文案润色、与结构无关的 runbook 步骤修订
- 单条命令内容对错（属领域专家审查，非架构检视）
- 尚未写进提案的空想扩展（无对象可检视）
- 紧急 hotfix 且仅改一行配置——除非用户明确要求

## 检视范围（先确认再开工）

| 范围 | 适用场景 |
|------|----------|
| 全仓结构 | 目录定稿、大重构 |
| 单个 `domain/` | 新中间件接入 |
| 单个 `scenario/` | 新故障现象定义 |
| 单条资产链路 | 验证 scenario → runbook → skill → command |
| PR / git diff | 增量变更是否破坏约定 |

用户未说明范围时，先问一句或根据 diff 推断，**不要默认全仓扫描**。

## 检视工作流（六步）

```text
1. 预检     → 范围是否过小/过大？对象是否存在？
2. 基准发现 → 按范围加载 README、architecture、spec、MongoDB 样例
3. 变更摘要 → 用 5–10 句话概括检视对象是什么、改动了什么
4. 双轴审查 → 结构合规 + 意图达成（见下），再过八维清单
5. 验证过滤 → 每条 finding 须有证据；低置信度进「需人工确认」
6. 输出报告 → 按 report-template；宁缺毋滥
```

基准发现规则：[references/guideline-discovery.md](references/guideline-discovery.md)  
置信度与误报过滤：[references/confidence-rubric.md](references/confidence-rubric.md)

## 双轴检视（不合并结论）

借鉴 code-review 的「标准 vs 需求」分离，架构检视分两轴，**报告里分开展示，不混排**：

| 轴 | 问什么 | 对照什么 |
|----|--------|----------|
| **结构合规** | 是否符合仓库既定结构与 spec？ | `docs/architecture.md`、各 `*-spec.md`、`domains/mongodb/` 样例 |
| **意图达成** | 是否实现提案/README 声称的目标？ | 用户提案、PR 描述、README 目标 |

示例：目录符合 architecture（结构合规 ✅），但提案要求「现象优先路由」而 metadata 未关联 scenario（意图达成 ❌）。

## 检视前准备

1. 读取检视对象：目录树、提案文档、PR diff、或具体资产（`metadata.yaml`、`scenario.yaml`、runbook/skill）。
2. 按 [guideline-discovery.md](references/guideline-discovery.md) 加载基准文档。
3. **样例优先级**：默认对照 `domains/mongodb/` 与 `scenarios/replica-inconsistency/`，不以未落地中间件为首选参照。

## 八维检视流程

按顺序过一遍，每项记录 **通过 / 风险 / 缺失**。细则见 [checklist.md](checklist.md)。

| # | 视角 | 核心问题 |
|---|------|----------|
| 1 | 值班 | 3 点故障时能否快速排除误报、分级止血、交接？ |
| 2 | Agent 运行时 | 能否完成「症状 → 路由 → 只读检查 → 证据 → 结论」闭环？ |
| 3 | 图谱模型 | 目录是视图还是主索引？跨资产链接是否靠稳定 ID？ |
| 4 | 重复风险 | `scenarios/`、`domains/`、runbook/skill/command 是否分工清晰？ |
| 5 | PaaS 约束 | 托管/自建、权限、观测入口、只读策略是否可表达？ |
| 6 | 命名纪律 | slug、taxonomy、metadata 是否同一套枚举？ |
| 7 | 反模式 | 是否触发已知烂法（见下方）？ |
| 8 | MVP 范围 | 是否可裁剪到一条 golden path 先跑通？ |

## 与本仓库原则的硬约束

检视时对照 [docs/architecture.md](../../../docs/concepts/architecture.md) 三条原则：

- **单一事实来源**：runbook 只在 `domains/<product>/runbooks/` 存一份
- **不重复存放**：顶层 `scenarios/` 不存产品专属命令/脚本/runbook
- **不提前抽象**：`core/shared/` 仅放跨 2+ 中间件且无产品语义的内容

### 当前 runtime 分层基准

```text
src/commands/   slash 命令、本地 CLI 和 adapter command 的正式编排入口
src/phases/     5 段 control plane；Phase 4 下 rules fallback 和 multitrack 并存
src/execution/  execution plane；远端接入、脚本投放、远程执行、结果回收
src/shared/     跨命令和跨阶段复用能力
plugins/claude/ Claude Code 插件源实现；安装后使用 bundled runtime
plugins/cursor/ Cursor command/rule projection；安装后使用 workspace-local runtime
tools/          薄入口、校验、回放、导入、生成和工程辅助工具
```

Phase 4 当前合同：

- `analysis.yaml` 生产者是 `src/phases/phase4/rules/<middleware>.py` rules fallback + guardrails。
- `src/phases/phase4/multitrack/` 写 `reasoning-board.yaml` 和 `analysis.multitrack.yaml`，不是生产 `analysis.yaml` 的唯一推理核。
- `agent-reasoning-task.md` 是人工或 Agent refinement 合同，不代表默认真实 Agent 自动闭环。

### 资产主从关系

```text
runbook  = 人类可读的真相源
command  = 单条命令片段，无控制流
script   = 可执行脚本，有控制流/聚合
skill    = Agent 编排层，引用 runbook/command/script，不复制步骤正文
```

### 场景与领域分工

| 位置 | 厚度 | 放什么 |
|------|------|--------|
| `scenarios/<phenomenon>/` | 薄 (~10%) | 现象定义、信号、路由提示 |
| `domains/<mw>/runbooks/` | 厚 (~60%) | 完整排查手册 |
| `domains/<mw>/commands|scripts|skills/` | 中 | 可执行片段与编排 |

## 七条反模式（命中即标红）

1. 先写 Markdown，后补 `metadata.yaml`
2. 各中间件目录结构或字段不一致
3. 顶层 `scenarios/` 写成完整大手册（应 < 1 页）
4. `interfaces/` 或插件适配器内复制第二份知识
5. skill 与 runbook 各写一套完整流程
6. `core/shared/` 出现产品专属工具或语义（如 `redis-cli`、`ISR`）
7. 无 golden path 测试覆盖关键路由

## 输出要求

使用 [report-template.md](report-template.md) 输出报告。

### 严重级别（对齐代码审查 P0/P1/P2）

| 级别 | 代号 | 含义 |
|------|------|------|
| 阻塞 | P0 | 违反 architecture/spec 或样例契约；不修不能合并 |
| 风险 | P1 | 3 个月内可能导致重复、路由失败、Agent 无法闭环 |
| 建议 | P2 | 体验与 contributor 成本优化 |
| 亮点 | — | 值得保留或推广的做法（可选，鼓励沉淀） |

### 每条 finding 格式

```markdown
- **级别**：P0 / P1 / P2
- **轴**：结构合规 / 意图达成
- **位置**：文件路径或资产 id
- **依据**：引用的 spec 条款、字段或样例差异
- **问题**：一句话说明
- **建议**：可操作的修复方向
- **置信度**：0–100（< 80 不进正式 findings，见 confidence-rubric）
```

### 审查原则（借鉴 code-review skill）

1. **证据先行**：必须引用路径、metadata 字段或 spec，禁止空泛「可能会乱」
2. **附带建议**：每个 P0/P1 都要有修复方向，不只批评
3. **宁缺毋滥**：置信度 < 80 不当作定论；不确定标「需人工确认」
4. **分轴呈现**：`## 结构合规` 与 `## 意图达成` 分开，不合并排序

报告还需包含：**总判断**、**保留·延后·砍掉** 表、**建议下一步**（最多 3 条）。

## v0 成功标准（检视新 domain/scenario 时必查）

以 README 定义的首个样例链路为基准。新 domain 应先证明能达到与 MongoDB 样例同等的完整度，再扩展其他中间件。

至少满足：

1. 输入典型症状（如「副本成员状态异常 / 复制滞后」），能路由到 `scenarios/replica-inconsistency` → `domains/mongodb`
2. 能加载 1 runbook + 若干 command/script（参照 `replica-member-not-healthy` 链路）
3. 执行策略默认只读
4. 输出结构化结论（含证据引用），非自由发挥
5. 有 1 条 golden path 可验证

## 参考样例（MongoDB 首选）

检视单条链路时，**优先**对照仓库内已落地的 MongoDB 范例，而非假设中的 Kafka/Redis 链路：

```text
scenarios/replica-inconsistency/scenario.yaml
  → domains/mongodb/runbooks/replica-set/replica-member-not-healthy/
  → domains/mongodb/skills/replica-set/triage-replica-member-not-healthy/
  → domains/mongodb/commands/replica-set/check-rs-status/
```

检视新问题域时，问：

- 新 domain 的目录深度、metadata 字段、资产分层是否与 `domains/mongodb/` 一致？
- 新 scenario 的厚度是否与 `scenarios/replica-inconsistency/` 一致（薄定义、不存产品实现）？
- skill 是否引用 runbook 而非复制？ID 与 `scenario` 关联是否正确？

## 附加资源

- 完整检查项：[checklist.md](checklist.md)
- 报告模板：[report-template.md](report-template.md)
- 基准发现：[references/guideline-discovery.md](references/guideline-discovery.md)
- 置信度与误报：[references/confidence-rubric.md](references/confidence-rubric.md)
