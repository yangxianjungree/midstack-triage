---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 2026-06-10 推理分析流程复盘

本文件记录 2026-06-10 围绕 MongoDB analyse 第 3/4/5 段链路的阶段性复盘，属于过程性讨论文档，不是 L1 事实源。

## 背景

在 sandbox 真实运行 incident

- `/home/stephen/AI/midstack-cursor-sandbox/.local/incidents/mongodb-20260610-192948-hjil`

时，当前链路已经验证出以下事实：

- 第 3 段证据包可以正常落盘
- 规则 runner 可以生成保底草稿 `analysis.rule-draft.yaml`
- Cursor Agent 可以继续回填更完整的正式 `analysis.yaml` 与 `report.md`

但这次运行也暴露出当前设计和实现仍有明显缺口，尤其集中在：

- 第 3 段采集模型是否合理
- 第 4 段推理是否具备足够的证据充分性约束
- 第 3 段与第 4 段之间是否应是单向串行，还是应支持小循环

## 本次真实运行的核心观察

### 1. 当前链路已经不是“只停在规则草稿”

真实 run 中：

- `analysis.rule-draft.yaml` 先生成
- 随后 `analysis.yaml` 被 Cursor Agent 改写
- `report.md` 也被对应刷新

说明“规则保底草稿 + Agent 回填正式分析”的方向是可行的。

### 2. 这次分析中“故障现象定位”是成立的

当前证据已经足以支持以下现象级判断：

- `pod/bnmongo-shard1-data-2` 处于 `CrashLoopBackOff`
- `mongod` 在启动后数秒内退出，退出码为 `14`
- `statefulset/bnmongo-shard1-data` 当前只有 `2/3` ready

也就是说：

- “哪个 Pod 出问题”
- “问题表现是什么”
- “对 shard 成员可用性造成了什么影响”

这些层级的结论可以成立。

### 3. 但“内部根因判断”证据仍然不足

当前 run 仍缺：

- 来自健康 peer 的 `rs.status`
- 更长的 mongod fatal log
- 更完整的 termination message / deeper runtime detail

因此这次 run 更合理的上限是：

- 对“故障现象”和“受影响拓扑单元”高置信
- 对“MongoDB 进程为何退出”“是否为副本集内部状态问题”保持中低置信或 `insufficient`

这里的关键不是“分析失败”，而是“能下到哪一层结论”必须受证据约束。

## 当前设计问题判断

## 1. 第 3 段和第 4 段当前过于线性

现在的主路径更接近：

`第 3 段采集 -> 第 4 段读现成证据 -> 第 5 段收尾`

这对于简单场景可工作，但对真实生产问题偏弱，因为：

- 第 4 段一旦提出新假设，无法自然回到第 3 段做定向补采
- 推理层只能被动接受“已有证据”，缺少“围绕假设继续找证据”的能力
- 复杂故障容易在证据不充分时过早收敛

更合理的模式应是：

`第 3 段初始证据 -> 第 4 段假设 -> 定向补采 -> 假设修正 -> 收敛`

也就是第 3/4 段之间应支持一个小循环，而不是严格一次性串行。

## 2. 当前 MongoDB 采集模型过于 Pod-centric，不够 topology-centric

这次讨论中已经确认一个重要判断：

- 故障 Pod 自身拿不到 `rs.status`，对 MongoDB 来说是正常现象，不应被误判为“额外异常”

真正应该建模的是：

- `mongos` 的可用候选执行点
- `configsvr` 副本集的可用候选执行点
- 每个 shard 副本集的可用候选执行点

对于 `rs.status`：

- 不需要机械地“每个成员都跑一次”
- 但每个 replica set 至少要有可选的健康执行点
- 当首选执行点失败时，应能自动 fallback 到同 replica set 的其他健康 member

对于 `mongos.get_shard_map`：

- 不应绑定单一 `mongos` Pod
- 应先找到一个健康、具备 `mongosh` / `mongo` 能力的 `mongos` 候选执行点

也就是说，第 3 段对 MongoDB 的采集目标应从“脚本打某个 Pod”升级为“脚本打某个拓扑单元的候选执行点集合”。

## 3. 当前缺少明确的证据充分性约束

这次 run 里，Agent 最终给出了合理方向，但当前合同仍有风险：

- 当故障 Pod 日志极短时，系统仍可能继续推断更深层根因
- 当 `rs.status` 缺失时，系统仍可能把副本集层判断说得过满
- 当前 `collection_report.evidence_gaps` 还没有区分“这是预期拿不到”还是“这是关键证据缺失”

因此，第 4 段需要显式引入：

- 结论层级约束
- 置信度上限约束
- 证据 gap 分类

## 设计修正建议

## 1. 将 analyse 主路径改为“证据驱动的小循环”

建议保留 5 段式大框架，但运行时允许：

- 第 3 段先生成初始证据包
- 第 4 段先提出候选假设和待验证动作
- 对可自动执行的只读验证动作，返回第 3 段补采
- 收到补采结果后，再由第 4 段继续收敛

这意味着：

- `analysis.yaml` 不一定一次性生成完
- 第 4 段应能驱动“二次采集”而不是只读静态文件

## 2. 明确 MongoDB 的“拓扑单元 -> 候选执行点”模型

建议在当前 `targets` 之上继续引入更明确的执行模型：

- `mongos_targets`
- `configsvr_targets`
- `shard_targets`
- `replicaset_targets`

每个 target 至少记录：

- 所属拓扑单元
- 候选 Pod 列表
- 当前健康优先级
- `mongosh` / `mongo` 是否可用
- 认证信息是否可用
- 最近一次失败原因

这样第 3 段就可以在执行前先判断：

- 这是“目标本来就故障，应该换 peer 采”
- 还是“整个 replica set 没有可用执行点，属于关键证据缺失”

## 3. 区分“故障现象结论”和“内部根因结论”

建议第 4/5 段在逻辑上区分两类结论：

- 现象级结论
  - 哪个对象异常
  - 异常表现是什么
  - 影响范围是什么
- 根因级结论
  - 为什么会这样
  - 属于 Kubernetes 层、MongoDB 进程层、配置层、认证层还是副本集层

如果只拿到了现象证据，就不应强推根因结论。

## 4. 为“证据不足但未失败”建立显式规则

建议新增两类 gap：

- `expected_gap`
  - 例如故障 Pod 无法提供自己的 `rs.status`
  - 例如坏 Pod 当前日志窗口过短，不能直接看到完整 shutdown / fatal tail
- `critical_gap`
  - 例如整个 replica set 没有任何健康 peer 可执行 `rs.status`
  - 例如所有 `mongos` 候选都无法获取 shard map
  - 例如所有认证候选都失效，导致关键 MongoDB 内部查询完全无法执行

只有 `critical_gap` 应显著拉低根因级结论的置信度或阻塞更深推理。

## 5. 对根因结论施加置信度上限

建议引入如下约束：

- 如果没有 peer `rs.status`，则“副本集内部状态问题”为 `supported` 的门槛应明显提高
- 如果没有足够的 mongod fatal log 或 termination detail，则“MongoDB 进程内部根因”不应高置信
- 如果只掌握 Pod runtime / event / workload readiness，则最多高置信下到“容器重启 / 成员不可用”这一层

这类约束不表示 analyse 失败，而是表示：

- 允许对现象高置信
- 但限制对更深根因的结论强度

## 外部参考与启发

以下资料不直接决定我们怎么实现，但对当前讨论有明确参考价值。

### 1. Datadog Bits AI SRE：推理和采集应形成循环，而不是一次性串行

Datadog 官方文档明确描述：

- 调查过程是连续的 `observation -> reasoning -> action` 循环
- 先形成假设，再查询数据验证或反驳
- 新证据出现后继续修正理解
- 如果证据不足，应输出 inconclusive，而不是强行给出结论

这和我们当前讨论的“第 3/4 段应形成小循环”高度一致。

参考：

- Datadog Docs, `Investigate Issues`
  - https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/
- Datadog Docs, `Bits AI SRE`
  - https://docs.datadoghq.com/bits_ai/bits_ai_sre/
- Datadog Blog, `Meet the new Bits AI SRE: Deeper reasoning, twice as fast`
  - https://www.datadoghq.com/blog/bits-ai-sre-deeper-reasoning/

### 2. PagerDuty：先找 origin / impact radius，而不是盯着单个坏点

PagerDuty 的 `Probable Origin` 强调：

- 优先帮助响应者定位更可能的 origin point
- 结合 related incidents 与依赖关系理解 impact radius
- 目标是尽快把正确团队拉进来，而不是让所有团队平铺排查

对我们来说，这意味着 MongoDB analyse 不应只围绕坏 Pod 做局部判断，而应优先识别：

- 它属于哪个 replica set / shard / configsvr
- 这个拓扑单元的其他健康 peer 是谁
- 是否存在更上游的 origin

参考：

- PagerDuty Knowledge Base, `Probable Origin`
  - https://support.pagerduty.com/main/docs/probable-origin
- PagerDuty Knowledge Base, `PagerDuty AIOps Quickstart Guide`
  - https://support.pagerduty.com/main/docs/pagerduty-aiops-quickstart-guide

### 3. AWS：Agent 不是只读现成证据，而是先问上下文，再跨数据源取证、拼时间线

AWS Security Incident Response 的官方介绍强调：

- agent 会先问 clarifying questions
- 再自动跨多个数据源取证
- 自动关联时间线与关键信息
- 最终输出 summary + timeline + findings

对我们来说，它强化了两点：

- 推理层应能驱动补采，而不是被动消费一次性证据
- 证据链和时间线本身应作为一等输出，而不仅是附属文本

参考：

- AWS Security Blog, `Accelerate investigations with AWS Security Incident Response AI-powered capabilities`
  - https://aws.amazon.com/blogs/security/accelerate-investigations-with-aws-security-incident-response-ai-powered-capabilities/

### 4. Microsoft LLexus / Triangle：TSG 编排、多角色协同、自动信息收集是正式方向

Microsoft 的相关研究和实践里：

- `LLexus` 明确把 Troubleshooting Guides 作为自动执行对象
- `Triangle` 强调多 Agent、多角色、自动故障信息收集和协同

这说明我们当前“规则保底 + Agent 推理 + runbook/skill/TSG 资产”的方向是合理的，但运行时应进一步补齐：

- 多轮信息收集
- 按团队/拓扑/领域拆分的角色视角
- 更显式的 TSG 驱动验证动作

参考：

- Microsoft Research, `LLexus: an AI agent system for incident management`
  - https://www.microsoft.com/en-us/research/publication/llexus-an-ai-agent-system-for-incident-management/
- Microsoft Research, `Triangle: Empowering Incident Triage with Multi-Agent`
  - https://www.microsoft.com/en-us/research/publication/triangle-empowering-incident-triage-with-multi-agents/
- Azure Blog, `Optimizing incident management with AIOps using the Triangle System`
  - https://azure.microsoft.com/en-us/blog/optimizing-incident-management-with-aiops-using-the-triangle-system/

## 当前建议结论

当前建议先不要立刻大改推理 prompt，而应先在设计上确认以下原则：

1. 第 3 段和第 4 段之间允许形成“初始采集 -> 假设 -> 补采 -> 收敛”的小循环
2. MongoDB 的关键内部查询应围绕“拓扑单元 + 候选健康执行点”建模，而不是绑定单 Pod
3. 故障 Pod 拿不到自身 `rs.status` 属于常见现象，应优先尝试健康 peer
4. 证据不足不等于 analyse 失败，但必须限制根因结论的层级和置信度
5. `collection_report` 需要区分 `expected_gap` 与 `critical_gap`

## 后续建议顺序

1. 先将上述原则补入当前 proposal / todo / code-change-plan
2. 再决定是否继续当前 paused 的 finalize 收尾代码
3. 然后优先改 MongoDB 第 3 段采集模型：
   - replica set 候选执行点
   - fallback 采集策略
   - critical gap 判定
4. 最后再调整 Agent 推理合同和置信度约束
