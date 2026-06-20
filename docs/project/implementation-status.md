---
status: draft
last_updated: 2026-06-20
supersedes: none
superseded_by: none
---

# 实现进展

本文件统一维护"已实现 / 未实现 / 已验证"类项目状态断言（L3，允许滞后）。

规范文档（`docs/specs/`）只定义设计意图，不承载实现进展；此前散落在 `README.md`「稳定结论」与 `plugin-runtime.spec.md` §12 中的进展内容已迁移至此。

## 总体进展

- MongoDB MVP 第一批 12 个第 3 段脚本已完成合同级实现，并已通过真实 K8s 环境验证
- 正式运行时代码已集中到 `src/`，按 `commands/`、`phases/`、`execution/`、`shared/` 划分
- Claude 适配器已支持 bundled runtime 打包、安装、自检和 sandbox 本地测试
- Cursor 适配器已支持 workspace-local runtime、命令/rule 投影、自检和 sandbox smoke
- 本地仓库工具、validator、replay、`src/` runtime 和插件安装态 runtime 的最低版本为 Python 3.10+
- `tools/plugin/midstack-local.py` 已收敛为本地 CLI 适配层，不再承载膨胀的正式实现
- Phase 1/2 已支持 remote/local/offline 三类 intake 场景识别；remote 仍是默认主路径，local 已可基于本机 kubectl context 进入 live collection，offline 仍以已有 artifact 消费为主
- 第 3 段默认日志采集已收敛到共享 `kubernetes.collect.logs.current` / `kubernetes.collect.logs.previous`；MongoDB 日志 alias 仅作兼容入口
- 第 4 段多轨推理实现已收敛到 `src/phases/phase4/multitrack/`；默认 agent runtime 为 `auto`，可在 `ANTHROPIC_API_KEY` + `anthropic` SDK 可用时尝试 Claude 推理，否则降级 mock。当前 `/midstack:analyse` 的生产 `conclusion_summary` 仍由 rules fallback + guardrails 守底，multitrack 结果会以 `agent_reasoning` 辅助草稿进入 `analysis.yaml` 和 reasoning segment，并由 `agent_conclusion_gate` 基于 `evidence_refs` 与结构化 `conclusion_candidate` 记录该草稿是否具备提升为正式结论的资格
- 第 4/5 段已生成 append-only 推理历史：`reasoning-manifest.yaml` 和 `reasoning/*.yaml` segment；`analysis.yaml` / `report.md` 作为最新物化视图
- Phase 4 rules 已输出 `reasoning_timeline`、`deepening_findings`、`verification_requests`、`deep_analysis_requests`、`retrieval_context`、`experience_matches` 和 `source_boundaries`；历史经验召回仍是预留字段，当前不接入真实向量库
- 受控验证请求已分层：一等只读 `auto_allowed` 脚本可由 analyse 编排交回 Phase 3 定向补采；二等 ad hoc 只读命令必须结构化 argv、approval required；破坏性命令会被 guardrail 标记 blocked
- Replay fixture 已拆分为 `tests/fixtures/active/` 与 `tests/fixtures/legacy/`，默认 replay、score 和仓库门禁只读取 active 样本
- Fixture hygiene gate 已覆盖 active、legacy 和 golden-path fixtures，阻断运行时生成物、疑似密钥和公网 IP；内网 IP 当前作为 warning 暴露
- 历史兼容层和旧入口目录已清理：`tools/lib/`、`tools/remote-executor/`、`tools/remote-smoke/`、`tests/replay/`、`tests/tools/analyse/`

## 当前结构状态

### 正式 runtime

- `src/commands/`
  slash 命令和本地 CLI 的正式编排入口
- `src/phases/`
  排障 5 段 control plane 实现
- `src/execution/`
  execution plane 的远端接入、脚本投放、远程执行和结果回收
- `src/shared/`
  跨命令、跨阶段复用的正式运行时能力

### Agent 适配器

- `plugins/claude/`
  官方 Claude Code 插件源实现；安装后使用 bundled runtime，不依赖 sandbox 内的源仓库 checkout
- `plugins/cursor/`
  Cursor command/rule projection 适配器；安装后使用 workspace-local runtime，不依赖源仓库 checkout

### 工程工具

- `tools/`
  仅保留薄入口、校验、回放、导入、生成和工程辅助工具
- `tests/`
  按 ownership 收敛到 `execution/`、`phases/`、`plugins/`、`shared/`、`tools/` 等目录，不再新增 `tests/unit/` 这类扁平历史目录
- `tests/fixtures/`
  `active/` 存放默认门禁样本，`legacy/` 存放历史归档样本，raw/private/sensitive 现场材料不得入库

## 第一版已实现能力清单

### `/plugin:start`

- 接收启动输入
- 支持"参数可选 + 交互补全"
- 创建 `incident_id`
- 创建 incident 目录和基础文件
- 识别 remote / local / offline intake 场景
- 在 remote 缺关键信息时记录本机 kubectl context 提示
- 验证远程环境基础可达性
- 验证基础 Kubernetes 操作能力
- local 模式验证本机 kubectl context 和基础对象盘点，不走 SSH/sshpass
- offline 模式可记录 artifact source 或 pasted evidence，但缺完整 artifact 时保持 blocked
- 判断并输出 `ready / blocked`
- 将新记录设为当前会话目标记录

### `/plugin:analyse`

- 基于当前目标记录继续执行
- 执行第 3 段信号采集与治理
- 输出：
  - `structured_record`
  - `signal_bundle`
  - `collection_report`
- 执行第 4 段过程推理，生成 `reasoning-board.yaml` 和 `analysis.multitrack.yaml`
- 通过 rules fallback + guardrails 生成生产 `analysis.yaml`
- 生成 `reasoning-manifest.yaml` 和 append-only reasoning segment，记录本轮分析快照、自动补采审计和 hypothesis validation 隔离引用
- 将 Phase 4 multitrack/Claude 辅助草稿写入 `analysis.yaml.agent_reasoning`、`report.md` 和 `reasoning/0002-agent-multitrack.yaml`，并写入 `agent_conclusion_gate` 评估结果；当前即使 gate 判定 `eligible` 也只记录资格，不覆盖 rules fallback 守底的结论字段
- 对一等只读 `verification_requests` 执行 Phase 3 定向补采并重新物化分析；对 ad hoc 请求只做 guardrail 归一化或 blocked，不自动执行
- 对机制已成立但 root cause 未闭合的场景可输出 plan-only `deep_analysis_requests`；analyse 会将已有证据派生物化到 `deep-analysis.yaml` / `analysis.yaml.deep_analysis_results`，当前 MongoDB split-brain 已覆盖基线扫描、代码逻辑分析、代码路径追踪和只读复现计划四类深挖结果
- 输出第 5 段阶段性结论
- 输出知识沉淀候选
- 可直接消费：
  - fixture 输入目录
  - `/start` 生成的 incident 目录
  - 已完成的 remote run 目录
- 可通过 `.local` 远程环境配置调度真实 MongoDB 只读采集，然后继续分析
- 可通过 ready local incident 的 `local-config.yaml` 使用本地 transport 调度同一批 Phase 3 采集脚本
- 支持 `--scope full`、`--scope collect`、`--scope reason` 三个正式 pipeline 切片

### MongoDB

- 环境与对象盘点
- Kubernetes 对象采集
  - `StatefulSet`
  - Pod
  - `Service`
  - Node
- 分片集群 / 副本集基础 topology 识别
- `rs.status()` 基础成员状态采集
- `rs.conf()` 定向只读采集
- Kubernetes Pod stdout/stderr 日志采集
  - 当前日志
  - 重启前日志（如可用）
- MongoDB 应用日志 sink 发现和文件日志 tail 定向补采
- DNS、网络 overlay、Pod describe 等定向补采能力
- 基础信号治理
  - 时间对齐
  - 对象关联
  - 初步过滤降噪
- replica set 多视角不变量 deepening
- split-brain enabling-cause 候选假设和只读验证请求
- MongoDB election、heartbeat、reconfig、startup、fatal 日志 highlight 归一化

### MongoDB 第一批脚本

`/plugin:analyse` 的 MongoDB MVP 已完成 12 个默认第 3 段采集/治理资产的合同级实现（清单与执行顺序见[插件运行时规范](../specs/plugin-runtime.spec.md)，能力边界见 [Analyse MVP 规范](../specs/analyse-mvp.spec.md)）。其中当前/previous Pod 日志通过共享 Kubernetes 资产采集，MongoDB `collect.logs.current/previous` 只保留兼容 alias。

真实环境验证状态：

- 以上 12 个脚本已通过真实 K8s 环境远程采集回归
- 测试环境为 3 节点 Kubernetes 集群
- 目标 namespace 为 `psmdb-test`
- 验证对象包括：
  - 12 个 Pod
  - 3 个 StatefulSet
  - 2 个 Service
  - 3 个 Node
  - 2 个 shard
  - 3 个副本集，9 个成员
  - 22 个日志文件
  - 63 条日志 highlights
  - 1 个 signal bundle

### `/plugin:review`

- 保留命令入口
- 保留运行时规则和目标记录选择规则
- 五维评分与改进建议已有第一版实现

### Claude 插件

- 已支持插件打包、安装、更新到目标 sandbox 工作区
- 已支持 sandbox 本地 marketplace 安装模式
- 已支持 bundled runtime 自检和安装后完整性校验
- 已清理旧的 namespaced / hyphen slash surface，当前正式命令为：
  - `/midstack:start`
  - `/midstack:analyse`
  - `/midstack:review`
  - `/midstack:validate`

### Cursor 插件

- 已支持本地 Cursor 插件链接和工作区命令/rule projection
- 已支持 workspace-local runtime 打包到目标工作区
- 已支持工作区状态文件校验、runtime marker 检查和版本检查
- 已支持固定 sandbox 自动化适配器冒烟回归

## 第一版未实现能力清单

### `/plugin:analyse`

- `force_recollect` 参数
- 复杂多记录切换命令
- 真实 Claude API 推理结果覆盖生产结论的闭环（当前 auto runtime 可尝试 Claude，draft 已进入 `agent_reasoning`，`agent_conclusion_gate` 会基于证据引用和结构化候选结论评估是否具备提升资格，但 `conclusion_summary` 仍由 rules fallback + guardrails 守底）
- 深入层自动执行闭环：
  - 基线扫描结果自动物化
  - 代码逻辑分析结果自动回写生产结论
  - 代码路径追踪自动闭合证据边
  - 复现脚本或 fixture 自动生成

### `/plugin:review`

- 评分权重正式化
- 评分结果归档策略正式化

### MongoDB

- 更复杂的高级场景自动化分析
- 节点系统日志的完整实现
- 指标采集的完整实现
- 外部日志系统接入的完整实现

### 其他中间件

- Pulsar Active MVP 正式支持（当前仅为 Skeleton / contract path：资产、首条 golden path、脚本合同和 rules analyser 已在）
- Redis 正式支持
- Elasticsearch 正式支持
- Kafka 正式支持
