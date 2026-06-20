---
status: draft
last_updated: 2026-06-20
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
- `agent_conclusion_gate`：Agent 草稿是否具备提升为正式结论的资格评估；当前只记录资格，不应用覆盖。
- `agent-reasoning-task.md`：人工或 Agent refinement 的任务合同。
- `retrieval_context` / `experience_matches`：未来历史经验或向量库召回字段；当前未接入真实召回时 `experience_matches` 为空。
- `deep_analysis_requests`：深入层推理请求，描述基线扫描、代码逻辑、路径追踪或复现计划等 plan-only 工作，不代表自动执行命令。

## 推理闭环

1. Phase 3 先把原始状态、日志、指标、事件和拓扑压缩成结构化信号。
2. rules fallback 生成保守的基线假设、结论、证据缺口和下一步动作。
3. 领域不变量检查把已采证据继续深化成 `deepening_findings`，例如 MongoDB replica set 多视角配置、成员和 quorum 是否一致。
4. 时间线构建器把用户线索、异常信号、Kubernetes events 和采集动作整理进 `reasoning_timeline`。
5. Phase 4 根据证据缺口和待验证假设生成 `verification_requests`；命令编排层会把一等只读且 `auto_allowed` 的脚本请求交回 Phase 3 定向补采，然后重新生成生产 `analysis.yaml`。
6. 当机制证据已经成立但 enabling/root cause 未闭合时，Phase 4 可以生成 `deep_analysis_requests`，要求 Agent 或后续开发工作继续做基线扫描、代码逻辑分析、代码路径追踪或只读复现计划。
7. analyse 主链路把 multitrack/Claude 草稿摘要写入 `agent_reasoning`，并通过 `agent_conclusion_gate` 评估它是否满足提升资格。
8. Agent refinement 读取上述产物，补充或修正 `analysis.yaml` 与 `report.md`。
9. 第 5 段把可靠结论、证据缺口、只读下一步和可沉淀知识写回结果与 `knowledge_candidates`。

## 推理历史与共享隔离

`analysis.yaml` 和 `report.md` 是最新物化视图，允许被 rules fallback、Agent refinement 和 finalize 刷新。为了避免推理过程被覆盖，Phase 4/5 同时维护 append-only 历史：

- `reasoning-manifest.yaml`：可变索引，记录当前 `current_head`、物化输出、共享证据池和隔离模型。
- `reasoning/*.yaml`：不可变 segment，例如 `0001-rules-fallback.yaml`、`0002-agent-refinement.yaml`；每个 segment 保存当轮 `analysis_snapshot`、结论摘要、自动验证执行审计和 hypothesis validation。

共享/隔离规则：

- `input.yaml`、`structured_record.yaml`、`signal_bundle.yaml`、`collection_report.yaml` 属于共享只读证据池。
- 每个 hypothesis validation 只能写自己的 `private_write_ref`，例如 `reasoning/0002-agent-refinement.yaml#hypothesis_validations[H1]`。
- 一个 hypothesis 的支持证据、反证、证据缺口和验证请求必须挂回该 hypothesis，不能覆盖另一个 hypothesis 的验证记录。
- 一等只读 `auto_allowed` 请求如果被编排层执行，其脚本状态和输出引用写入当前 segment 的 `executed_validations`；请求本身仍可在 `analysis.yaml.verification_requests` 中保留为待闭合证据缺口。
- 当某轮 refinement 需要改变总体结论时，追加新的 segment 并移动 manifest `current_head`；不要改写旧 segment。
- `analysis.yaml` 保持方便消费的最新视图；需要审计过程时读取 manifest 和 segment 历史。

## Agent 的职责

Agent refinement 应该做：

- 比较多个候选假设，不只复述 rules fallback 的第一结论。
- 使用 `reasoning_timeline` 解释关键事件顺序，但不把时间先后单独当作因果证明。
- 使用 `deepening_findings` 从机制继续追问 enabling cause 或 root cause。
- 将已经出现的反证写入 `counter_evidence`，避免把被反驳路径继续作为无条件下一步。
- 将缺失证据分成 `expected_gap` 和 `critical_gap`，并据此控制结论层级与置信度。
- 保留 `verification_requests`、`deep_analysis_requests`、`retrieval_context`、`experience_matches` 和 `source_boundaries` 等顶层字段。

Agent refinement 不应该做：

- 把历史经验、runbook、用户线索或知识资产当作当前故障的直接结论证据。
- 在当前证据不足时强行给出 root cause。
- 重复建议已经采集、已验证或已被反证的动作。
- 绕过 execution guardrail 自行执行会改变环境状态的命令。

## Agent 结论门禁

`agent_conclusion_gate` 是 Agent 草稿和正式结论之间的显式边界。它解决两个问题：第一，Claude 或 multitrack 可能提出更好的候选结论；第二，这个候选不能在没有证据桥的情况下覆盖 rules fallback。

当前门禁条件是保守的：

- runtime 必须是真实 `claude`，mock 草稿只能作为辅助信息。
- 候选 hypothesis 必须是 `supported`，置信度达到门槛。
- 候选必须通过 `agent_reasoning.hypotheses[].evidence_refs` 引用当前 incident 证据，例如 `structured_record`、`signal_bundle`、`collection_report`、`deepening_findings`、`deep_analysis_results` 或 `verification_requests`。
- `experience_matches`、`retrieval_context`、runbook、历史经验和用户线索不能作为直接证据引用。
- 未闭合的 `critical_gap` 会阻止提升。

当前实现只写入 `decision`、`selected_candidate`、`blockers` 和 `override_applied: false`。即使 `decision: eligible`，生产 `conclusion_summary` 仍由 rules fallback + guardrails 守底；后续如果要启用覆盖，需要单独实现“应用 override 并追加 reasoning segment”的闭环。

## 动态验证边界

Phase 4 可以提出验证请求，但验证请求分层处理。`verification_requests` 是当前仍需要验证或补采的请求队列，不是完整执行日志；执行历史和每轮推理快照由 `reasoning-manifest.yaml` 与 `reasoning/*.yaml` 承载。

| 层级 | 例子 | 策略 |
| --- | --- | --- |
| 一等只读资产 | `domains/*/scripts/manifest.yaml` 中声明为 `readonly: true` 的脚本或结构化 command | 可进入 `verification_requests`，允许标记 `execution_policy: auto_allowed`；在 `analyse` 编排中会自动进入 Phase 3 定向补采 |
| 二等临时只读命令 | 临时 `kubectl get`、`mongosh` 只读查询、日志 tail | 必须使用结构化 `asset.argv`，经过只读 guardrail 后仍只能是 `approval_required`，默认先记录为 planned |
| 改变环境的动作 | `rs.reconfig()`、删除 Pod、重启进程、修改 YAML、写文件 | 必须 `blocked`，不得由 Phase 4 自动执行 |

自动补采不是 Phase 4 直接执行命令，而是控制面在 rules fallback 产出后调用 Phase 3 recollection 复用既有执行面。补采完成后 rules fallback 会基于更新后的证据重新物化 `analysis.yaml` 和 `report.md`。如果请求仍缺证据，它可以继续以 `planned` 形式保留；因此 `status: planned` 不能单独理解成“从未尝试过”。

开发新能力时，优先把稳定的只读验证沉淀为一等资产，而不是让 Agent 长期依赖自由拼接命令。

## 深入层请求边界

`deep_analysis_requests` 用于把“还需要更深一层推理”的工作显式化。它和 `verification_requests` 的区别是：

| 字段 | 含义 |
| --- | --- |
| `capability: baseline_scan` | 对比当前证据和健康基线或领域不变量，输出差异和缺口 |
| `capability: code_logic_analysis` | 解释组件决策逻辑或协议规则如何允许当前机制发生 |
| `capability: code_path_tracing` | 把日志、状态、配置和命令输出串成可审计证据路径 |
| `capability: repro_script_generation` | 生成只读复现计划、合成 fixture 或 simulator 方案，不操作 live 环境 |

当前 `deep_analysis_requests` 默认是 `execution_boundary: plan_only`、`risk_level: read-only`、`scope: current_incident`。analyse 主链路可以基于已有 incident 证据把这些请求派生成 `deep-analysis.yaml` 和 `analysis.yaml.deep_analysis_results`，但这个物化过程仍是只读的派生分析，不执行仓库外命令，也不接触 live 环境。如果深挖过程中发现需要新现场证据，必须转换成受 guardrail 保护的 `verification_requests`；不能把 shell 命令或会改环境的动作塞进 `deep_analysis_requests`。

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
- 成因候选层：将历史网络或 MongoDB heartbeat 分区、reconfig/member metadata drift、MongoDB heartbeat/auth/process 层异常写成 `insufficient` hypothesis，而不是直接升格为根因。
- 待验证层：下一步应转向只读比较 `rs.conf()`、MongoDB heartbeat/election 日志、变更记录和重启前日志，解释为什么配置或视图会分裂；`mongodb.collect.replicaset.rs_conf` 和仓库内日志脚本都属于一等只读资产。
- 深入层：输出 `deep_analysis_requests`，让 Agent 或开发者继续做健康基线对比、MongoDB 选举/配置决策逻辑解释、证据路径追踪，以及不改 live 集群的只读复现计划。

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
