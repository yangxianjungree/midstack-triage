# Asset Reference Spec

本文件定义跨资产引用协议，用于连接 `scenarios/`、`runbooks/`、`commands/`、`skills/` 与 `scripts/`。

相关文档：

- [docs/architecture.md](architecture.md)
- [docs/TRIAGE_WORKFLOW_SPEC.md](TRIAGE_WORKFLOW_SPEC.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](PLUGIN_RUNTIME_SPEC.md)
- [core/models/asset-reference.schema.yaml](../core/models/asset-reference.schema.yaml)

## 1. 目标

- 用稳定 `id` 引用资产，目录移动不破坏链接
- 统一 skill、runbook、analyse 编排、golden path 的引用格式
- 兼容过渡期内的路径字符串引用

## 2. 引用格式

### 2.1 结构化引用（推荐）

```yaml
- type: scenario
  id: replica-inconsistency

- type: runbook
  id: mongodb-replica-member-not-healthy

- type: command
  id: mongodb-check-rs-status

- type: skill
  id: mongodb-triage-replica-member-not-healthy

- type: script
  id: mongodb.collect.pods.state
```

### 2.2 路径引用（过渡期兼容）

```yaml
- domains/mongodb/runbooks/replica-set/replica-member-not-healthy
```

规则：

- 新资产优先使用结构化引用
- 路径引用只作人类可读补充或历史兼容，不作为主键
- validator 对两种格式都应校验目标存在

## 3. 各 `type` 的解析规则

| type | 主键来源 | 解析方式 |
|------|----------|----------|
| `scenario` | `scenarios/<slug>/scenario.yaml` 的 `id` | 文件名与 `id` 应一致 |
| `runbook` | `metadata.yaml` 的 `id` | 在 `domains/<mw>/runbooks/**/metadata.yaml` 中查找 |
| `command` | `metadata.yaml` 的 `id` | 在 `domains/<mw>/commands/**/metadata.yaml` 中查找 |
| `skill` | `metadata.yaml` 的 `id` | 在 `domains/<mw>/skills/**/metadata.yaml` 中查找 |
| `script` | `manifest.yaml` 的 `script_id` | 在 `domains/<mw>/scripts/manifest.yaml` 中查找 |

## 4. 字段落点

### 4.1 `skill.metadata.yaml`

```yaml
required_assets:
  - type: scenario
    id: replica-inconsistency
  - type: runbook
    id: mongodb-replica-member-not-healthy
  - type: command
    id: mongodb-check-rs-status
  - type: script
    id: mongodb.collect.pods.state
  - type: script
    id: mongodb.collect.replicaset.rs_status
```

原则：

- skill 编排引用，不复制 runbook 正文
- 第 3 段脚本通过 `type: script` 接入 analyse 主路径

### 4.2 `runbook.metadata.yaml`（可选扩展）

```yaml
workflow_phases:
  - 3
  - 4
related_scripts:
  - mongodb.collect.pods.state
  - mongodb.collect.replicaset.rs_status
related_skills:
  - mongodb-triage-replica-member-not-healthy
```

### 4.3 golden path / analyse 编排

golden path 和插件编排应使用与 skill 相同的 `type + id` 格式，避免第三套引用语法。

## 5. 与 5 段主流程的映射

| 主流程段 | 典型资产 |
|----------|----------|
| 1-2 受理与环境确认 | `input.yaml`、`structured_record` |
| 3 信号采集与治理 | `type: script` |
| 4 推理诊断与验证 | `type: skill`、`type: command`、`type: runbook` |
| 5 结论与沉淀 | `analysis.yaml`、`type: scenario`（回灌标签） |

## 6. 校验

运行：

```bash
python3 tools/validators/validate-mongodb-scripts.py
python3 tools/validators/validate-golden-paths.py
python3 tools/validators/validate-repo.py --skip-replay --skip-score --skip-cursor
```

## 7. 迁移策略

1. 新 skill 只使用结构化引用
2. 现有 skill 在改动时逐步迁移
3. `tools/generators/generate-asset.py` 后续默认生成结构化引用
4. 当全部 MongoDB skill 迁移完成后，再评估是否废弃路径引用
