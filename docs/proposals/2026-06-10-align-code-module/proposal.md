---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 2026-06-10 代码模块按当前 L1 文档对齐提案

## 背景

本提案记录当前代码实现与最新文档结构之间的偏差，用于后续代码整改前确认边界。

本文是过程性提案，不是事实源。事实源以 `docs/specs/`、`core/models/`、`core/templates/`、`core/taxonomies/` 为准；历史讨论位于 `docs/decisions/`，不作为当前实现裁决依据。

相关过程讨论：

- [2026-06-10 推理分析流程复盘](2026-06-10-reasoning-flow-review.md)

## 变更类型

本轮对齐可能影响：

- 插件命令行为
- adapter output 语义
- incident 生命周期状态机
- 当前目标记录选择
- incident 输入冻结策略
- `review` 输出落点
- remote executor 与脚本 runtime map
- 第 4 段 Agent 推理边界

## 当前文档基线

- 文档裁决入口为 `docs/README.md`
- 命令行为、状态机、目标记录选择以 `docs/specs/plugin-runtime.spec.md` 为准
- incident 目录结构和文件职责以 `docs/specs/incident-record.spec.md` 为准
- `analyse` 第一版能力边界以 `docs/specs/analyse-mvp.spec.md` 为准
- 命令对外使用方式以 `docs/specs/plugin-usage.spec.md` 为准
- 字段结构、模板和枚举以 `core/models/`、`core/templates/`、`core/taxonomies/` 为准

## 当前真实代码链路

1. Cursor 命令入口位于 `plugins/cursor/commands/` 和 `plugins/cursor/rules/`
2. MCP server 位于 `plugins/cursor/mcp-server.py`
3. 本地命令原型位于 `tools/plugin/midstack-local.py`
4. 真实远程只读采集当前通过 `tools/remote-executor/mongodb-executor.py` 调度，`tools/remote-smoke/mongodb-smoke.py` 仅保留兼容 smoke 包装入口
5. MongoDB 第 3 段脚本源位于 `domains/mongodb/scripts/`
6. 脚本输出通过 `tools/lib/patch_merge.py` 合并为 incident 三类记录
7. 第 4、5 段当前由 `tools/analyse/mongodb-analyse.py` 先生成规则保底草稿，Cursor Agent 再基于 incident 证据包继续回填正式 `analysis.yaml`
8. `review` 当前写入 `analysis.yaml.review`，并生成 `review-adapter-output.yaml`

## 已对齐项

- 对外主路径仍是 `/midstack:start`、`/midstack:analyse`、`/midstack:review`
- `midstack_validate` 作为工程自检入口，不属于用户排障主路径
- MongoDB MVP 第 3 段脚本清单已包含 11 个脚本
- 脚本调用合同已采用 `--context-file`、`--output-file`、`--artifact-dir`
- `analyse` 能消费 fixture、incident、remote run 或 remote config，并生成 `analysis.yaml` 与 `report.md`
- `review` 当前已经是五维评分原型，adapter output 使用 `completed`，不再使用 `awaiting_human_feedback`

## 本轮已处理

- `incident_id` 已按 L1 调整为 `<middleware>-<YYYYMMDD>-<HHMMSS>-<rand4>`
- `/midstack:start` 的 `customer_clue` 已改为高价值可选输入，缺失时不再构成 `blocked`
- `start` / `analyse` 的阻塞场景已统一为结构化 adapter output，并以成功命令调用返回
- MCP tool call 已优先返回 adapter output 摘要，而不是只返回本地路径文本
- `analyse` 已读取 `meta.yaml` 校验 incident 状态，只有 `ready` 或 `analysed` 可进入分析
- 无 current incident、incident 不存在、状态不满足或缺 `remote-config.yaml` 时，`analyse` 已返回结构化 `blocked`
- `/start` 创建的 incident 已作为当前目标记录，包括 `blocked` incident
- `analyse` 已避免静默覆盖 `/start` 生成的 `input.yaml`
- `review` 已写入 `analysis.yaml.review`，不再生成 `review.yaml`
- `/review` 无显式 incident 时已默认使用会话级当前目标记录
- Cursor smoke 测试已改为检查 `analysis.yaml.review`
- `/start` 的 `object-inventory.yaml` 已补充 MongoDB role、部署架构候选、targets、相关 Node 和相关 Event 只读线索
- `tools/remote-executor/mongodb-executor.py` 已从 smoke 入口中独立出来，作为当前正式远程执行入口
- 当前 remote executor 已从 `script-runtime-map.example.yaml` + MongoDB manifest 解析脚本，不再在执行器内部硬编码脚本源路径映射
- 当前 remote executor 已为每个脚本执行落 `remote-executor-request.yaml` 和 `remote-executor-result.yaml`
- 当前 remote executor 已补充基础 capability checks 和一批远程执行错误分类起点：`missing_sshpass`、`ssh_*`、`kubectl_*`
- 当前 remote executor 已补充顶层 `remote-executor-run.yaml`，即使 preflight `blocked` / batch `failed` 也会保留 run 级结构化结果
- 当前 remote executor 已对 `mongodb.collect.mongos.get_shard_map` 和 `mongodb.collect.replicaset.rs_status` 增加脚本级 preflight：target pod 解析、Pod 内 `mongosh` / `mongo` 可用性检查，以及 `target_pod_not_found` / `pod_tool_missing` 分类
- 当前 analyse 远程采集路径已消费 `/start` 产出的 `object-inventory.yaml`，把 `targets`、部署架构和拓扑线索传入第 3 段 context
- 当前 `/start` 已能从 Pod / StatefulSet 的显式 `secretKeyRef` 提取 MongoDB 认证 `secret_ref` hint，并通过 `object-inventory.yaml -> context-profile -> script context` 传给 `mongos_query` / `replicaset_query`
- remote run 转 incident 时，`script_outputs/` 已保留 `remote-executor-request/result`、stdout/stderr、artifacts，并把执行层成败补入 `collection_report`
- `analyse` 导入 remote run 时，已能消费 run 级 `blocked` / `failed` 结果：保留 `collection_report` 与 run-level 证据，并返回对应 adapter output，而不是只报本地异常

## 剩余待确认偏差

- `/start` 的第 2 段对象盘点仍是轻量只读线索，不执行 `rs.status()`、日志采集或 MongoDB shell 命令；副本集成员状态和深度验证仍属于 analyse 第 3 段
- 兼容保留的 `remote-smoke.py` 现在只做 smoke 包装；当前 remote executor 已具备 run-level / per-script 请求结果落盘、基础 capability checks、关键 MongoDB 脚本的 target / pod tool preflight、`secret_ref` hint 传递和 blocked 导入链路，但错误分类覆盖度、能力检查深度和部分回收语义仍是轻量实现，未完全收敛到 L1 最终边界
- 第 4 段当前已明确采用“规则 runner 保底草稿 + Cursor Agent 回填正式分析”的共存方式；后续仍需继续验证该链路在不同 Agent 平台上的稳定性
- 当前 MongoDB analyse 的采集目标模型仍偏 Pod-centric，尚未按 replica set / shard / configsvr / mongos 的候选健康执行点来建模，详见[推理分析流程复盘](2026-06-10-reasoning-flow-review.md)
- 当前第 3/4 段仍以单向串行为主，尚未形成“初始采集 -> 假设 -> 定向补采 -> 收敛”的小循环
- 当前 evidence gap 仍未显式区分 `expected_gap` 与 `critical_gap`，因此根因级结论的置信度上限约束还不够清晰

## 建议优先确认

1. 当前 remote executor 的错误分类、能力检查和回收语义如何继续收敛到 L1 最终边界
2. MongoDB 第 3 段采集目标是否应从单 Pod 调用提升为“拓扑单元 + 候选健康执行点”模型
3. 第 3/4 段是否应从单向串行改为允许假设驱动补采的小循环
4. `collection_report` 是否应区分 `expected_gap` 与 `critical_gap`，并据此限制根因级结论置信度

## 影响范围

- `tools/plugin/midstack-local.py`
- `plugins/cursor/mcp-server.py`
- `plugins/cursor/commands/`
- `plugins/cursor/rules/`
- `plugins/cursor/test-mcp-server.py`
- `plugins/cursor/test-sandbox.py`
- `tools/remote-executor/mongodb-executor.py`
- `tools/remote-smoke/mongodb-smoke.py`
- `tools/analyse/mongodb-analyse.py`
- `core/templates/analysis.template.yaml`
- `core/templates/review.template.yaml`
- `core/models/adapter-output.schema.yaml`
- `core/taxonomies/status-types.yaml`
- `tests/fixtures/`
- `tools/replay/`
- `tools/validators/`

## 兼容性

当前采用：

- `analyse` 完成第 3 段后继续生成 `analysis.rule-draft.yaml` 和 `agent-reasoning-task.md`
- Cursor Agent 读取 incident 证据与任务单，回填正式 `analysis.yaml` 与 `report.md`
- 规则 runner 保留为 MVP 保底草稿与离线 replay / score 基线
- 但上述链路仍需结合[推理分析流程复盘](2026-06-10-reasoning-flow-review.md)继续收敛第 3 段采集模型和第 4 段置信度约束

需要特别评估：

- remote executor 正式化是否兼容当前 remote smoke 结果目录
- 引入 Agent 推理层时，应避免直接把全量原始日志交给模型；优先消费第 3 段整理后的证据包、证据缺口和 artifact 引用

## 决策

待确认。

## 落地清单

- 确认 remote smoke 与正式 remote executor 的边界
- 确认规则 runner 与 Agent 推理层的边界
- 确认 `/start` targets 到 analyse context 的注入边界
- 验证完成后再更新 `docs/project/implementation-status.md` 或 `docs/project/todo.md`
