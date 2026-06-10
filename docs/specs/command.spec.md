---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Command Spec

## 最小字段

每个命令资产目录至少包含：

- `metadata.yaml`
- `command.md`

`metadata.yaml` 的最小字段集（字段定义以 [core/models/command.schema.yaml](../../core/models/command.schema.yaml) 为准，本清单为摘要）：

```yaml
id: string
title: string
middleware: string
component: string
scenario: string
risk_level: string  # 枚举见 core/taxonomies/risk-levels.yaml
tags:
  - string
required_tools:
  - string
expected_signal:
  - string
```

## 组织规则

- 命令资产按产品归档在 `domains/<product>/commands/`
- 命令只描述一组清晰目的的检查动作
- 高风险命令不能与只读命令混写在同一资产中

## 模型

- [core/models/command.schema.yaml](../../core/models/command.schema.yaml)
