---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Incident Record Spec

本文件用于确认单次排障记录的目录结构、核心文件职责和文件之间的关系，作为编码前的结构基线。

相关讨论见：

- [docs/DISCUSSIONS.md](../decisions/discussions-archive.md)
- [docs/PLUGIN_USAGE_SPEC.md](plugin-usage.spec.md)
- [docs/TRIAGE_WORKFLOW_SPEC.md](triage-workflow.spec.md)

## 1. 目录结构

当前建议采用“一次排障一个目录”的方式。

```text
incidents/
  <incident_id>/
    meta.yaml
    input.yaml
    structured_record.yaml
    signal_bundle.yaml
    collection_report.yaml
    analysis.yaml
    logs/
      raw/
      processed/
```

## 2. 文件职责总览

| 文件 | 主要职责 | 主要阶段 |
|---|---|---|
| `meta.yaml` | 记录级元信息、状态和导航入口 | 全流程 |
| `input.yaml` | 启动输入和原始故障线索 | 第 1 段 |
| `structured_record.yaml` | 对象、拓扑、状态、日志等结构化明细 | 第 2、3 段 |
| `signal_bundle.yaml` | 治理后的信号结果 | 第 3 段 |
| `collection_report.yaml` | 采集过程结果、失败、留白和证据缺口 | 第 3 段 |
| `analysis.yaml` | 假设、验证、结论、知识沉淀候选、review 结果 | 第 4、5 段 |

## 3. `meta.yaml`

### 目标

- 作为单次排障记录的总入口
- 保存状态、标识和导航信息
- 不承载分析内容

### 建议字段

- `incident_id`
- `middleware`
- `status`
- `created_at`
- `updated_at`
- `plugin_version`
- `current_command`
- `namespace`
- `cluster_id`
- `owner`

### 使用原则

- 只做总入口和导航
- 不放假设、结论、评分、原始线索和结构化明细

## 4. `input.yaml`

### 目标

- 保存启动输入
- 保存第一手原始故障线索
- 为第 1 段和第 2 段提供基础输入

### 建议字段

- `middleware`
- `k8s_access_ips`
- `username`
- `password`
- `port`
- `customer_clue`
- `clue_enrichment`
- `input_source`
- `received_at`

### 使用原则

- 前面阶段的基础输入默认冻结
- 如需修订，应记录修订动作，而不是静默覆盖原值

## 5. `structured_record.yaml`

### 目标

- 保存结构化对象、拓扑、状态和日志明细
- 作为第 2 段和第 3 段的核心明细文件

### 最小结构

- `summary`
- `details`
- `generated_at`

### 使用原则

- 人可读
- 脚本可处理
- 保留原始明细，不承担推理职责

## 6. `signal_bundle.yaml`

### 目标

- 保存信号治理后的结果
- 为第 4 段 Agent 提供最直接的推理输入

### 建议骨架

```yaml
signal_overview:
abnormal_signals:
object_signal_links:
timeline_summary:
processed_log_highlights:
generated_at:
updated_at:
```

### 使用原则

- 只放治理后的信号
- 不重复存放大段原始日志和大段对象明细

## 7. `collection_report.yaml`

### 目标

- 保存采集过程本身的结果和缺口
- 明确哪些证据成功拿到，哪些失败或留白

### 建议骨架

```yaml
collection_actions:
successful_items:
failed_items:
blank_items:
evidence_gaps:
generated_at:
updated_at:
```

### 使用原则

- 回答“采到了什么、没采到什么、为什么没采到”
- 避免第 4 段把“没看到”误判成“没有异常”

## 8. `analysis.yaml`

### 目标

- 承载第 4 段推理诊断结果
- 承载第 5 段阶段性结论
- 承载 `review` 反馈结果

### 建议骨架

```yaml
hypotheses:
validation_actions:
conclusion_summary:
knowledge_candidates:
review:
generated_at:
updated_at:
```

### 使用原则

- 假设、验证、结论、review 四类内容并存但不混写
- `review` 并入 `analysis.yaml`，不再单独使用 `review.yaml`

## 9. `logs/`

### 目标

- 保存原始日志与处理后日志文件
- 与 YAML 结构文件分离，避免大段日志撑爆结构化文件

### 子目录

- `logs/raw/`
  - 原始日志
- `logs/processed/`
  - 处理后日志

## 10. 文件之间的关系

### 从前到后的关系

1. `meta.yaml`
   - 定位当前记录和状态
2. `input.yaml`
   - 保存启动输入和原始线索
3. `structured_record.yaml`
   - 保存对象、拓扑、状态和日志明细
4. `signal_bundle.yaml`
   - 从明细中抽出治理后的信号
5. `collection_report.yaml`
   - 说明采集质量和证据缺口
6. `analysis.yaml`
   - 基于前面三类结果做推理、结论和 review

### 脚本与 Agent 的边界

- 脚本主要产出：
  - `structured_record.yaml`
  - `signal_bundle.yaml`
  - `collection_report.yaml`
- Agent 主要产出：
  - `analysis.yaml`

## 11. 当前结论

当前编码前已经可以明确以下结构基线：

- 一次排障一个目录
- 先使用 YAML + 日志目录跑通
- 不急于引入数据库
- `meta.yaml` 只做导航
- `input.yaml` 只做启动输入
- 第 3 段产出三类结构化结果
- 第 4、5 段及 `review` 结果统一落在 `analysis.yaml`
