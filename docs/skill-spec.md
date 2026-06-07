# Skill Spec

## 最小字段

每个技能资产目录至少包含：

- `metadata.yaml`
- `skill.md`

`metadata.yaml` 的最小字段集：

```yaml
id: string
title: string
middleware: string
component: string
primary_scenario: string
inputs:
  - string
outputs:
  - string
required_assets:
  - string
safety_constraints:
  - string
```

## 组织规则

- skill 是给 Agent 的工作流封装，不是 runbook 的复制版
- skill 可以引用 command 和 runbook，但不重复粘贴全部内容
- skill 应明确输入、输出和停止条件

## 模型

- [core/models/skill.schema.yaml](/home/stephen/AI/midstack-triage/core/models/skill.schema.yaml)
