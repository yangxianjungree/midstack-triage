# Runbook Spec

## 最小字段

每个 runbook 目录至少包含：

- `metadata.yaml`
- `runbook.md`

`metadata.yaml` 的最小字段集：

```yaml
id: string
title: string
middleware: string
component: string
scenario: string
summary: string
risk_level: read-only | low-risk | high-risk
tags:
  - string
required_tools:
  - string
applicable_env:
  - string
verification_steps:
  - string
rollback_or_safety_notes:
  - string
```

## 组织规则

- runbook 物理上按组件存储
- runbook 逻辑上按场景检索
- 一个 runbook 只对应一个主场景
- 如果一个 runbook 覆盖多个相关症状，其他症状通过标签表达，不复制第二份 runbook

## 模型

- [core/models/runbook.schema.yaml](/home/stephen/AI/midstack-triage/core/models/runbook.schema.yaml)
