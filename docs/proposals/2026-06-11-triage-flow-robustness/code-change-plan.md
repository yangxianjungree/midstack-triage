---
status: draft
last_updated: 2026-06-11
supersedes: none
superseded_by: none
---

# 2026-06-11 排障小循环实施计划

本文件承接 [`context.md`](./context.md) 和 [`discussions.md`](./discussions.md) 中已收敛的结论，记录从当前实现演进到“单次 analyse 内部多假设 + 一轮定向补采小循环”的执行顺序。

本文件是过程性执行计划，不替代 L1。L1 事实源仍以 `docs/specs/`、`core/templates/`、`core/models/`、`core/taxonomies/` 为准。

## 基线

- 用户侧主路径仍是一次 `/midstack:analyse`
- 第一版只做最多 1 轮定向补采，不做多轮自动编排
- 第一版优先用 soft constraints 跑通语义，再决定是否升级为模板或 taxonomy 变更
- 代码改动按“小步可验证”推进；每一轮都要有对应 smoke、replay 或 review 验证

## 当前实现入口

当前最直接相关的入口包括：

- `tools/plugin/midstack-local.py`
  - 生成 `analysis.rule-draft.yaml`
  - 生成 `agent-reasoning-task.md`
  - 写 `analysis.yaml.review`
- `plugins/cursor/mcp-server.py`
  - 暴露 `midstack_analyse_reasoning`
  - 将 `agent-reasoning-task.md` 交给 Agent
- `domains/mongodb/scripts/collect/`
  - 当前已存在 `collect-logs-current.sh`
  - 当前已存在 `collect-logs-previous.sh`
  - 当前已存在 `collect-replicaset-rs-status.sh`
  - 尚未有“应用日志源定位”类 playbook

## 非目标

以下内容不作为本轮第一优先级：

- 直接实现通用多轮自动编排器
- 让 Agent 自由执行任意 shell 补采
- 在未验证前大改 `analysis.template.yaml` 或 taxonomy
- 把历史案例检索做成复杂推荐系统

## 第一轮：推理合同和任务单收敛

目标：先让第 4/5 段的 Agent 合同显式表达这次已决定的运行时原则，即便 runtime 还没进入自动补采。

重点：

- `agent-reasoning-task.md` 明确要求：
  - 维护多条候选假设
  - 区分 `expected_gap` / `critical_gap`
  - 显式限制结论层级和置信度
  - 区分当前证据、历史触发假设、用户线索
  - 在证据不足时给出高价值 `next_actions`
- `midstack_analyse_reasoning` prompt 文案同步更新
- Cursor command / rule 文案同步更新，避免 Agent 继续按一次性串行思路写 `analysis.yaml`

优先文件：

- `tools/plugin/midstack-local.py`
- `plugins/cursor/mcp-server.py`
- `plugins/cursor/commands/midstack:analyse.md`
- `plugins/cursor/rules/midstack-triage.mdc`

验证：

- Cursor MCP smoke
- 生成的 `agent-reasoning-task.md` 包含新约束
- sandbox / fixture 中 `analysis.yaml` 结构仍可被现有 review 和 finalize 消费

## 第二轮：review 过程偏差检查

目标：在不新增第二套总分的前提下，让 `/midstack:review` 能识别过程偏差，而不只看结果完整度。

重点：

- 为当前 review 评分增加过程偏差检查：
  - `answer_led_bias`
  - `surface_to_root_cause_jump`
  - `missing_evidence_bridge`
  - `critical_gap_ignored`
  - `overconfident_conclusion`
  - `missing_next_action`
- 将过程偏差映射到现有五维评分的 `reason`
- 将高风险偏差写入 `regression_risks`
- 将修正建议写入 `improvement_suggestions`

优先文件：

- `tools/plugin/midstack-local.py`
- `core/templates/review.template.yaml` only if existing structure proves insufficient

验证：

- 本地 `review` smoke
- fixture / baseline incident 的 review 输出对比
- `analysis.yaml.review` 仍符合现有消费路径

## 第三轮：MongoDB 白名单补采 playbook

目标：先把最有价值、最稳定的定向补采动作整理成固定 playbook，而不是直接上通用补采框架。

第一批 playbook：

- replica set `rs.status` peer fallback
- `kubectl logs --previous`
- 健康 peer / 同伴视角连接验证
- `discover_log_sink`
  - 确认应用日志是 stdout/stderr 还是 file
  - 若是 file，确认是否回链 stdout
  - 若不是，继续追卷或节点侧真实文件

对 MongoDB 的最小目标：

- 故障 Pod 无法提供自身 `rs.status` 时，优先尝试健康 peer
- `kubectl logs` 很短时，不直接猜根因，而是触发 `discover_log_sink`
- 将 playbook 结果回写为可被 Agent 理解的 artifact 和 gap 提示

优先文件：

- `domains/mongodb/scripts/collect/collect-replicaset-rs-status.sh`
- `domains/mongodb/scripts/collect/collect-logs-previous.sh`
- `domains/mongodb/scripts/collect/collect-logs-current.sh`
- `domains/mongodb/scripts/collect/` 下新增 `discover-log-sink` 类脚本或等价收集器
- runtime map / executor 相关装配代码

验证：

- MongoDB script validator
- fake / fixture 场景下的 artifact 输出检查
- 至少一个可复现“日志很短”的案例回归

## 第四轮：gap 分类和结论 ceiling 落地

目标：先让 runtime 和 Agent 输出都能稳定表达 `expected_gap` / `critical_gap` 以及结论层级上限，再考虑是否升级 schema。

重点：

- `collection_report.evidence_gaps` 增加运行时约定：
  - 哪些 gap 是 `expected_gap`
  - 哪些 gap 是 `critical_gap`
  - gap 对哪条假设或哪一层结论有影响
- `analysis.yaml` 运行时增加“最深可支持结论层级”的表达
- 对最容易过度外推的场景加少量 hard guardrails：
  - 无 peer `rs.status` 时限制副本集内部机制类高置信结论
  - 无直接 fatal log / termination detail 时限制进程内部根因高置信结论
  - 未关闭 `critical_gap` 时限制根因级高置信结论

优先文件：

- `tools/plugin/midstack-local.py`
- Agent reasoning task / prompt 相关入口
- 必要时补充 replay comparison / score 工具

验证：

- 旧 fixture 不因新增软字段而崩溃
- review 能识别过度外推
- 案例回归中不再出现“gap 未关闭仍高置信根因”

## 第五轮：单次 analyse 内一轮小循环

目标：在已有 playbook、gap 分类和结论 ceiling 都跑通后，再实现最小 runtime 小循环。

最小闭环：

1. 初始固定采集
2. 规则草稿 + Agent 初判
3. 判断是否满足补采门禁
4. 若满足，则执行最多 1 轮、2 到 3 个白名单只读动作
5. merge 新 artifact / gap / signal
6. Agent 继续收敛并 finalize

实现约束：

- 不做通用多轮调度器
- 不开放任意 shell
- 超过时间预算即停止
- 失败时允许阶段性结论，而不是把 analyse 标成整体失败

优先文件：

- `tools/plugin/midstack-local.py`
- `tools/remote-executor/`
- `plugins/cursor/mcp-server.py`
- incident artifact merge 相关逻辑

验证：

- 本地 `analyse` smoke
- Cursor MCP smoke
- freeze / replay 回归
- 至少一个定向补采成功案例
- 至少一个“证据不足但正确止步”的案例

## 第六轮：L1 升级和稳定化

目标：只有在前几轮语义稳定、案例验证通过后，再把 soft constraints 升级为正式 L1 结构。

候选升级项：

- `analysis.template.yaml`
  - 是否纳入 `deepest_supported_level`
- `collection_report` / taxonomy
  - 是否纳入 gap 类型枚举
- `review.template.yaml`
  - 是否需要结构化 `process_findings`

升级前提：

- 至少多个真实或冻结案例复用
- replay / score 工具能稳定消费
- 不引入与现有 incident 兼容性冲突的迁移成本

## 建议实施顺序

建议按以下顺序推进：

1. 第一轮：推理合同和任务单收敛
2. 第二轮：review 过程偏差检查
3. 第三轮：MongoDB 白名单补采 playbook
4. 第四轮：gap 分类和结论 ceiling 落地
5. 第五轮：单次 analyse 内一轮小循环
6. 第六轮：L1 升级和稳定化

这个顺序的目的，是先把“怎么想、怎么写、怎么评估”跑通，再把“怎么自动补采”落进 runtime。
