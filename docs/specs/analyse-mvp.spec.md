---
status: authoritative
last_updated: 2026-06-14
supersedes: none
superseded_by: none
---

# Analyse MVP Spec

本文件定义第一版 `/<plugin_name>:analyse` 的能力边界。

目标是明确第一版 analyse 做什么、不做什么，以及执行完成后应产出哪些结构化结果。

相关文档：

- [插件使用规范](plugin-usage.spec.md)
- [排障流程规范](triage-workflow.spec.md)
- [插件运行时规范](plugin-runtime.spec.md)
- [单次排障记录规范](incident-record.spec.md)
- [实施计划](../project/implementation-plan.md)

## 1. 定位

`analyse` 是第一版正式分析入口。

它负责在 `/start` 已完成受理、环境确认和对象盘点基础上，继续执行第 3、4、5 段：

1. 第 3 段：信号采集与治理
2. 第 4 段：推理诊断与深入验证
3. 第 5 段：结论整合与知识沉淀

第一版 `analyse` 执行完成后，用户应直接看到阶段性结论和报告，不需要再执行 `/review` 才能得到排障结果。

`review` 只用于插件效果评分和优化反馈，不属于用户排障主路径。

### 运行时入口说明

第一版 `analyse` 的 incident 合同、采集合同和推理合同在不同适配器之间保持一致；当前差异只在运行时分发方式：

- Claude 适配器从安装后的 bundled runtime 进入 `src/commands/analyse.py`
- Cursor 适配器从 workspace-local runtime 的 `.cursor/midstack-triage-runtime/bin/midstack-local.py` 进入同一套 bundled `src/commands/analyse.py`

两种入口最终都复用：

- `src/commands/analyse.py`
- `src/phases/phase3/incident_build.py`
- `src/phases/phase3/remote_collection.py`
- `src/phases/phase3/remote_run.py`
- `src/phases/phase3/recollection.py`
- `src/phases/phase3/recollection_run.py`
- `src/phases/phase3/report_gaps.py`
- `src/phases/phase3/scenario_routing.py`
- `src/phases/phase3/skill_runtime.py`
- `src/phases/phase4/reasoning.py`
- `src/phases/phase5/finalize.py`
- `src/execution/remote/executor.py`

## 2. 前置条件

第一版 `analyse` 的前置条件：

- 当前会话存在目标 incident
- 若用户未指定 `incident_id`，默认使用会话级当前目标记录（唯一定义见[插件运行时规范](plugin-runtime.spec.md) §4）
- incident 状态为 `ready`，或为 `analysed`（基于已有记录继续分析，见[插件运行时规范](plugin-runtime.spec.md) §7）
- 已提供中间件类型
- 已验证远程环境信息
- 已验证基础 Kubernetes 操作
- 如已提供客户线索，已确认其可以被理解

如果前置条件不满足，`analyse` 不应继续执行采集和推理，应返回 `adapter output`：

- `status: blocked`
- `blocking_items` 中说明缺少什么
- `next_actions` 中说明用户或运行时应如何修正

## 3. 第一版支持范围

第一版正式支持：

- Middleware: `mongodb`
- Topology: 优先支持 Kubernetes 中的 MongoDB 分片集群
- Deployment architecture:
  - Bitnami 风格部署
  - operator+CRD：认证读取通过 `secret_ref` 纳入第一版范围（见[插件运行时规范](plugin-runtime.spec.md) §10）；拓扑识别等完整适配后续实现
- 执行方式：
  - 通过 `remote executor` 进入用户提供的远程 K8s 环境
  - 通过 `kubectl` 和 `kubectl exec` 执行采集
  - MongoDB 客户端工具默认在 Pod 内执行

当前正式远程执行入口位于 `src/execution/remote/executor.py`。

第一版 MongoDB 第 3 段执行范围固定为 11 个 MVP 脚本：

1. `mongodb.collect.pods.state`
2. `mongodb.collect.statefulsets.yaml`
3. `mongodb.collect.services.yaml`
4. `mongodb.collect.nodes.state`
5. `mongodb.collect.events.yaml`
6. `mongodb.collect.mongos.get_shard_map`
7. `mongodb.collect.replicaset.rs_status`
8. `mongodb.collect.logs.current`
9. `mongodb.collect.logs.previous`
10. `mongodb.normalize.logs.highlights`
11. `mongodb.normalize.signals.bundle`

## 4. 输入

`analyse` 的输入来自已冻结的 incident 记录。

主要输入文件：

- `meta.yaml`
- `input.yaml`
- `/start` 阶段已确认的环境信息
- `/start` 阶段已确认的目标中间件信息
- 客户提供的原始线索和富化结果

第一版 `analyse` 不应静默修改 `/start` 阶段的基础输入。

如果必须修正基础输入，应阻塞并要求用户重新确认，而不是在 `analyse` 中自动覆盖。

## 5. 第 3 段输出

第 3 段由脚本和 remote executor 主导。

当前正式实现边界：

- control plane 编排位于 `src/commands/` 与 `src/phases/`
- execution plane 远程执行位于 `src/execution/remote/`
- `tools/plugin/midstack-local.py` 只保留本地 CLI 适配职责

脚本输出采用统一合同：

```text
<script> --context-file <path> --output-file <path> --artifact-dir <path>
```

每个脚本写出自己的 `output-file`，由插件运行时合并到 incident 记录。

第一版第 3 段最终至少产出：

- `structured_record.yaml`
- `signal_bundle.yaml`
- `collection_report.yaml`

其中：

- `structured_record.yaml`
  - 保存 Kubernetes 对象、MongoDB topology、成员状态、日志引用等结构化明细
- `signal_bundle.yaml`
  - 保存治理后的异常信号、对象信号关联、时间线摘要和日志 highlights
- `collection_report.yaml`
  - 保存采集动作、成功项、失败项、留白项和证据缺口

第 3 段原则：

- 采集失败不等同于 analyse 失败
- 部分采集失败应进入 `collection_report.evidence_gaps`
- 证据缺口必须显式传递给第 4 段
- 原始大日志应保存为 artifact，不直接塞入结构化 YAML

## 6. 第 4 段输出

第 4 段由 Agent 主导。

第一版应生成多条候选假设，而不是只生成一个结论。

每条假设至少包含：

- `hypothesis_id`
- `statement`
- `causal_path`
- `supporting_evidence`
- `counter_evidence`
- `disconfirming_conditions`
- `evidence_gaps`
- `validation_actions`
- `validation_result`

`validation_result` 取值（枚举见 [core/taxonomies/status-types.yaml](../../core/taxonomies/status-types.yaml)）：

- `supported`
- `refuted`
- `insufficient`

> 字段结构以 [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml) 为准，本清单为摘要。

第 4 段原则：

- 必须区分“未采到证据”和“证据证明没有问题”
- 必须显式记录反证条件
- 必须将每个验证动作和结果挂回对应假设
- 如果证据不足，应输出 `insufficient`，不强行下确定结论

模板：

- [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml)

## 7. 第 5 段输出

第 5 段负责形成阶段性结论和知识沉淀候选。

第一版至少输出（结构对齐 `core/templates/analysis.template.yaml`）：

- `conclusion_summary`
  - `statement`
  - `confidence`
  - `impact_scope`
  - `primary_cause_category`
  - `evidence`
  - `limitations`
- `next_actions`
- `knowledge_candidates`

建议 `confidence` 使用：

- `high`
- `medium`
- `low`

`knowledge_candidates` 可以包括：

- 新 runbook 候选
- 新 command 候选
- 新 script 候选
- 新 skill 候选
- 已有资产的修订建议

模板：

- [core/templates/knowledge-candidate.template.yaml](../../core/templates/knowledge-candidate.template.yaml)

第 5 段原则：

- 结论必须引用证据
- 置信度必须和证据充分性匹配
- 高风险动作只作为建议，不自动执行
- 知识沉淀候选不直接写入正式资产，需要后续 review

## 8. Adapter Output

`analyse` 完成后，应返回 `adapter output` 摘要。

成功完成时：

- `command: analyse`
- `status: completed`
- `summary` 简述分析结果
- `record_refs` 指向生成的 incident 文件
- `next_actions` 给出用户下一步动作
- `blocking_items: []`

阻塞时：

- `command: analyse`
- `status: blocked`
- `blocking_items` 必须非空
- `record_refs` 可以只包含当前已有记录

失败时：

- `command: analyse`
- `status: failed`
- `warnings` 或 `blocking_items` 说明失败位置

`adapter output` 不承载完整证据，只引用 incident 记录。

## 9. 非目标

第一版 `analyse` 明确不实现：

- 不实现 `--scope`
- 不实现 `--force_recollect`
- 不做自动修复
- 不执行高风险处置动作
- 不做跨中间件联合诊断
- 不保证覆盖所有 MongoDB 部署架构
- 不自动把知识沉淀候选写入正式资产
- 不替代 `/review` 的插件效果评分

## 10. 验收条件

第一版 `analyse` 规范验收条件：

- 能说明第一版 analyse 的输入来源
- 能说明前置条件不足时如何 blocked
- 能列出 MongoDB 第一版执行的 11 个脚本
- 能说明第 3 段的三个主要输出
- 能说明第 4 段假设结构
- 能说明第 5 段结论结构
- 能说明 adapter output 的摘要职责
- 能明确列出第一版不做的能力

## 11. 后续版本

后续版本再考虑：

- `--scope`
- `--force_recollect`
- 更多 MongoDB 场景
- operator+CRD 完整认证适配
- 更多中间件
- review 评分自动化
- fixture replay 和 score comparison 自动化
