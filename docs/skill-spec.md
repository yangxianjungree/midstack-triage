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
  - type: string
    id: string
safety_constraints:
  - string
```

`required_assets` 支持：

- 路径字符串（过渡期）
- 结构化引用：`type` + `id`，见 [docs/ASSET_REFERENCE_SPEC.md](ASSET_REFERENCE_SPEC.md)

## 组织规则

- skill 是给 Agent 的工作流封装，不是 runbook 的复制版
- skill 可以引用 command、runbook 和 script，但不重复粘贴全部内容
- skill 应明确输入、输出和停止条件
- 第 3 段 analyse 脚本通过 `type: script` 引用 `script_id`

## 模型

- [core/models/skill.schema.yaml](../core/models/skill.schema.yaml)
- [core/models/asset-reference.schema.yaml](../core/models/asset-reference.schema.yaml)
- [docs/ASSET_REFERENCE_SPEC.md](ASSET_REFERENCE_SPEC.md)
