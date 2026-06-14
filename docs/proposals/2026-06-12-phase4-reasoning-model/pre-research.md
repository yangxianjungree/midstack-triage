---
status: draft
last_updated: 2026-06-12
type: external-landscape-research
related_spec: ./spec.md
---

# 第 4 段推理模型 — 外部实践预研

本文件汇总大厂产品、开源项目与方法论中，与「多假设 + 推理 + 验证 + 并行」相关的实现方式，供 midstack-triage 第 4 段统一模型时参考。

**预研问题：** 业界如何实现多假设推理？并行时是否共享信息？与 midstack 现有设计如何对齐？

---

## 1. 跨行业共识模式

几乎所有成熟方案都**不是**「读一遍证据 → 给一个结论」，而是下面这个内核（名称各异）：

| 模式名 | 代表 | 步骤 |
|--------|------|------|
| **O-R-A 循环** | [Datadog Bits Investigation](https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/) | Observation → Reasoning → Action，循环直到收敛或 inconclusive |
| **假设-演绎法** | [Google SRE Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/) | 观察 → 形成可证伪假设 → 设计实验/查询 → 支持或否定 → 重复 |
| **假设驱动 RCA** | [Azure SRE Agent](https://learn.microsoft.com/en-us/azure/sre-agent/root-cause-analysis) | 收集上下文 → 形成假设 → 逐条验证 → 输出证据链 |
| **Plan-Execute-Reflect** | [AWS OpenSearch Investigation Agent](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/application-investigation-agent.html) | 规划 → 执行查询/分析 → 反思 → 多步 workflow |
| **Agentic Loop** | [HolmesGPT](https://github.com/HolmesGPT/holmesgpt) | LLM 推理 ↔ 并行 tool 调用 ↔ 状态合成，直到终止条件 |

**对 midstack 的含义：** 第 4 段「推理诊断与深入验证」在业界对应的是 **O-R-A 循环 + 假设组合管理**，而不是单次 LLM 填空。我们文档里的「多轮」应明确写成 **Evidence Loop 轮次**，避免与「多假设数据结构并行」混淆。

---

## 2. 大厂产品对照

### 2.1 Datadog Bits AI SRE — 最接近你设想的「并行假设树」

来源：[Investigate Issues 文档](https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/)、[产品博客](https://www.datadoghq.com/blog/bits-ai-sre/)

**流程：**

1. 告警触发后自动拉上下文（runbook、历史调查、telemetry）
2. **动态生成多条根因假设**
3. **并发验证各假设**（官方表述：*verify each one concurrently*、*hypothesis tree*）
4. 每条假设分类为 validated / invalidated / inconclusive
5. 展示 **Agent Trace**（逐步推理）+ **Investigation 树状视图**（调查路径）

**信息共享：** 强共享。官方强调 *each step builds on prior findings*；树状结构表示分支共享上游证据、在分叉点各自深入。

**并行形态：** 假设树的多分支**同时推进**（不是仅最终输出里并列几条 hypothesis 文本）。

**可借鉴：**

- 假设树 UI/数据结构（父证据 → 子假设 → 验证动作）
- Agent Trace 作为第 4 段过程 artifact（对应我们的 `agent-reasoning-task` / 未来 `reasoning-board`）
- inconclusive 作为一等公民收尾

### 2.2 AWS DevOps Agent — 多假设 + 正反证 + Investigation Journal

来源：[AWS DevOps Blog](https://aws.amazon.com/blogs/devops/how-aws-devops-agent-uses-multi-agent-reasoning-to-find-root-causes/)

**架构分层：**

- **Topology Graph**：全局架构上下文（依赖、部署、运行时关系）
- **Triage**：快速关联告警（速度优先）
- **Investigation**：深度推理引擎（**并行生成竞争假设 + 正反证验证**）
- **Mitigation / Prevention**：修复建议与模式沉淀
- **Investigation Journal**：全程不可变审计轨迹

**Investigation 内步骤：**

1. Context acquisition（影响面 + 近期变更）
2. 宽网证据采集（metrics baseline、logs、traces、配置、时间线）
3. **同时生成多个竞争理论**（模式匹配、异常检测、部署关联、上下游、资源约束）
4. **并行验证**，每条假设同时找支持证据和反证
5. 区分 cause vs root cause；无法区分时显式标 ambiguous

**案例（checkout 延迟）：** 三个假设（配置变更、支付网关慢、连接池满）**同时检查**；前两个被反证排除，第三个与 onset 时间一致且无矛盾 → root cause。

**可借鉴：**

- **共享 Journal + 拓扑图** ≈ 我们的 `structured_record` + `signal_bundle` + 未来 reasoning board
- **反证优先**（explicitly challenge each hypothesis）— 与 Google SRE 一致
- 人类可随时 natural language steer，journal 记录 steer 影响

### 2.3 Azure SRE Agent — 串行假设验证 + 历史召回

来源：[Root Cause Analysis 文档](https://learn.microsoft.com/en-us/azure/sre-agent/root-cause-analysis)

**流程：** 收集上下文 → 形成假设 → **逐条**系统验证 → 输出带引用的推理链。

文档示例为 **顺序** 否定 H1、H2，再 validate H3（非并行树）。

**可借鉴：**

- 假设块的可读输出格式（INVALIDATED / VALIDATED）
- 「召回相似 incident」作为正式步骤（对应我们的历史案例 / knowledge assets）
- 强调 *evidence trail not in your head*

### 2.4 Amazon OpenSearch Investigation Agent — 结构化假设 + 人工 Accept/Rule out

来源：[Investigation Agent 文档](https://docs.aws.amazon.com/opensearch-service/latest/developerguide/application-investigation-agent.html)

**流程：** 目标驱动 deep research → 多步 plan/execute/reflect → 输出 **按 likelihood 排序的假设列表**，每条带 data evidence。

**人机协作：** 用户可对主假设或备选假设 **Accept** 或 **Rule out**；可 **Reinvestigate** 并带入已有假设与 findings。

**可借鉴：**

- `validation_result` 与人工 `Accept`/`Rule out` 的对应关系
- Reinvestigate = 我们的「定向补采 + 再推理」产品化表达

### 2.5 PagerDuty — 历史模式，非 Agent 推理

来源：[Probable Origin](https://support.pagerduty.com/main/docs/probable-origin)、[Related Incidents](https://support.pagerduty.com/main/docs/related-incidents)

**定位：** 用 6 个月历史模式推断 **probable origin**（数据科学排序），**不声称给出 root cause**。

**与第 4 段关系：** 属于 **假设来源 / 范围收敛**，不是验证引擎。对应 midstack 中 scenario 路由、历史案例检索 — **不能替代当前现场证据**（我们已收敛的原则与 PagerDuty 官方表述一致）。

**Post-incident 视角：** [Howie 分析指南](https://howie-guide.pagerduty.com/analyze/) 强调在时间线中标注「何时提出/证伪假设、谁提出、谁证伪」— 对 review 与知识沉淀有参考价值。

### 2.6 Google SRE — 方法论基线（非产品实现）

来源：[Effective Troubleshooting](https://sre.google/sre-book/effective-troubleshooting/)、[GCP Troubleshooting Tips](https://cloud.google.com/blog/products/gcp/troubleshooting-tips-help-your-cloud-provider-help-you)

**要点：**

- 假设-演绎法；优先 **falsify** 而非只找支持证据
- 长问题用 **共享摘要文档** 维护「仍可能 / 已排除」假设列表，避免重复劳动
- 复杂多团队场景可用 Kepner-Tregoe IS/IS NOT（与单 Agent 流水线正交）

**对并行的态度：** 方法论层面是「多假设并存、有序淘汰」，**未规定**必须机器并行；但强调同时维护多条候选、记录证伪路径。

---

## 3. 开源项目对照

### 3.1 HolmesGPT（CNCF Sandbox）— 单 Agent 循环 + 并行 Tool

仓库：[HolmesGPT/holmesgpt](https://github.com/HolmesGPT/holmesgpt)

**架构：**

- 中心 `ToolCallingLLM` **agentic loop**（推理 → 工具 → 合成 → 再推理）
- **多工具并行执行**（ThreadPoolExecutor，最多 16 workers）
- Prompt 强制 **多阶段调查**：Phase 1 → STOP & Evaluate → Phase 2… → Mandatory Final Review
- TodoWrite 任务列表；独立任务要求并行执行

**并行层次：**

| 层次 | 是否并行 |
|------|----------|
| 多条假设各自独立 Agent | 否（单 LLM 上下文） |
| 同一轮多个 tool 调用 | 是 |
| 多阶段调查 phase | 否（顺序），但 phase 内可并行 tool |

**可借鉴：** 在 **不引入多 Agent** 的前提下，第 4 段可先做到「单推理轨 + 并行只读采集/查询」；Investigation Procedure 的 phase gate 可写入 `agent-reasoning-task.md`。

### 3.2 Siclaw — 显式 4 阶段 + 并行验证（只读）

文档：[Deep Investigation](https://docs.siclaw.ai/features/deep-investigation)、[GitHub](https://github.com/scitix/siclaw)

**流程（DP 模式）：**

1. 证据收集 / triage
2. 提出 2–5 条排序假设（用户可确认/调整/跳过）
3. **最多 3 个子 Agent 并行验证**（每条假设一轨）
4. 合成报告（根因、置信度、因果链、remediation）

**信息共享 — 重要反例：**

- 早期文档曾写子 Agent **不共享信息**以防确认偏误
- 较新文档改为 **same-agent delegation** 收集 evidence capsules，再由主 Agent 合成
- Investigation Memory：历史调查注入假设生成与验证（[PR #74](https://github.com/scitix/siclaw/pull/74) 三层 prior knowledge）

**可借鉴：**

- 只读默认 + 显式 DP 模式触发（对应我们的 `/midstack:analyse` 内部分支）
- 用户确认假设后再并行验证（human-in-the-loop gate）
- **并行验证 vs 信息共享是设计权衡**，不是非黑即白

### 3.3 Aurora / IncidentFox — LangGraph 编排

仓库：[Arvo-AI/aurora](https://github.com/Arvo-AI/aurora)、[incidentfox/incidentfox](https://github.com/incidentfox/incidentfox)

**模式：** 告警 webhook → LangGraph 状态机 → 动态选 30+ 工具 → RCA 报告。

**并行：** 框架层支持图分支并行；具体是否按假设分轨取决于 graph 设计（公开文档偏「单调查流」而非 Datadog 式假设树）。

**可借鉴：** 若 midstack 未来要做 **runner 侧编排**（定向补采、多步），LangGraph 类 state + reducer 是业界默认选项（见 [LangGraph 文档](https://github.com/langchain-ai/langgraph)）。

### 3.4 PostMortem.ai — 对抗式多 Specialist

仓库：[tazwaryayyyy/PostMortem-ai](https://github.com/tazwaryayyyy/PostMortem-ai)

**模式：** Hypothesis / Evidence / RootCause / **Critic**（独立模型族）/ Report / Vision — 流式共享 state，Critic **主动找洞**。

**可借鉴：** 「并行 + 信息共享」的一种实现是 **对抗合并**而非「各轨独立写结论」；适合高价值、低频次疑难 case，成本高。

### 3.5 Multi-agent-RCA-project — 辩论 + Judge 多轮

仓库：[ZamoRzgar/Multi-agent-RCA-project](https://github.com/ZamoRzgar/Multi-agent-RCA-project)

**模式：** Log / KG / Hybrid 三个 Reasoner 出竞争假设 → Judge 打分 → 最多 3 轮 refine。

**可借鉴：** 学术化「多视角 + 裁判」；与 midstack review 五维评分有结构相似性。

### 3.6 agentm — 假设驱动 Orchestrator + Worker

PyPI：[agentm](https://pypi.org/project/agentm/)

**模式：** Orchestrator 维护 hypothesis 集合，dispatch scout/verify/deep_analyze 子 Agent，更新/删除假设，输出 CausalGraph。

**可借鉴：** 与我们在 `spec.md` 中 **方案 B（分轨 + 黑板合并）** 几乎同构；开源验证了这一 API 形状的可行性。

---

## 4. 并行与信息共享：三种主流架构

| 架构 | 代表 | 并行什么 | 如何共享 | 优点 | 缺点 |
|------|------|----------|----------|------|------|
| **A. 单 Agent 循环 + 并行 Tool** | HolmesGPT、Azure（偏此） | 工具/查询 | 单上下文自动共享 | 成本低、实现简单 | 易锚定第一个 plausible 假设 |
| **B. 假设树 / 多轨并行 + 共享黑板** | Datadog Bits、AWS DevOps Agent | 假设分支 | Journal / 树节点 / 共享 state | 反锚定强、路径可追溯 | 编排与 merge 复杂 |
| **C. 隔离并行 + 末端合成** | Siclaw（早期） | 假设验证 | 验证期不共享，最后 merge | 降低确认偏误 | 轨间无法互补反证，可能重复劳动 |
| **D. 对抗辩论** | PostMortem.ai、Multi-agent-RCA | 角色并行 | Message + shared state | 强迫质疑 | Token 成本最高 |

**你的设想（多假设流水线并行 + 信息共享互补）** 在业界主要对应 **B**，Datadog 与 AWS 的公开描述最接近；**不是** Siclaw 早期的隔离验证。

**推荐组合（务实）：**

- **默认：** A（单 Agent + 并行只读 tool/补采）+ 结构化多假设输出
- **升级路径：** B 的简化版 — 2–3 条 top 假设分轨，写入 `reasoning-board.yaml`，Lead 合并到 `analysis.yaml`
- **可选实验：** D 仅用于 fixture 回归或人工触发的「疑难模式」

---

## 5. 「深入验证」在业界的含义

| 来源 | 「深入」指什么 |
|------|----------------|
| Datadog | 沿假设树向下 drill（更多 telemetry 查询），非默认代码分析 |
| AWS | Investigation 阶段相对 Triage 的深度；Mitigation 分离 |
| OpenSearch | Reinvestigate、更深 dataset |
| midstack `presentation.md` | 代码级 / 专家级 **条件分支** |
| midstack `triage-workflow.spec.md` | 当前 MVP **明确不纳入**代码路径分析 |

**统一建议：**

- 段名保留「推理诊断与**深入验证**」
- 规范正文拆为：
  - **假设验证**（默认）：`validation_actions` / `validation_result`
  - **深入分支**（可选）：代码/专家路径，条件触发

避免用「深入验证」同时指段名、字段名和代码分析分支。

---

## 6. 与 midstack-triage 现状的差距

| 能力 | 业界常见 | midstack 现状 |
|------|----------|---------------|
| O-R-A / 证据循环 | 标准 | 规则定向补采有；**Agent 后再补采**未闭环 |
| 多假设数据结构 | 标准 | ✅ `analysis.yaml` + 合同 |
| 假设级并行执行 | Datadog/AWS/Siclaw DP | ❌ 单次 Agent |
| 共享推理黑板 | AWS Journal、Datadog Trace | ❌ 仅 `agent-reasoning-task.md` |
| 假设树 / 因果链可视化 | Datadog | ❌ |
| 历史作为假设来源 | 广泛 | 原则有；检索 MVP 弱 |
| 人工 Accept/Rule out | OpenSearch | 部分（review/finalize） |
| 只读 + 白名单补采 | Siclaw、我们 | ✅ 已收敛并实现 runner 侧 |

---

## 7. 预研结论（供讨论）

1. **你的设想有业界对标**，且大厂方向一致：**多竞争假设 + 并行验证 + 共享证据状态 + 反证优先**（Datadog、AWS 表述最清晰）。

2. **「统一术语」应先于「上并行」**：业界也把 *parallel hypotheses*（数据结构）、*parallel investigation branches*（执行）、*multi-round loop*（时间）分开讲；我们 spec 里的四层（Portfolio / Loop / Branch / Orchestration）与外部实践对齐。

3. **信息共享不是唯一正确答案**：Siclaw 用隔离防偏误；AWS/Datadog 用共享 Journal 防重复和锚定。midstack 更适合 **共享黑板 + 显式 cross_hypothesis_notes（反证传递）**，因为我们证据包已是共享的，隔离轨反而浪费补采。

4. **最小可行演进（不改 slash 命令）：**
   - Phase 1：文档统一 + `agent-reasoning-task` 增加「假设组合 / 证据循环」显式步骤
   - Phase 2：单 Agent 内并行只读 validation（HolmesGPT 式）
   - Phase 3：2–3 假设分轨 + `reasoning-board.yaml` + Lead merge（agentm / 方案 B）
   - Phase 4：评估是否要做 Datadog 式假设树 artifact

5. **不建议第一版照搬：** PostMortem 式全对抗多 Agent（成本）、LangGraph 全量编排（runner 复杂度过早）、PagerDuty 式「历史即结论」。

---

## 8. 参考链接索引

### 大厂 / 官方

- Google SRE Troubleshooting: https://sre.google/sre-book/effective-troubleshooting/
- Azure SRE Agent RCA: https://learn.microsoft.com/en-us/azure/sre-agent/root-cause-analysis
- AWS OpenSearch Investigation Agent: https://docs.aws.amazon.com/opensearch-service/latest/developerguide/application-investigation-agent.html
- AWS DevOps Agent multi-agent reasoning: https://aws.amazon.com/blogs/devops/how-aws-devops-agent-uses-multi-agent-reasoning-to-find-root-causes/
- Datadog Bits Investigate Issues: https://docs.datadoghq.com/bits_ai/bits_ai_sre/investigate_issues/
- Datadog Bits AI SRE blog: https://www.datadoghq.com/blog/bits-ai-sre/
- PagerDuty Probable Origin: https://support.pagerduty.com/main/docs/probable-origin

### 开源

- HolmesGPT: https://github.com/HolmesGPT/holmesgpt
- Siclaw: https://github.com/scitix/siclaw — https://docs.siclaw.ai/features/deep-investigation
- Aurora: https://github.com/Arvo-AI/aurora
- IncidentFox: https://github.com/incidentfox/incidentfox
- PostMortem.ai: https://github.com/tazwaryayyyy/PostMortem-ai
- Multi-agent-RCA: https://github.com/ZamoRzgar/Multi-agent-RCA-project
- agentm: https://pypi.org/project/agentm/
- LangGraph: https://github.com/langchain-ai/langgraph

### 仓库内已有

- `docs/references.md`
- `references/orchestration-patterns.md`（竞争假设调试 ↔ Agent Teams 范例）
- `docs/proposals/2026-06-11-triage-flow-robustness/discussions.md`（单次 analyse 小循环决策）
