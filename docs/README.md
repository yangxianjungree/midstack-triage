---
status: authoritative
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# 文档地图

本目录按「读者需求 / 内容类型」组织，参考 Diátaxis、Kubernetes 与 MongoDB 文档结构。
核心原则：**规范、解释、操作指南、项目管理、历史决策彻底分开**，避免把临时讨论当成现状读。

## 目录结构

| 目录 | 内容类型 | 放什么 |
|------|----------|--------|
| `concepts/` | 解释（Explanation） | 架构、流程概览、设计模式——讲「为什么这么设计」 |
| `specs/` | 规范（Reference） | 稳定的规范定义——与 `core/`（models/templates/taxonomies）共同构成 **L1 唯一事实源** |
| `guides/` | 操作指南（How-to） | 新增中间件、安装、校验等任务导向步骤 |
| `proposals/` | 变更提案 | 新需求、破坏性调整、跨文档结构变更的定稿前讨论稿 |
| `project/` | 项目管理 | 实施计划、TODO——时效性内容，允许滞后 |
| `analysis/` | 分析 | 领域对照等一次性分析快照 |
| `decisions/` | 历史决策/讨论 | 已归档的讨论稿——**冻结，非权威** |
| `references.md` | 外部参考 | 外部资料归档 |
| `presentation.md` | 汇报材料 | 面向干系人的汇报稿 |

## 权威分层（冲突时谁说了算）

文档之间出现冲突时，按下表从高到低裁决：

| 层级 | 位置 | 权威性 |
|------|------|--------|
| **L1 唯一事实源** | `docs/specs/` + `core/models/` schema + `core/templates/` + `core/taxonomies/` | 最高；冲突一律以它为准 |
| **L2 概念解释** | `docs/concepts/`、`docs/analysis/` | 不得与 L1 矛盾，只讲「为什么」 |
| **L3 项目状态** | `docs/project/` | 时效性内容，允许滞后但须标 `last_updated` |
| **L4 历史档案** | `docs/decisions/` | 冻结，可能过时，**不作为依据** |

根 `README.md` 是仓库门户：其架构、流程、快速体验与当前落地情况是 L1/L3 的**摘要**，与 L1 冲突时以 L1 为准。

### L1 内部分工（L1 之间冲突时谁说了算）

| 内容 | 唯一事实源 | 其他文档允许的形式 |
|------|-----------|--------------------|
| 三条基础结构约束（单一事实来源 / 不重复存放 / 不提前抽象） | [架构设计](concepts/architecture.md)「目标」节 | 引用；任何 spec 与之冲突时以它为准 |
| 字段名、结构、嵌套位置 | `core/models/` schema + `core/templates/` | 引用或摘抄子集，并标注「以 X 为准」 |
| 枚举值（状态、风险、候选类型等） | `core/taxonomies/` | 引用，不内联复述 |
| 命令行为、状态机、目标记录选择、运行时合同 | [插件运行时规范](specs/plugin-runtime.spec.md) | 引用，不另行定义 |
| incident 目录结构与文件职责 | [单次排障记录规范](specs/incident-record.spec.md) | 引用，不另行定义 |
| 排障主流程与各段语义 | [排障流程规范](specs/triage-workflow.spec.md) | 引用或概览 |

> 说明：`architecture.md` 仅其三条结构约束按上表参与 L1 裁决；该文件其余内容（设计动机、职责边界解释）仍属 L2，不得与 L1 矛盾。

字段修订纪律：**新增或修改字段时，先改 schema/模板/taxonomy，spec 只更新引用**；spec 中出现的任何字段清单都是下游摘要，不是平行定义。

## 变更流程（接入新需求时怎么改）

所有较大需求先判断是否影响 L1。若影响字段、状态机、命令行为、incident 结构、跨资产引用、目录边界或兼容性，先写入 [变更提案](proposals/README.md)，定稿后再修改 L1。

标准流程：

1. 先确定变更类型和唯一事实源，不直接改多个文档。
2. 如需讨论，在 `docs/proposals/` 新建提案；提案状态保持 `draft`。
3. 定稿后先修改 L1 事实源：`core/models/`、`core/templates/`、`core/taxonomies/` 或 `docs/specs/`。
4. 再更新引用方：README、concepts、project、领域 README、插件适配器文档只写摘要和链接。
5. 同步更新样例、fixture、validator、生成器或导入器说明，避免文档合同和校验入口分离。
6. 已实现、已验证、未实现等状态只写入 [实现进展](project/implementation-status.md) 或 [TODO](project/todo.md)，不写入 L1 规范。
7. 已被采纳或废弃的提案，迁移结论到 L1 或 L3，并把讨论背景归档到 `docs/decisions/`。

变更类型与入口：

| 变更类型 | 先改哪里 | 后续同步 |
|----------|----------|----------|
| 新字段、字段改名、嵌套结构调整 | `core/models/` 或 `core/templates/` | 对应 spec 摘要、示例、validator |
| 新枚举值、状态、风险等级、候选类型 | `core/taxonomies/` | spec 引用、validator、样例 |
| 插件命令、状态机、目标记录选择、运行时合同 | [插件运行时规范](specs/plugin-runtime.spec.md) | 插件使用规范、接口样例、适配器文档 |
| incident 文件、目录、文件职责 | [单次排障记录规范](specs/incident-record.spec.md) | 模板、analyse/review 规范、fixture |
| 新中间件 | `domains/<product>/` + 必要的 `core/` 扩展 | 场景引用、资产 metadata、脚本 manifest |
| 新故障场景 | `scenarios/<slug>/scenario.yaml` | 对应领域 runbook、command、skill、script 引用 |
| 新适配器 | `core/interfaces/` 或 `plugins/<agent>/` | 插件运行时规范、安装/测试说明 |
| 实现进展或验证状态 | `docs/project/implementation-status.md` | README 只保留状态摘要链接 |

破坏性变更要求：

- 修改 schema/template/taxonomy 的兼容性时，必须说明是否兼容旧资产。
- 不兼容时优先升级 `schema_id` 或 taxonomy 版本，并补迁移说明。
- 删除字段、改枚举值、改变命令状态语义、改变 incident 文件落点，都必须经过 proposal。
- 不允许只改实现或样例，不更新对应 L1 事实源。

## 文档状态头

每个文档顶部带 YAML front-matter，便于识别其权威性与时效：

```yaml
---
status: authoritative   # authoritative | stable | draft | archived
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---
```

`status` 取值与权威分层对应：

- `authoritative`：仅用于 L1（`docs/specs/`）和本文档地图（裁决规则本身）——冲突裁决依据
- `stable`：内容已收敛但不作裁决依据，用于 L2 解释类文档
- `draft`：内容未收敛，用于 L3 及其他在途文档
- `archived`：冻结归档，用于 L4

## 索引

### 概念（concepts/）

- [架构设计](concepts/architecture.md)
- [Midstack 架构图](concepts/architecture-overview.md)（主图 + ④ 展开）
- [排障流程概览](concepts/triage-workflow.md)
- [信号治理模式](concepts/signal-governance.md)

### 规范（specs/，唯一事实源）

- [核心规范英文索引](specs/README.en.md)
- [排障流程规范](specs/triage-workflow.spec.md)
- [插件使用规范](specs/plugin-usage.spec.md)
- [插件运行时规范](specs/plugin-runtime.spec.md)
- [Analyse MVP 规范](specs/analyse-mvp.spec.md)
- [单次排障记录规范](specs/incident-record.spec.md)
- [增量合并规范](specs/incident-patch-merge.spec.md)
- [跨资产引用规范](specs/asset-reference.spec.md)
- [Runbook 规范](specs/runbook.spec.md)
- [Command 规范](specs/command.spec.md)
- [Skill 规范](specs/skill.spec.md)

### 项目管理（project/）

- [实施计划](project/implementation-plan.md)
- [实现进展](project/implementation-status.md)
- [测试与安装门禁](project/testing-and-install-gates.md)
- [TODO](project/todo.md)
- [Phase 4 集成说明](project/phase4-multitrack-integration.md)
- [Phase 4 Agent 驱动推理流程](project/phase4-agent-driven-reasoning.md)

### 操作指南（guides/）

- [新增中间件 domain](guides/add-domain.md)

### 变更提案（proposals/）

- [变更提案入口](proposals/README.md)

### 分析与参考

- [领域记录对照](analysis/domain-record-comparison.md)
- [rs.status 采集缺口分析](analysis/rs-status-collection-gap.md)
- [外部参考资料](references.md)
- [汇报材料](presentation.md)

### 历史决策（decisions/，已归档·非权威）

- [排障流程讨论](decisions/triage-workflow-discussion.md)
- [旧根 README 归档](decisions/legacy-readme-2026-06-16.md)
- [讨论归档](decisions/discussions-archive.md)
