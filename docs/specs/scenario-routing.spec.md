---
status: draft
last_updated: 2026-06-12
supersedes: none
superseded_by: none
---

# Scenario Routing Spec

本文件定义从 `signal_bundle` 自动推断 `scenario` 的运行时合同。

## 1. 触发时机

- 在 `/midstack:analyse` 中，Phase 3 产出 `signal_bundle.yaml` 之后执行
- 在定向补采与 Phase 4 推理之前执行

## 2. 输入

- `signal_bundle.yaml`
- `structured_record.yaml`（可选，用于结构化路径加分）
- `input.yaml.customer_clue`（仅 tie-break，不作证据级路由）
- `input.yaml.middleware`

## 3. 输出

写入 `input.yaml`：

- `scenario`：最高分 scenario；无匹配时为 `unknown`
- `scenario_inference`：
  - `method`：当前为 `signal_bundle_rules_v1`
  - `confidence`：`high` | `medium` | `low`
  - `candidates`：按 score 降序的候选列表
  - `unresolved`：top1 与 top2 分差小于阈值时为 `true`
  - `matched_signals`：primary scenario 的匹配信号

## 4. 覆盖规则

仅在以下情况自动推断并覆盖 `scenario`：

- 当前 `scenario` 为 `unknown`、空或 `baseline`

显式指定的 scenario（fixture 或用户）保持不变。

## 5. 规则来源

- 路由表：`core/routing/scenario-signal-map.yaml`
- 实现：`tools/lib/scenario_router.py`

## 6. 与 skill 的关系

推断得到 `scenario` 后，运行时通过 `tools/lib/skill_resolver.py` 解析 `primary_scenario` 匹配的 skill，用于：

- 定向补采 script 白名单
- `agent-reasoning-task.md` 资产注入
- 知识沉淀候选匹配
