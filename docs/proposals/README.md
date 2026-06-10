---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 变更提案

本目录用于承载尚未进入 L1 规范的新需求、破坏性调整和跨文档结构变更。提案不是事实源；只有合入 `docs/specs/`、`core/models/`、`core/templates/` 或 `core/taxonomies/` 后，结论才成为规范。

## 什么时候需要提案

以下变更必须先写提案：

- 新增或修改 incident 文件、目录结构、文件职责
- 新增插件命令、改变状态机、改变默认目标记录选择规则
- 新增或修改 schema/template/taxonomy，且可能影响已有资产
- 新增中间件、新适配器或跨中间件通用能力
- 删除字段、重命名字段、改变枚举语义、改变命令输出状态
- 把某个领域经验提升为 `core/` 共性能力

以下变更通常不需要提案：

- 修正文档错别字、链接、标题或过期路径
- 给既有规范补充更清晰的引用，不改变语义
- 新增一个完全符合既有规范的 runbook、command、skill 或场景资产
- 在 `docs/project/implementation-status.md` 更新实现进展

## 提案最小结构

每个提案建议使用一个 Markdown 文件，文件名使用短横线命名，例如：

```text
docs/proposals/add-redis-domain.md
docs/proposals/change-incident-record-v2.md
```

提案内容至少包括：

```markdown
---
status: draft
last_updated: YYYY-MM-DD
supersedes: none
superseded_by: none
---

# <proposal title>

## 背景

说明为什么需要这个变更。

## 变更类型

说明影响的是字段、枚举、命令行为、incident 结构、新中间件、新场景、新适配器，或其他类型。

## 影响范围

列出需要修改的事实源、引用文档、样例、validator、生成器或适配器文档。

## 兼容性

说明是否兼容旧资产；不兼容时说明迁移方式和版本策略。

## 决策

记录采纳、推迟或废弃的结论。

## 落地清单

- 更新 L1 事实源
- 更新引用文档
- 更新样例和校验
- 更新实现进展或 TODO
```

## 落地规则

- 提案定稿后，先修改 L1 事实源，再修改 README、concepts、project 或领域 README。
- 字段和结构变更先改 `core/models/` 或 `core/templates/`。
- 枚举变更先改 `core/taxonomies/`。
- 命令行为、状态机和运行时合同先改 `docs/specs/plugin-runtime.spec.md`。
- incident 目录结构和文件职责先改 `docs/specs/incident-record.spec.md`。
- 实现状态只写入 `docs/project/implementation-status.md` 或 `docs/project/todo.md`。
- 提案采纳或废弃后，应把最终结论同步到事实源；保留背景时再归档到 `docs/decisions/`。
