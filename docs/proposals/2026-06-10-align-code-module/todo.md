---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 2026-06-10 代码模块对齐 TODO

本文件是本提案目录下的过程性待办清单，不是事实源。

## 待确认

- [x] `blocked` 对 MCP 是否应表现为成功 tool call，并通过 adapter output 暴露 `status: blocked`
- [x] `customer_clue` 是否按 L1 改为可选输入，缺失时不阻塞 `/midstack:start`
- [x] `analyse` 是否绝不静默重写 `/start` 阶段冻结的 `input.yaml`
- [x] `review` 是否立即迁移到 `analysis.yaml.review`，停止生成 `review.yaml`
- [x] `remote-smoke.py` 回退为兼容保留的 smoke test 包装入口，正式执行入口迁移到 `tools/remote-executor/`
- [x] 第 4 段 Agent 推理层当前由 Cursor Agent 读取 incident 后继续推理，并回填 `analysis.yaml` / `report.md`
- [x] 规则 runner 当前定位为第 4 段 MVP 保底草稿与离线 replay / score 基线，不作为正式 Agent 推理替代

## 待实施

- [x] 按 L1 补齐 `incident_id` 的 `<middleware>-<YYYYMMDD>-<HHMMSS>-<rand4>` 规则
- [x] 将 `customer_clue` 从必填改为可选，并调整 start blocked 条件
- [x] 补齐 `meta.yaml` 的 `created / blocked / ready / analysing / analysed / reviewed` 状态迁移
- [x] 将 `start` / `analyse` 的阻塞场景统一为结构化 adapter output
- [x] MCP tool call 返回内容优先展示 adapter output 摘要，而不是只返回本地路径
- [x] `analyse` 读取 `meta.yaml` 并校验 incident 状态，状态不满足时返回 `blocked`
- [x] `analyse` 不再静默覆盖 `/start` 生成的 `input.yaml`
- [x] `review` 写入 `analysis.yaml.review`，并调整 `record_refs`
- [x] `review` 无显式 incident 时默认使用会话级当前目标记录
- [x] 更新 Cursor smoke 测试，不再断言必须存在 `review.yaml`
- [x] `/start` 的 `object-inventory.yaml` 补充 MongoDB role、部署架构、targets、相关 Node 和相关 Event 只读线索
- [x] remote executor preflight `blocked` / batch `failed` 时保留顶层 `remote-executor-run.yaml`，并让 incident 导入链路消费该结果
- [x] 为 `mongos.get_shard_map` 和 `replicaset.rs_status` 补齐脚本级 target / pod tool preflight，并将 `target_pod_not_found` / `pod_tool_missing` 纳入当前执行层分类
- [x] 将 `/start` 可见的显式 `secretKeyRef` 认证线索提取为 `auth_hints.selected_secret_ref`，并传递到 analyse 第 3 段 context
- [ ] 将 current remote executor 的错误分类继续收敛到 L1 最终边界，补齐更多 staging / output / artifact failure code
- [ ] 将 current remote executor 的能力检查和回收语义继续收敛到 L1 最终边界，明确 `partial` / `failed` 的 artifact retrieval 边界
- [x] 将 `/start` 识别出的 `targets` 接入当前 analyse 远程采集 context 生成逻辑
- [x] remote run 转 incident 时保留 `remote-executor-request/result`、执行日志和 artifacts，并把执行层结果回写到 `collection_report`
- [x] `remote-smoke.py` 增加基础 capability checks 和首批错误分类
- [x] 补齐第 4 段 Agent 推理层的触发点、输入证据包、输出合同和与规则 runner 的共存方式

## 待验证

- [x] 本地插件命令 smoke：`start`、`analyse`、`review`
- [x] Cursor MCP smoke
- [x] MongoDB fixture replay
- [x] MongoDB score comparison
- [x] 仓库 validator
- [x] 至少一个真实 remote smoke 或等价冻结 fixture 回归
