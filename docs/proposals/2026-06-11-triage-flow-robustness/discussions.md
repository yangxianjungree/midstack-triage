---
status: draft
last_updated: 2026-06-11
supersedes: none
superseded_by: none
---

# 排障流程健壮性 — 讨论记录

本文件承接 [`context.md`](./context.md) 中的待讨论点。每个二级标题对应一个独立讨论主题；讨论过程、选项对比和结论都写在对应章节内。

讨论状态：`pending` | `in_progress` | `decided` | `deferred`

---

## `analyse` 是否应显式支持一轮或多轮定向补采

**状态：** `decided`

### 背景

当前主路径更接近「第 3 段一次性采集 → 第 4 段读现成证据 → 第 5 段收尾」。真实排障更常见的是「初始采集 → 假设 → 发现证据缺口 → 定向补采 → 修正假设 → 收敛」。Datadog Bits AI SRE 等产品也是 observation → reasoning → action 循环，而不是一次性串行。

相关背景见 [`context.md`](./context.md) 与 [`2026-06-10-reasoning-flow-review.md`](../2026-06-10-align-code-module/2026-06-10-reasoning-flow-review.md)。

### 待决问题

- 第一版是否需要显式支持多轮，还是只预留记录结构、运行时仍单轮？
- 补采由谁触发：Agent 推理层、规则 runner，还是两者协作？
- 补采范围是否限定为只读动作？是否需要上限（轮次、动作数、超时）？
- 多轮补采在命令层如何体现：仍是一次 `/midstack:analyse`，还是用户可感知的多阶段？

### 讨论记录

#### 2026-06-11 — 现状梳理

当前实现（`tools/plugin/midstack-local.py` + `midstack:analyse` 命令）的实际链路：

```text
远程 executor 跑固定 11 步采集脚本
  -> mongodb-analyse.py 规则草稿
  -> 写 analysis.rule-draft.yaml / report.md / agent-reasoning-task.md
  -> Agent 读现成 artifact，回填 analysis.yaml
  -> midstack_finalize_analysis
```

几个关键事实：

- L1 已预留 `validation_actions`（`planned|executed|blocked`）和 `next_actions`，但**没有**「回到第 3 段执行补采」的运行时机制。
- `analyse-mvp.spec.md` 和 `plugin-runtime.spec.md` 明确把 `--force_recollect` 列为**后续版本**，第一版不实现。
- incident 状态机允许 `analysed` 后继续 analyse，但这是「整轮重跑」，不是「围绕假设的定向补采」。
- k8s-project 案例说明：补采的价值往往来自**问题重写**（如「真实 MongoDB 日志源在哪」），而不只是「再多跑一遍固定清单」。

#### 2026-06-11 — 方案选项

**方案 A：第一版仍单轮，只加强记录**

- 运行时：固定清单采集一次，Agent 推理一次。
- 改进：`validation_actions` / `next_actions` / `evidence_gaps` 写清楚「建议补采什么、为何重要」。
- 补采动作留给人工或后续 `/analyse` 整轮重跑。
- 优点：改动最小，和当前 MVP 边界一致。
- 缺点：推理层仍被动消费一次性证据；和 Datadog 式循环差距大。

**方案 B：第一版支持「一轮」定向补采（推荐作为最小闭环）**

- 运行时：`初始采集 -> 规则/Agent 初判 -> 最多 1 轮定向补采 -> 再推理收敛`。
- 补采触发：Agent 从 `validation_actions` 或 gap 列表选出**已在 script catalog 内的只读动作**；runner 执行后 merge 进 incident artifact。
- 命令层：用户仍只调一次 `/midstack:analyse`；补采是内部小循环，对用户透明。
- 上限：1 轮、限定 script 白名单、超时/动作数 cap。
- 优点：最小实现即可验证「假设驱动补采」是否真提升结论质量；和昨天复盘建议一致。
- 缺点：需要定义补采动作选择规则、artifact merge 合同、何时停止。

**方案 C：第一版支持多轮自动循环**

- 类似 Datadog Bits：observation → reasoning → action 直到收敛或达上限。
- 优点：最接近理想排障形态。
- 缺点：编排、停止条件、成本控制、过程可追溯性都显著复杂；不适合作为第一版闭环。

#### 2026-06-11 — 收敛后的方向

本轮讨论先收敛到以下方向：

- 用户侧仍保持**一次** `/midstack:analyse`，不把主路径做成多个用户可见的 analyse 循环。
- 单次 analyse 内部允许维护**多条候选假设**，并在假设之间比较支持证据、反证和证据缺口。
- 第一版运行时只支持**最多 1 轮**定向补采小循环，不直接做多轮自动编排。
- 定向补采由 Agent 推理层触发、runner 执行；runner 负责白名单和执行边界，不负责自主决定补采方向。
- 补采动作只允许**catalog 白名单内的只读动作**；任何需要写操作、破坏性动作或额外人工确认的动作，都不进入自动小循环。
- 若补采后仍缺关键证据，analyse 允许以**阶段性结论 + 关键 gap + next actions** 收尾，不强行给根因。

这个方向的目标不是保证每次都拿到根因，而是把「一次性串行采集」升级为「单次 analyse 内的证据驱动收敛」。

#### 2026-06-11 — 运行时门禁与停止条件

| 分项 | 本轮结论 | 说明 |
|---|---|---|
| 轮次 | 先 1 轮 | 多轮留后续；先验证小循环是否真提升结论质量 |
| 触发者 | Agent 主导，runner 执行 | 规则 runner 可提示 gap，但不反过来自动决定补采 |
| 动作范围 | 只读 + catalog 白名单 | 不开放任意 shell；优先固定 playbook |
| 命令体验 | 单次 `/midstack:analyse` | 不拆新 slash 命令；内部完成小循环 |
| 收尾方式 | 允许 inconclusive / 阶段性收尾 | 结论受限时给出 gap 和 next actions，不强行给根因 |
| 与 `force_recollect` 关系 | 定向补采 ⊂ 后续 recollect 能力 | 定向是围绕假设补几项；force_recollect 是整包重采 |

进入定向补采小循环前，至少同时满足以下门禁：

1. 仍有至少 1 条值得继续验证的假设，且当前状态为 `insufficient`，不是已支持或已排除。
2. 存在明确的 `critical_gap`，该 gap 会影响结论层级或主假设判断，而不只是补充细节。
3. 有白名单内、只读、可执行的补采动作，且动作成功后预期会带来明确的信息增益。
4. 该补采有机会完成以下至少一项：支持主假设、排除强备选假设、提升可给出的结论层级。

第一版建议附加以下硬上限：

- 每次 `/midstack:analyse` 最多 1 轮定向补采。
- 每轮最多 2 到 3 个补采动作。
- 仅允许只读动作。
- 超过单轮时间预算后停止，转为阶段性结论。

停止条件建议为：

- 已取得足够直接的证据，主假设可支持。
- 补采后仍缺关键证据，且剩余只读动作无法关闭关键 gap。
- 剩余动作只会补细节，不会改变结论深度或主要判断。
- 需要写操作、权限提升或人工确认才能继续。

#### 2026-06-11 — 第一版补采 playbook 倾向

第一版不建议完全依赖 Agent 临场即兴决定补采动作，而是优先从固定 playbook 起步，再允许 Agent 在白名单范围内选用：

- replica set `rs.status` peer fallback
- `kubectl logs --previous` / previous logs 补采
- 健康 peer / 同伴视角连接验证
- 应用日志源定位（log sink / destination / path）
- 节点侧只读日志文件追踪

其中「应用日志源定位」应作为一个明确 playbook 存在：当 `kubectl logs` 很短，但现象更像“应用进程启动后失败”时，不直接猜根因，而是先回答“应用日志真正写到哪里”。对 MongoDB，这通常意味着先查健康 Pod 中的 `mongod` 配置，再确认日志文件是否回链到 stdout/stderr，必要时继续追到卷或节点侧真实文件。

### 结论

已决定采用**单次 `/midstack:analyse` + 多假设并行维护 + 最多 1 轮定向补采小循环**的方向，而不是多个用户可见 analyse 循环。第一版的重点是把 evidence-driven 小循环跑通，并通过门禁、白名单、时间预算和阶段性收尾控制复杂度；多轮自动循环留待后续版本再评估。

---

## `collection_report` 是否需要区分 `expected_gap` 与 `critical_gap`

**状态：** `decided`

### 背景

当前 `evidence_gaps` 尚未区分「预期拿不到」和「关键证据缺失」。例如故障 Pod 无法提供自身 `rs.status` 属于常见现象；但整个 replica set 没有任何健康 peer 可执行 `rs.status` 则属于关键缺口，应显著拉低根因级结论置信度。

### 待决问题

- 两类 gap 的定义边界是什么？由采集脚本判定还是 Agent 判定？
- 是否进入 L1 schema / taxonomy，还是先在 prompt 和 review 中软约束？
- `critical_gap` 是否应阻塞更深推理，还是只限制置信度上限？
- 与现有 `failed_items` / `blank_items` 的关系如何划分，避免语义重叠？

### 讨论记录

#### 2026-06-11 — 为什么要区分两类 gap

当前 `failed_items` / `blank_items` 只回答“哪项没采到”或“哪项内容为空”，但不回答：

- 这是不是现场里常见、可预期的缺口；
- 它会不会影响当前假设判断；
- 它会不会限制结论层级和置信度；
- 是否值得触发一轮定向补采。

因此需要把“采集层事实”和“推理层影响”分开表达。

#### 2026-06-11 — 两类 gap 的建议语义

建议保留 `collection_report.evidence_gaps` 作为统一入口，但在运行时显式区分：

- `expected_gap`
  - 现场里常见或可预期的缺口；
  - 当前对象拿不到该证据不意外；
  - 通常存在替代证据路径，或该缺口本身不直接阻断更深判断。
- `critical_gap`
  - 会直接影响某条主假设验证、某类关键内部查询，或某一结论层级；
  - 如果不补齐，就必须限制相关结论的层级或置信度；
  - 在存在白名单补采动作时，应优先作为小循环触发条件。

MongoDB 当前已确认的典型例子：

- 故障 Pod 无法提供自身 `rs.status`，通常属于 `expected_gap`。
- 整个 replica set 没有任何健康 peer 可执行 `rs.status`，属于 `critical_gap`。
- `kubectl logs` 很短但尚未确认应用真实日志源，属于 `critical_gap`。
- 故障 Pod 自身 fatal tail 很短，但已能从文件日志或健康 peer 获得关键证据，通常只算 `expected_gap`。

#### 2026-06-11 — 与现有字段的分工

建议分工如下：

- `failed_items`
  - 记录采集动作失败了什么。
- `blank_items`
  - 记录命令成功但返回为空或无有效内容。
- `evidence_gaps`
  - 记录这些缺口对推理意味着什么，以及是否影响结论深度。

也就是说，`failed_items` / `blank_items` 是执行结果，`evidence_gaps` 是推理语义，不互相替代。

#### 2026-06-11 — 判定责任与运行时效果

第一版建议采用“脚本提示 + Agent 定稿”的方式：

- 采集脚本或 runner 可基于已知模式给出候选 gap 提示。
- Agent 根据当前假设、替代证据和结论目标，最终判定为 `expected_gap` 还是 `critical_gap`。
- `review` 后续应检查 gap 分类是否合理，避免把关键缺口写成普通留白。

运行时效果建议为：

- `expected_gap`
  - 显式记录；
  - 不单独触发自动小循环；
  - 需要在假设或结论里说明替代证据或局限。
- `critical_gap`
  - 可作为定向补采门禁；
  - 若未关闭，应限制相关假设的 `validation_result` 和最终结论层级；
  - 若无可执行只读补采动作，应直接转入阶段性收尾，而不是强行下根因。

#### 2026-06-11 — 第一版落地方式

当前不建议立刻大改 L1 schema。更稳妥的顺序是：

1. 先在 prompt、playbook、review 和 discussion 中把 `expected_gap` / `critical_gap` 的语义跑通；
2. 用几个真实案例验证分类边界；
3. 再决定是否把 gap 类型补进模板和 taxonomy。

### 结论

已决定在运行时显式区分 `expected_gap` 与 `critical_gap`。第一版先作为软约束进入 `collection_report.evidence_gaps`、推理 prompt 和 review 规则，而不是立即大改 L1 schema。`critical_gap` 不等同于 analyse 失败，但若未关闭，应成为补采触发条件或结论层级/置信度上限的依据。

---

## `analysis.yaml` 是否需要更明确表达结论层级和置信度上限

**状态：** `decided`

### 背景

规范已有多假设、`validation_result` 和 `conclusion_summary`，但运行时仍可能在证据不足时给出过深的根因判断。需要区分现象级、影响级、机制级、根因级结论，并在证据不足时对置信度设上限。

k8s-project 案例说明：仅凭 Kubernetes 表层信号可以高置信说明 `mongod` 启动失败，但不应高置信说明 journal 损坏。

### 待决问题

- 结论层级是独立字段、嵌在 `conclusion_summary` 内，还是靠 `confidence` + `limitations` 间接表达？
- 置信度上限由规则引擎硬约束，还是 Agent 自律 + review 兜底？
- 假设级 `confidence` 与结论级 `confidence` 如何分工？
- 是否需要显式记录「当前证据允许下的最深结论层级」？

### 讨论记录

#### 2026-06-11 — 为什么需要显式结论层级

当前只有 `conclusion_summary.statement + confidence + limitations`，运行时容易出现两个问题：

- 结论文本已经下到了根因层，但 `limitations` 里才补一句“证据不足”；
- 假设层仍是 `insufficient`，最终结论却给出了过满的根因判断。

因此，结论层级不能只靠文字自觉，至少要在运行时显式表达“当前证据允许下到哪一层”。

#### 2026-06-11 — 建议的层级模型

本轮建议继续沿用背景文档里的四层划分：

- 现象级：哪个对象异常，异常表现是什么；
- 影响级：影响哪个拓扑单元或服务能力；
- 机制级：异常通过什么机制导致影响；
- 根因级：为什么发生。

对 MongoDB / Kubernetes 场景，可接受的典型收敛方式是：

- 只掌握 K8s 表层状态时，可高置信收敛到现象级，部分场景可到影响级。
- 拿到同伴视角、拓扑状态或关键内部查询后，才有机会推进到机制级。
- 拿到应用自身直接错误日志、明确配置/认证/存储错误等证据后，才应进入根因级。

#### 2026-06-11 — 第一版表达方式

第一版建议先把“最深可支持结论层级”作为 `conclusion_summary` 的可选扩展字段来讨论和试运行，而不是先改动全部模板基线。可采用类似：

- `deepest_supported_level`
  - `phenomenon`
  - `impact`
  - `mechanism`
  - `root_cause`

运行时约束建议为：

- `conclusion_summary.statement` 不应超过 `deepest_supported_level`。
- 若团队希望保留更深一层的“最可能解释”，应放在候选扩展字段或假设块里，而不是冒充当前已证实结论。
- `limitations` 继续说明为什么暂时不能再往下走。

#### 2026-06-11 — 置信度上限如何工作

`conclusion_summary.confidence` 应表达“对当前已报告结论”的置信度，而不是“对某个猜测根因”的主观把握。

因此第一版建议引入以下约束：

- 若只掌握 Pod runtime / event / readiness 等表层信号，则最多高置信到现象级或影响级。
- 若没有 peer `rs.status` 或等价拓扑内部状态证据，则副本集内部机制类结论不应高置信。
- 若没有足够直接的 mongod fatal log、termination detail 或等价应用内部证据，则进程内部根因不应高置信。
- 若存在未关闭的 `critical_gap`，则受影响结论层级必须降级，或保持低/中置信。

这里的关键是：**高置信只对当前层级成立，不自动外推到更深层级。**

#### 2026-06-11 — 假设级与结论级 confidence 分工

建议分工如下：

- 假设级 `confidence`
  - 用于表达某条假设当前相对更值得优先验证；
  - 只服务于第 4 段推理，不直接等于最终结论。
- 结论级 `conclusion_summary.confidence`
  - 只表达最终输出结论在其声明层级上的可信度；
  - 必须同时受证据充分性和 gap 分类约束。

也就是说，可以存在“某根因假设看起来最像”，但最终结论仍只能在机制级或影响级给出高置信。

#### 2026-06-11 — 约束方式

第一版不建议把所有场景都硬编码成规则引擎，但应对最容易过度外推的场景加少量硬约束，再由 Agent 和 review 补齐：

- 已知高风险场景使用明确 ceiling guardrails；
- 其余场景由 Agent 按 gap 和证据链自律；
- `review` 负责发现“证据不足仍高置信根因”的过程偏差。

### 结论

已决定在运行时显式表达结论层级，并为更深层结论设置置信度上限。第一版建议先把“最深可支持结论层级”作为 `conclusion_summary` 的可选扩展字段试运行，同时用少量 hard guardrails 限制最常见的过度外推场景；正式模板和 taxonomy 变更可在更多案例验证后再推进。

---

## `review` 是否需要加入过程偏差评分，而不只是结果质量评分

**状态：** `decided`

### 背景

`/midstack:review` 目前主要服务插件改进闭环。若只评价最终文本完整性，无法捕捉 answer-led bias、跳层取证、证据不足仍高置信根因等过程问题。k8s-project 四次过程对比说明，过程质量与结果文本质量可以分离。

### 待决问题

- 过程偏差项是固定清单还是按中间件/场景扩展？
- 评分写入 incident 的哪个块：`review` 子结构、独立 artifact，还是 meta？
- 过程偏差与结果质量是分开评分还是合成一个总分？
- 哪些偏差应触发「必须改进」vs「建议改进」？

### 讨论记录

#### 2026-06-11 — 为什么需要过程偏差视角

当前 `review` 已有五维评分原型：

- `evidence_completeness`
- `hypothesis_coverage`
- `validation_depth`
- `conclusion_confidence`
- `knowledge_reusability`

这套维度已经能覆盖结果质量，但仍不足以识别一些明显的过程问题，例如：

- 把用户线索或事后答案当成现场证据；
- answer-led bias；
- 从表层信号直接跳到深层根因；
- 证据不足却给出高置信根因；
- 明明存在关键 gap，却没有提出补采或下一步动作。

这些问题未必都会反映为“结果文本很差”，但会直接影响排障可靠性，因此应进入 review。

#### 2026-06-11 — 第一版不新增第二套总分

第一版不建议额外发明一套独立“过程总分”，否则会和现有五维评分并行，增加解释成本。

更稳的做法是：

- 保留现有五维评分作为主评分面；
- 额外引入“过程偏差检查清单”；
- 将发现的过程偏差映射到已有维度的 reason、overall reason、improvement suggestions 或 regression risks。

也就是说，过程偏差是**对现有 review 的强化解释层**，不是新的平行评分体系。

#### 2026-06-11 — 第一版建议检查的过程偏差

第一版建议至少检查以下偏差：

- `answer_led_bias`
  - 历史答案、用户披露、经验模式直接被写成现场结论。
- `surface_to_root_cause_jump`
  - 仅凭表层 K8s 现象就跳到进程内部或数据层根因。
- `missing_evidence_bridge`
  - 缺少从观测面到根因面的关键证据桥梁。
- `critical_gap_ignored`
  - 已有关键 gap，但未触发补采，也未限制结论层级。
- `overconfident_conclusion`
  - 假设仍 `insufficient` 或 gap 未关闭，却给出高置信结论。
- `missing_next_action`
  - 已知证据不足，但没有给出最有价值的下一步补采动作。

这些项可以先作为固定清单起步，后续再按中间件扩展。

#### 2026-06-11 — 与现有评分维度的映射

建议映射关系如下：

- `answer_led_bias`
  - 主要影响 `hypothesis_coverage`、`validation_depth`
- `surface_to_root_cause_jump`
  - 主要影响 `validation_depth`、`conclusion_confidence`
- `missing_evidence_bridge`
  - 主要影响 `evidence_completeness`、`validation_depth`
- `critical_gap_ignored`
  - 主要影响 `validation_depth`、`conclusion_confidence`
- `overconfident_conclusion`
  - 主要影响 `conclusion_confidence`
- `missing_next_action`
  - 主要影响 `knowledge_reusability`、`validation_depth`

这样第一版仍可复用现有 `review.template.yaml` 结构，不必立即改动评分 schema。

#### 2026-06-11 — 输出位置与使用方式

第一版仍建议把结果写入 `analysis.yaml.review`，不新建独立 artifact。

过程偏差的输出方式建议为：

- 在相关 score 维度的 `reason` 中体现；
- 在 `improvement_suggestions` 中给出明确修正建议；
- 对高风险偏差可写入 `regression_risks`。

如果后续发现偏差项需要结构化统计，再考虑是否新增 `review.process_findings` 一类扩展字段。

#### 2026-06-11 — 严重度建议

第一版可先做轻量分层：

- 必须改进
  - `answer_led_bias`
  - `critical_gap_ignored`
  - `overconfident_conclusion`
- 建议改进
  - `missing_evidence_bridge`
  - `surface_to_root_cause_jump`
  - `missing_next_action`

### 结论

已决定让 `review` 加入过程偏差检查，但第一版不新增第二套总分。现有五维评分继续作为主评分面，过程偏差通过固定检查清单映射到 score reasons、improvement suggestions 和 regression risks，并继续写入 `analysis.yaml.review`。

---

## 历史案例和知识资产如何进入第 4 段

**状态：** `decided`

### 背景

相似历史案例、用户事后答案、runbook/skill 都可以帮助生成假设和验证路径，但不能替代当前现场证据。k8s-project 过程 2 展示了 answer-led bias 的风险。需要明确知识资产在第 4 段的角色边界。

### 待决问题

- 历史案例作为假设来源、验证路径来源，还是仅作推荐参考资料——三者是否可同时存在？
- 用户线索在 `start` 阶段如何标记，避免在第 4 段被当成已证实证据？
- 知识资产匹配时机：第 4 段推理前检索，还是缺口出现后再推荐？
- 是否需要显式记录「哪些假设来自历史/知识，哪些来自当前证据」？

### 讨论记录

#### 2026-06-11 — 角色边界

历史案例、runbook、技能、用户线索、事后答案，都不应直接作为“当前现场证据”进入结论链。

第一版建议将它们的角色收敛为三类：

- 假设来源
  - 帮助提出“可能是什么”。
- 验证路径来源
  - 帮助提出“下一步该验证什么、该补采什么”。
- 推荐参考资料
  - 在输出里提示相关案例或 runbook，供人工复查。

其中前两类可以直接服务第 4 段，第 3 类更适合作为附加支持信息。

#### 2026-06-11 — 明确禁止的做法

以下做法应明确禁止：

- 因为历史案例高度相似，就把其根因写成当前根因；
- 因为用户事后披露了故障制作方式，就跳过当前现场取证；
- 因为 runbook 常见某类故障，就绕过当前证据桥梁直接下结论。

历史/知识资产的价值是**缩小搜索空间和提供验证路径**，不是替代当前 incident 的证据链。

#### 2026-06-11 — 建议的进入时机

第一版建议两个进入时机都保留，但角色不同：

1. 第 4 段初始推理前
   - 用于生成候选假设和候选验证路径；
   - 但不应提升任何假设的证据等级。
2. 发现关键 gap 后
   - 用于推荐更有针对性的补采 playbook；
   - 特别适合回答“下一步去哪补证据”。

对当前项目而言，第二种时机往往更有价值，因为它更接近 evidence-driven workflow，而不是 answer-led workflow。

#### 2026-06-11 — 来源标记

第一版建议在运行时至少做到软约束区分：

- 来自当前 incident 证据的判断；
- 来自历史案例或知识资产触发的假设；
- 来自用户线索的未证实信息。

即使暂时不新增正式字段，也应在 prompt、reasoning 任务单或 review 中要求 Agent 明确区分这些来源，避免混写。

后续若需要结构化，可考虑为假设补充类似：

- `source_type: evidence|history|user_clue|runbook`

但这不是第一版必须项。

#### 2026-06-11 — 与知识沉淀的关系

第 4 段引用历史案例和知识资产，不等于直接沉淀新知识。

只有在当前 incident 完成排障后，且证据链足够清楚时，才应通过：

- `knowledge_candidates`
- 后续 `/midstack:review`

来判断是否形成新的 runbook、command、script、skill 或资产更新候选。

也就是说：

- 历史知识进入第 4 段，是为了帮助当前推理；
- `knowledge_candidates` 进入第 5 段，是为了沉淀这次新经验。

### 结论

已决定让历史案例和知识资产进入第 4 段，但角色仅限于假设来源、验证路径来源和推荐参考资料，不能直接充当当前现场证据。第一版优先以软约束要求 Agent 区分“当前证据”“历史触发假设”“用户线索”，并在关键 gap 出现后优先用知识资产推荐补采路径，而不是直接替代结论。
