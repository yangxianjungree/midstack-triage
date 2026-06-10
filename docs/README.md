---
status: authoritative
last_updated: 2026-06-10
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
| `specs/` | 规范（Reference） | 稳定的规范定义——**唯一事实源** |
| `guides/` | 操作指南（How-to）·规划中（二期） | 本地校验、远程 smoke、安装等操作步骤；当前散在 README 与 `tools/*/README.md`，待抽取 |
| `project/` | 项目管理 | 实施计划、TODO——时效性内容，允许滞后 |
| `analysis/` | 分析 | 领域对照等一次性分析快照 |
| `decisions/` | 历史决策/讨论 | 已归档的讨论稿——**冻结，非权威** |
| `references.md` | 外部参考 | 外部资料归档 |
| `presentation.md` | 汇报材料 | 面向干系人的汇报稿 |

## 权威分层（冲突时谁说了算）

文档之间出现冲突时，按下表从高到低裁决：

| 层级 | 位置 | 权威性 |
|------|------|--------|
| **L1 唯一事实源** | `docs/specs/` + `core/models/` schema | 最高；冲突一律以它为准 |
| **L2 概念解释** | `docs/concepts/`、`docs/analysis/` | 不得与 L1 矛盾，只讲「为什么」 |
| **L3 项目状态** | `docs/project/` | 时效性内容，允许滞后但须标 `last_updated` |
| **L4 历史档案** | `docs/decisions/` | 冻结，可能过时，**不作为依据** |

> 例外：`docs/concepts/architecture.md` 含三条基础结构约束（单一事实来源 / 不重复存放 / 不提前抽象），其约束效力等同 L1、高于普通 spec；若某 spec 与之冲突，以 architecture 为准。

## 文档状态头

每个文档顶部带 YAML front-matter，便于识别其权威性与时效：

```yaml
---
status: authoritative   # authoritative | draft | archived
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---
```

## 索引

### 概念（concepts/）

- [架构设计](concepts/architecture.md)
- [排障流程概览](concepts/triage-workflow.md)
- [信号治理模式](concepts/signal-governance.md)

### 规范（specs/，唯一事实源）

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
- [TODO](project/todo.md)

### 分析与参考

- [领域记录对照](analysis/domain-record-comparison.md)
- [外部参考资料](references.md)
- [汇报材料](presentation.md)

### 历史决策（decisions/，已归档·非权威）

- [排障流程讨论](decisions/triage-workflow-discussion.md)
- [讨论归档](decisions/discussions-archive.md)
