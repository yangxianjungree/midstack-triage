---
status: draft
last_updated: 2026-06-19
supersedes: none
superseded_by: none
---

# Phase 4 Agent-Driven Reasoning Flow

本文面向开发人员，说明第 4 段如何把第 3 段信号、领域知识、历史经验预留字段和 Agent refinement 串成可审计的推理闭环。

规范性字段定义以 [triage-workflow.spec.md](../specs/triage-workflow.spec.md) 和 [analysis.template.yaml](../../core/templates/analysis.template.yaml) 为准。本文只解释开发和扩展时的协作方式。

## 目标

第 4 段不只是给出“像什么故障”的分类，而是持续回答三个问题：

- 当前证据能支持哪些候选假设。
- 哪些领域不变量、反证和时间线能把结论从现象推进到机制或根因。
- 还缺什么只读证据，才能验证或排除下一层假设。

## 输入

当前 Phase 4 主要读取这些 incident 产物：

- `structured_record.yaml`：对象、拓扑、状态、日志和脚本结构化结果。
- `signal_bundle.yaml`：异常信号、对象关联、时间线摘要和归一化后的信号。
- `collection_report.yaml`：采集覆盖面、失败项和证据缺口。
- `analysis.rules-fallback.yaml`：rules fallback 产出的生产分析副本。
- `analysis.multitrack.yaml`：multitrack 辅助草稿，不替代生产 `analysis.yaml`。
- `agent-reasoning-task.md`：人工或 Agent refinement 的任务合同。
- `retrieval_context` / `experience_matches`：未来历史经验或向量库召回字段；当前未接入真实召回时 `experience_matches` 为空。

## 推理闭环

1. Phase 3 先把原始状态、日志、指标、事件和拓扑压缩成结构化信号。
2. rules fallback 生成保守的基线假设、结论、证据缺口和下一步动作。
3. 领域不变量检查把已采证据继续深化成 `deepening_findings`，例如 MongoDB replica set 多视角配置、成员和 quorum 是否一致。
4. 时间线构建器把用户线索、异常信号、Kubernetes events 和采集动作整理进 `reasoning_timeline`。
5. Phase 4 根据证据缺口和待验证假设生成 `verification_requests`，但当前只表达计划，不默认动态执行。
6. Agent refinement 读取上述产物，补充或修正 `analysis.yaml` 与 `report.md`。
7. 第 5 段把可靠结论、证据缺口、只读下一步和可沉淀知识写回结果与 `knowledge_candidates`。

## 推理历史与共享隔离

`analysis.yaml` 和 `report.md` 是最新物化视图，允许被 rules fallback、Agent refinement 和 finalize 刷新。为了避免推理过程被覆盖，Phase 4/5 同时维护 append-only 历史：

- `reasoning-manifest.yaml`：可变索引，记录当前 `current_head`、物化输出、共享证据池和隔离模型。
- `reasoning/*.yaml`：不可变 segment，例如 `0001-rules-fallback.yaml`、`0002-agent-refinement.yaml`；每个 segment 保存当轮 `analysis_snapshot`、结论摘要和 hypothesis validation。

共享/隔离规则：

- `input.yaml`、`structured_record.yaml`、`signal_bundle.yaml`、`collection_report.yaml` 属于共享只读证据池。
- 每个 hypothesis validation 只能写自己的 `private_write_ref`，例如 `reasoning/0002-agent-refinement.yaml#hypothesis_validations[H1]`。
- 一个 hypothesis 的支持证据、反证、证据缺口和验证请求必须挂回该 hypothesis，不能覆盖另一个 hypothesis 的验证记录。
- 当某轮 refinement 需要改变总体结论时，追加新的 segment 并移动 manifest `current_head`；不要改写旧 segment。
- `analysis.yaml` 保持方便消费的最新视图；需要审计过程时读取 manifest 和 segment 历史。

## Agent 的职责

Agent refinement 应该做：

- 比较多个候选假设，不只复述 rules fallback 的第一结论。
- 使用 `reasoning_timeline` 解释关键事件顺序，但不把时间先后单独当作因果证明。
- 使用 `deepening_findings` 从机制继续追问 enabling cause 或 root cause。
- 将已经出现的反证写入 `counter_evidence`，避免把被反驳路径继续作为无条件下一步。
- 将缺失证据分成 `expected_gap` 和 `critical_gap`，并据此控制结论层级与置信度。
- 保留 `verification_requests`、`retrieval_context`、`experience_matches` 和 `source_boundaries` 等顶层字段。

Agent refinement 不应该做：

- 把历史经验、runbook、用户线索或知识资产当作当前故障的直接结论证据。
- 在当前证据不足时强行给出 root cause。
- 重复建议已经采集、已验证或已被反证的动作。
- 绕过 execution guardrail 自行执行会改变环境状态的命令。

## 动态验证边界

Phase 4 可以提出验证请求，但验证请求分层处理：

| 层级 | 例子 | 策略 |
| --- | --- | --- |
| 一等只读资产 | `domains/*/scripts/manifest.yaml` 中声明为 `readonly: true` 的脚本或结构化 command | 可进入 `verification_requests`，允许标记 `execution_policy: auto_allowed` |
| 二等临时只读命令 | 临时 `kubectl get`、`mongosh` 只读查询、日志 tail | 必须先经过只读 guardrail，默认先记录为 planned |
| 改变环境的动作 | `rs.reconfig()`、删除 Pod、重启进程、修改 YAML、写文件 | 必须 `blocked`，不得由 Phase 4 自动执行 |

开发新能力时，优先把稳定的只读验证沉淀为一等资产，而不是让 Agent 长期依赖自由拼接命令。

## 历史经验和领域知识

未来接入向量数据库或历史案例库后，经验召回应只影响两个位置：

- 生成新的候选假设。
- 生成新的只读验证路径。

经验召回不能直接进入：

- `supporting_evidence`
- `conclusion_summary.evidence`
- `deepening_findings.evidence_refs`

这些字段只能引用当前 incident 的证据。历史经验的价值是提示“可能像什么”和“下一步怎么验证”，不是替代现场取证。

## MongoDB Split-Brain 示例

以 MongoDB 副本集脑裂为例：

- 现象层：多个成员视角中出现不一致的 PRIMARY 或成员健康状态。
- 机制层：成员之间的 `rs.status()` 视角不一致，说明副本集决策视图已经分裂。
- 深化层：如果 `config_version`、`config_term`、members 列表和 `voting_members_count` 多视角不一致，应记录为配置、成员或 quorum 不变量冲突。
- 反证层：如果当前 TCP/27017 已经双向连通，不能继续把“持续网络分区”当作未经限定的唯一解释。
- 待验证层：下一步应转向只读比较 `rs.conf()`、MongoDB heartbeat/election 日志、变更记录和重启前日志，解释为什么配置或视图会分裂。

这类设计不是为某一个 case 写死规则，而是把领域诊断语法沉淀为可复用的不变量、反证和验证请求。

## 新领域扩展方式

为新中间件或新组件扩展 Phase 4 时，按以下顺序做：

1. 定义最小信号：哪些状态、日志、指标或事件可以低成本采集。
2. 定义领域不变量：哪些事实在健康系统中必须一致或满足约束。
3. 定义反证：哪些已采事实会削弱或排除常见错误假设。
4. 定义一等只读验证资产：把稳定验证动作放入 `domains/<product>/scripts/`、`commands/` 或 runbook。
5. 定义经验知识入口：把专家经验写进 domain component、runbook 或 skill，但保持证据边界。
6. 更新 rules fallback 或 deepening helper，让 `analysis.yaml` 输出结构化字段，而不是只输出自然语言总结。

## 常见反模式

- 只识别故障类型，不继续追问为什么能发生。
- 把所有 next actions 都写成通用排查列表，不看当前证据已经验证或反驳了什么。
- 让 Agent 临时拼接大量命令，长期不沉淀一等资产。
- 把历史案例中的答案直接套到当前 incident。
- 把 timeline 写成报告装饰，而不是用来约束因果推理和证据缺口。
