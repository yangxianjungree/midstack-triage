---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 2026-06-10 代码模块修改计划

本文件记录本轮从当前 L1 文档对齐到代码整改的执行顺序。

## 基线

- L1 事实源优先级最高：`docs/specs/`、`core/models/`、`core/templates/`、`core/taxonomies/`
- 本目录只记录过程、待确认点和执行计划，不替代 L1
- 代码修改小步推进，每步都要能用 smoke、replay 或 validator 验证
- 有分歧的实现点先回到 `proposal.md` 和 `todo.md` 记录，再决定是否改代码

## 第一轮：命令输出和 incident 生命周期

目标：先修正和 L1 明确冲突、且不依赖 Agent 推理方案选择的运行时问题。

- `incident_id` 增加 `rand4`
- `customer_clue` 改为可选输入
- `start` 创建 incident 时写入更完整的 `meta.yaml`
- `start` 和 `analyse` 的 blocked 场景返回结构化 adapter output
- `analyse` 读取 `meta.yaml` 并校验 incident 状态
- `analyse` 执行时更新 `analysing / analysed` 状态
- MCP 返回 adapter output 摘要，避免只返回路径文本

验证：

- 本地 `start` / `analyse` smoke
- adapter output schema 校验
- Cursor MCP smoke

## 第二轮：冻结输入和 current incident

目标：让 `/start` 到 `/analyse` 的记录延续行为符合 L1。

- `analyse` 不静默覆盖 `/start` 生成的 `input.yaml`
- 如需补充采集输入，另存采集上下文或 remote run 引用，不改基础输入
- 无 current incident 或状态不满足时，返回 `blocked`
- 明确最近 `start` 和最近 `analyse` 完成记录的默认命中逻辑

验证：

- 基于 `/start` 生成 incident 后执行 `/analyse`
- 对 blocked/current 缺失场景做本地 smoke
- fixture replay 不受影响

## 第三轮：review 落点对齐

目标：让 `review` 输出落点符合 `incident-record.spec.md` 和 `review.template.yaml`。

- `review` 从单独 `review.yaml` 迁移到 `analysis.yaml.review`
- `review` adapter output 的 `record_refs` 指向 `analysis.yaml` 的 review block
- 更新 Cursor smoke 和 sandbox 测试，不再要求 `review.yaml`
- 如 fixture 或 score 工具依赖 `review.yaml`，同步改为读取 `analysis.yaml.review`

验证：

- 本地 `review` smoke
- Cursor MCP smoke
- adapter output schema 校验

## 第三点五轮：`/start` 对象盘点轻量增强

目标：补齐 `/start` 第 2 段可以安全完成的只读对象盘点，但不把 `/start` 扩展成第 3 段采集执行器。

- `object-inventory.yaml` 为 Pod / StatefulSet / Service 增加 MongoDB role hints 和部署架构 hints
- 在 namespace 已确认时生成 `targets`：`statefulset_refs`、`service_refs`、`pod_refs`、`node_refs`、`mongos_pod_ref`
- 补充相关 Node 摘要和相关 Kubernetes Event 摘要
- 补充 `topology_hints` 和 `deployment_architecture_candidates`
- 不在 `/start` 执行 `rs.status()`、日志采集或 MongoDB shell 命令
- `/start` 识别出的 `targets`、部署架构和拓扑线索已接入当前 analyse 远程采集 context 生成逻辑
- 当前已切出 `tools/remote-executor/` 作为正式执行入口，`remote-smoke.py` 只保留兼容 smoke 包装

验证：

- 本地语法检查
- `start` blocked smoke
- fake kubectl inventory smoke
- 仓库 validator

## 第四轮：remote executor 与 runtime map

目标：把当前 remote executor 入口、runtime map 查找和兼容 smoke 包装边界拆清楚。

- 将 `remote-smoke.py` 收敛为兼容 smoke 包装入口
- 若保留为 MVP 执行器，按 remote executor 请求 / 结果模型补齐输出边界
- 通过 `script-runtime-map.yaml` 查找脚本运行路径，减少硬编码
- 统一错误分类和 blocked / failed 语义
- remote run 转 incident 时保留执行层 request/result、stdout/stderr 和 artifacts，避免 incident 丢失执行证据

验证：

- MongoDB remote smoke
- 远程结果目录转 incident
- fixture freeze / replay

## 第五轮：Agent 推理层

目标：补齐“第 3 段证据包之后”的第 4 段 Agent 推理编排边界。

当前确认采用方案 C：

- 保留规则 runner 的稳定回归价值
- 让 Agent 只消费第 3 段整理后的证据包、证据缺口和 artifact 引用
- 避免直接把全量原始日志交给模型
- 保留未来适配不同 Agent 平台的空间
- `analyse` 成功后额外落 `analysis.rule-draft.yaml` 和 `agent-reasoning-task.md`
- Cursor Agent 按任务单继续回填正式 `analysis.yaml` 与 `report.md`

进入下一步代码前，应先参考：

- [2026-06-10 推理分析流程复盘](2026-06-10-reasoning-flow-review.md)

其中已额外确认：

- 第 3/4 段后续应优先评估“小循环”而不是严格单向串行
- MongoDB 内部查询目标应逐步收敛到“拓扑单元 + 候选健康执行点”
- 根因级结论需要更明确的证据充分性和置信度上限约束

验证：

- 固定 fixture 下的推理输出可检查
- score comparison 能识别推理质量变化
- review score 能反映证据完整度、假设覆盖和验证深度

## 第六轮：文档和状态回写

目标：代码验证完成后，再同步稳定文档。

- 如需改变命令行为，先更新 `docs/specs/plugin-runtime.spec.md`
- 如需改变 incident 文件职责，先更新 `docs/specs/incident-record.spec.md`
- 如需改变字段、模板或枚举，先更新 `core/models/`、`core/templates/` 或 `core/taxonomies/`
- 已完成和已验证内容写入 `docs/project/implementation-status.md`
- 未完成内容写入 `docs/project/todo.md`
