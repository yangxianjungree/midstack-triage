---
status: authoritative
last_updated: 2026-06-20
supersedes: none
superseded_by: none
---

# Incident Record Spec

本文件用于确认单次排障记录的目录结构、核心文件职责和文件之间的关系，作为编码前的结构基线。

相关讨论见：

- [讨论归档](../decisions/discussions-archive.md)
- [插件使用规范](plugin-usage.spec.md)
- [排障流程规范](triage-workflow.spec.md)

> 本文件是 incident 目录结构与核心文件职责的唯一权威定义。已有对应模板的文件（当前为 `analysis.yaml`，见 [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml)）字段结构以模板为准；其余文件（`meta.yaml`、`input.yaml`、`structured_record.yaml`、`signal_bundle.yaml`、`collection_report.yaml`、`report.md`）暂以本规范的骨架为事实源，模板补齐后迁移。

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
    analysis.rules-fallback.yaml
    analysis.multitrack.yaml
    reasoning-manifest.yaml
    reasoning/
      0001-rules-fallback.yaml
      0002-agent-refinement.yaml
    report.md
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
| `reasoning-manifest.yaml` | append-only 推理历史索引、当前 head、共享/隔离模型 | 第 4、5 段 |
| `reasoning/*.yaml` | 单轮推理 segment；保存当轮分析快照、假设验证记录和证据引用 | 第 4、5 段 |
| `report.md` | 面向用户的可读排障报告，由 `analyse` 基于 `analysis.yaml` 生成 | 第 5 段 |

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

字段结构以 [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml) 为准：

```yaml
hypotheses:
conclusion_summary:
next_actions:
verification_requests:
reasoning_timeline:
deepening_findings:
knowledge_candidates:
retrieval_context:
experience_matches:
source_boundaries:
review:
generated_at:
updated_at:
```

### 使用原则

- 假设、结论、知识沉淀、review 四类内容并存但不混写
- 验证动作（`validation_actions`）嵌套在各假设内，挂回对应假设，不设顶层列表
- `verification_requests` 是 Phase 4 产出的待验证请求队列，不表示已经执行；仓库内只读脚本/命令是一等资产，可标记为 `auto_allowed`，临时只读命令必须先经过 guardrail，破坏性动作必须 `blocked`
- `report.md` 应展示关键 `verification_requests`，让用户能区分一等只读资产、二等临时只读请求和 blocked 动作；展示不代表已经执行
- `reasoning_timeline` 汇总当前证据中的关键时间顺序，用于报告可信度和假设关联；时间线本身不单独证明因果
- `deepening_findings` 记录领域不变量冲突、反证和机制深化观察；它必须引用当前证据，不得引入未采集事实
- `retrieval_context` 只作为未来历史经验/向量召回的查询上下文，不表达当前结论
- `experience_matches` 在未接入真实召回前必须保持空列表；接入后也只能作为假设或验证路径来源
- `source_boundaries` 明确当前故障证据与假设来源的边界；历史经验、runbook 和用户线索不得直接作为 `conclusion_summary` 的支撑证据
- `review` 并入 `analysis.yaml`，不再单独使用 `review.yaml`

## 9. `reasoning-manifest.yaml` 和 `reasoning/`

### 目标

- 保存第 4、5 段推理过程的 append-only 历史
- 让 `analysis.yaml` 和 `report.md` 继续作为“最新物化视图”，同时保留每轮推理为什么变化
- 明确多假设验证过程的共享输入和隔离输出边界

### 最小结构

```yaml
schema_version: reasoning-history.v1
current_head: reasoning/0002-agent-refinement.yaml
materialized_outputs:
  analysis: analysis.yaml
  report: report.md
shared_evidence_pool:
  access: read_only
  refs:
    - path: input.yaml
      access: read_only
      status: present
isolation_model:
  shared_readonly_refs:
    - input.yaml
    - structured_record.yaml
    - signal_bundle.yaml
    - collection_report.yaml
  isolated_validation_prefix: reasoning/*.yaml#hypothesis_validations
segments:
  - segment_id: 0001-rules-fallback
    path: reasoning/0001-rules-fallback.yaml
    source: rules_fallback
    analysis_sha256: ...
```

每个 `reasoning/*.yaml` segment 至少包含：

```yaml
schema_version: reasoning-segment.v1
segment_id: 0002-agent-refinement
source: agent_refinement
shared_evidence_pool:
  access: read_only
hypothesis_validations:
  - hypothesis_id: H1
    isolation:
      scope: hypothesis_validation
      shared_read_refs:
        - signal_bundle.yaml
      private_write_ref: reasoning/0002-agent-refinement.yaml#hypothesis_validations[H1]
analysis_snapshot:
```

### 使用原则

- `reasoning/*.yaml` 是 append-only 历史段；已存在的段不得被后续推理静默改写。
- `reasoning-manifest.yaml` 是可变索引；它可以更新 `current_head`，但不得伪造或删除已有 segment。
- `analysis.yaml` 和 `report.md` 是最新物化视图；允许被 Agent/finalize 刷新，但对应变化必须追加新的 reasoning segment。
- `shared_evidence_pool` 中的 incident 证据对所有 hypothesis validation 只读共享。
- 每个 hypothesis validation 只能写自己的 `private_write_ref`，不能覆盖其他 hypothesis 的验证记录。
- 一个 hypothesis 的反证、证据缺口和验证动作必须挂回该 hypothesis；如果需要影响总体结论，通过新的 segment 发布，而不是直接改写旧段。

## 10. `logs/`

### 目标

- 保存原始日志与处理后日志文件
- 与 YAML 结构文件分离，避免大段日志撑爆结构化文件

### 子目录

- `logs/raw/`
  - 原始日志
  - 手工粘贴的命令输出或截图文字应先作为原始证据保存，例如 `logs/raw/manual-evidence.txt`
- `logs/processed/`
  - 处理后日志

手工粘贴内容在未经治理前不得直接伪装成 `structured_record.yaml`、`signal_bundle.yaml` 或 `collection_report.yaml`。

## 11. 文件之间的关系

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
7. `reasoning-manifest.yaml` / `reasoning/`
   - 记录 `analysis.yaml` 与 `report.md` 每次物化变化背后的推理历史
8. `report.md`
   - 基于 `analysis.yaml` 生成面向用户的可读报告

### 脚本与 Agent 的边界

- 脚本主要产出：
  - `structured_record.yaml`
  - `signal_bundle.yaml`
  - `collection_report.yaml`
- Agent 主要产出：
  - `analysis.yaml`
  - `report.md`
  - `reasoning/*.yaml` 的追加段

## 12. 当前结论

当前编码前已经可以明确以下结构基线：

- 一次排障一个目录
- 先使用 YAML + 日志目录跑通
- 不急于引入数据库
- `meta.yaml` 只做导航
- `input.yaml` 只做启动输入
- 第 3 段产出三类结构化结果
- 第 4、5 段及 `review` 结果统一落在 `analysis.yaml`
