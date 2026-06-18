---
status: authoritative
last_updated: 2026-06-12
supersedes: none
superseded_by: none
---

# Skill Spec

## 最小字段

每个技能资产目录至少包含：

- `metadata.yaml`
- `skill.md`

`metadata.yaml` 的最小字段集（字段定义以 [core/models/skill.schema.yaml](../../core/models/skill.schema.yaml) 为准，本清单为摘要）：

```yaml
id: string
version: string
status: string  # 枚举见 core/taxonomies/status-types.yaml 的 asset_status
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
- 结构化引用：`type` + `id`，见[跨资产引用规范](asset-reference.spec.md)

当前治理试点要求 `domains/mongodb/skills/**/metadata.yaml` 必须声明 `version` 和 `status`。其他 asset family 后续按 proposal 分批推广。

## 组织规则

- skill 是给 Agent 的工作流封装，不是 runbook 的复制版
- skill 可以引用 command、runbook 和 script，但不重复粘贴全部内容
- skill 应明确输入、输出和停止条件
- 第 3 段 analyse 脚本通过 `type: script` 引用 `script_id`

## 运行时消费（混合模式 C）

skill 在运行时承担三层职责，但不替代 MVP 全量采集：

| 阶段 | skill 角色 |
|------|------------|
| Phase 3 MVP 采集 | 不参与；仍执行中间件 manifest 中的 MVP 脚本全集 |
| Scenario 推断后 | 按 `primary_scenario` 解析 matched skill |
| 定向补采 | `required_assets` 中 `type: script` 且 manifest `readonly: true` 的条目构成白名单；gap 触发器从中选取 |
| Phase 4 Agent | 读取 `skill.md` workflow、inputs、outputs、stop conditions |
| 知识沉淀 | scenario 已知后，按 skill/runbook/command metadata 生成候选 |

定向补采白名单解析见 `src/shared/skill_resolver.py`。Scenario 推断见 [scenario-routing.spec.md](scenario-routing.spec.md)。

## 模型

- [core/models/skill.schema.yaml](../../core/models/skill.schema.yaml)
- [core/models/asset-reference.schema.yaml](../../core/models/asset-reference.schema.yaml)
- [跨资产引用规范](asset-reference.spec.md)
