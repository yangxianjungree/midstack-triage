---
status: draft
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# TODO

本文件用于记录当前已识别、但暂未继续推进的事项。

讨论过程和结论请同步记录到[讨论归档](../decisions/discussions-archive.md)。

## 待讨论

### 1. 仓库结构进一步定稿

- 是否需要在 `domains/` 下为不同中间件补齐统一骨架
- `core/models/`、`core/templates/`、`core/taxonomies/` 的最终文件布局
- `interfaces/plugin/` 下需要暴露哪些最小接口契约

### 2. 资产规范进一步收敛

- `runbook`、`command`、`skill` 的 metadata 字段是否需要继续精简或补充
- `scenario.yaml` 的最小字段集是否已经足够
- 标签、风险等级、适用环境等枚举是否需要集中到 `core/taxonomies/`

### 3. MongoDB 样例是否足以代表通用模式

- 是否继续补 MongoDB 第二个场景，用于验证结构稳定性
- 是否直接平移一套样例到 Kafka、Redis 或 Pulsar，验证跨中间件可复用性

### 4. 适配器策略

- 主仓库保留 `interfaces/` 接口定义，同时在 `plugins/<agent>/` 保留适配器源实现是否继续稳定
- Claude Code、Codex、Cursor 的适配器后续是否拆为独立仓库
- 各适配器与本仓库之间采用何种版本兼容策略

### 5. 运行与安全边界

- 只读、低风险、高风险动作的判定标准是否需要更正式的分类文件
- runbook、skill、script 在“诊断阶段”和“处置阶段”的边界是否需要单独建模

## 待实现

近期执行优先级以[实施计划](implementation-plan.md)为准。

测试、验证与优化闭环已作为最后一类实施需求记录在[实施计划](implementation-plan.md#p3-测试验证与优化闭环)。

### 1. 补齐共性层占位与规范

- 在 `core/models/` 中继续补齐严格 schema 或跨资产引用校验
- 在 `core/templates/` 中继续按实际 analyse/review 输出迭代模板字段
- 在 `core/taxonomies/` 中继续补充中间件大类、组件类型和信号类型枚举

### 2. 补齐接口定义

- 为适配器消费补充 `runbook`、`command`、`skill`、`agent output` 的接口定义文件
- 为第 3 段到第 4 段的三类接口输出补充样例
- 补充脚本 manifest 的严格 schema
- 补充第 3 段 `context-file` / `output-file` 的严格 schema
- 补充 `script-runtime-map.yaml` 的严格 schema
- 补充 `remote executor` 请求和结果的严格 schema

### 3. 补齐工具链

- `tools/validators/`：继续补齐 metadata、目录结构、schema 校验
- `tools/generators/`：继续补齐更多资产类型和批量生成能力
- `tools/importers/`：继续补齐 command、skill、script 等更多资产导入能力

### 4. 补齐 MongoDB 领域资产

- 增加更多 MongoDB 组件目录样例
- 增加更多 MongoDB 场景样例
- 增加脚本资产样例，验证 `scripts/` 的组织方式
- 按已确认规则补齐 `domains/mongodb/scripts/helpers/`
- `/plugin:analyse` 的 `force_recollect` 参数设计与实现

### 5. 安全与敏感信息处理

- 明确密码、账号、入口 IP 等敏感信息的存储和展示规则
- 明确哪些字段需要脱敏
- 明确日志、记录文件和输出中的敏感信息处理策略
- operator+CRD 场景下从 Kubernetes Secret 读取 MongoDB 认证信息已在核心采集脚本落地；后续仍需补完整拓扑适配和脱敏策略

### 6. Fixture 生命周期与脱敏治理

- 为历史 fixture 增加状态和版本元信息，例如 `status`、`schema_version`、`last_verified_with`
- 继续收敛 fixture hygiene validator 的客户名、未脱敏日志和内网 IP allowlist 策略
- 将现存 fixture 中的私网 IP 逐步替换为文档保留地址或明确假值，减少 warning 噪音

### 7. 扩展到其他中间件

- Redis
- Elasticsearch
- Kafka
- Pulsar
- `review` 评分权重和结果归档策略正式化

## 已完成但需后续复核

### 0. Fixture 生命周期与脱敏治理

- 已将 `tests/fixtures/` 拆分为 `active` / `legacy`
- 默认 replay、score gate 和 MongoDB fixture validator 已切到 active fixture
- 已将 raw/private/sensitive fixture 目录和 `.local/fixtures/` 加入 `.gitignore`
- 已扩展 fixture hygiene validator，覆盖 active、legacy 和 golden-path fixtures，阻断运行产物、疑似密钥和公网 IP
- 已修复 `kubernetes-readiness-failure-sample` 的最小证据链，避免历史期望阻断默认 validator

### 1. 结构边界

- 已明确 `scenarios/` 只定义场景，不存产品专属 runbook
- 已明确 `domains/<product>/` 只存具体中间件资产
- 已明确 runbook 只存一份，物理上按组件组织，逻辑上按场景检索
- 已明确 `interfaces/` 放跨适配器接口定义，`plugins/<agent>/` 放适配器源实现
- 已明确源码仓库自己的 `.cursor/` 不作为 Midstack 插件安装投影
- 已明确 `core/shared/` 四类目录的职责边界
- 已明确 MongoDB 第一版脚本目录与命名规范
- 已明确主仓库脚本资产与插件运行时脚本分离
- 已明确最小 `script_id` 规则
- 已明确单中间件 `manifest.yaml` 方案
- 已明确插件侧 `script_id -> runtime_path` 最小映射方案
- 已明确第 3 段脚本最小调用合同
- 已明确 `remote executor` 作为正式执行层
- 已明确中间件工具优先通过 Pod 内执行
- 已明确真实 K8s 环境的脚本测试分层方式
- 已明确 `remote executor` 的最小请求、结果和错误模型
- 已实现 `mongodb.collect.pods.state` 的合同级脚本
- 已实现 `mongodb.collect.statefulsets.yaml` 的合同级脚本
- 已实现 `mongodb.collect.services.yaml` 的合同级脚本
- 已实现 `mongodb.collect.nodes.state` 的合同级脚本
- 已实现 `mongodb.collect.events.yaml` 的合同级脚本
- 已实现 `mongodb.collect.resources.metrics` 的合同级脚本
- 已实现 `mongodb.collect.mongos.get_shard_map` 的合同级脚本
- 已实现 `mongodb.collect.replicaset.rs_status` 的合同级脚本
- 已实现 `mongodb.collect.logs.current` 的合同级脚本
- 已实现 `mongodb.collect.logs.previous` 的合同级脚本
- 已实现 `mongodb.normalize.logs.highlights` 的合同级脚本
- 已实现 `mongodb.normalize.signals.bundle` 的合同级脚本
- 已通过真实 K8s 环境验证 `mongodb.collect.pods.state`
- 已通过真实 K8s 环境验证 `mongodb.collect.statefulsets.yaml`
- 已通过真实 K8s 环境验证 `mongodb.collect.services.yaml`
- 已通过真实 K8s 环境验证 `mongodb.collect.nodes.state`
- 已通过真实 K8s 环境验证 `mongodb.collect.events.yaml`
- 已通过真实 K8s 环境验证 `mongodb.collect.resources.metrics`
- 已通过真实 K8s 环境验证 `mongodb.collect.mongos.get_shard_map`
- 已通过真实 K8s 环境验证 `mongodb.collect.replicaset.rs_status`
- 已通过真实 K8s 环境验证 `kubernetes.collect.logs.current`
- 已通过真实 K8s 环境验证 `kubernetes.collect.logs.previous`
- 已通过真实 K8s 环境验证 `mongodb.normalize.logs.highlights`
- 已通过真实 K8s 环境验证 `mongodb.normalize.signals.bundle`
- 已补齐 MongoDB MVP 第一批 12 个脚本的合同级实现
- 已通过真实 K8s 环境跑通 MongoDB MVP 第一批 12 个脚本
- 已补充基于 `src/execution/remote/executor.py` 的远程脚本测试执行入口
- 已使用正式远程 smoke 工具跑通 MongoDB MVP 第一批 12 个脚本
- 已明确第 3 段脚本需兼容 Python 3.6 且不默认依赖 `PyYAML`
- 已补充 `tools/validators/validate-mongodb-scripts.py`，用于校验 MongoDB 脚本 manifest 与插件运行时映射
- 已补充 `tools/validators/validate-repo.py`，用于串联资产合同校验、fixture replay 和 score gate
- 已通过 `validate-mongodb-scripts.py` 校验 MongoDB MVP 第一批 12 个脚本
- 已补充 `core/models/script-context.schema.yaml` 和 `core/models/script-output.schema.yaml` 的轻量合同模型
- 已补充 MongoDB 基础采集脚本 `context-file` 和 `output-file` 示例文件
- 已补充 MongoDB `context.example.yaml` / `output.example.yaml` 的最小合同校验
- 已补充 `script-runtime-map.example.yaml` 与 manifest 的一致性校验
- 已补充 `core/models/script-runtime-map.schema.yaml` 轻量合同模型
- 已补充 `core/models/remote-executor-request.schema.yaml` 和 `core/models/remote-executor-result.schema.yaml` 轻量合同模型
- 已补充 `remote-executor-request.example.yaml` / `remote-executor-result.example.yaml` 的最小合同校验
- 已补充 `core/models/script-manifest.schema.yaml` 轻量合同模型
- 已补充 MongoDB `manifest.yaml` 的最小合同校验
- 已补充 `core/models/runbook.schema.yaml`、`core/models/command.schema.yaml`、`core/models/skill.schema.yaml` 轻量合同模型
- 已补充 MongoDB runbook、command、skill metadata 的最小合同校验
- 已补充 `core/models/adapter-output.schema.yaml` 轻量合同模型
- 已补充 `interfaces/plugin/adapter-output.example.yaml` 示例
- 已补充 adapter output 的最小合同校验
- 已补充 runbook、command、skill 的 metadata 和正文模板
- 已补充风险等级、状态、场景类型、能力类型和标签规范枚举
- 已将风险等级、状态和场景类型共性枚举接入 validator
- 已补充诊断检查单和事件总结模板
- 已补充 analysis、review、knowledge candidate 模板
- 已补充 `tools/generators/generate-asset.py`，支持生成 runbook、command、skill 资产骨架
- `tools/generators/generate-asset.py` 已支持 `--kind bundle` 批量生成一个场景下的 runbook、command、skill
- 已补充 `tools/importers/import-runbook.py`，支持导入已有 Markdown 为标准 runbook 资产
- `tools/importers/import-runbook.py` 已支持导入 runbook、command、skill 三类 Markdown 资产
- 已补充 `docs/specs/analyse-mvp.spec.md`，明确第一版 `/plugin:analyse` 能力边界
- 已补充跨资产引用校验：scenario 定义、领域资产 scenario 引用、skill required_assets 引用
- 已补充 MongoDB 第二场景 `connection-failure` 的 scenario、runbook、command、skill 样例
- validator 已改为校验 MongoDB 下所有 runbook、command、skill metadata
- 已补充 MongoDB `components/` 组件入口索引
- 已补充 MongoDB scripts helpers 边界说明
- validator 已支持 MongoDB 领域资产 component 引用校验
- MongoDB `mongos getShardMap` 和 `replicaset rs.status` 脚本已支持从 Kubernetes Secret 读取认证信息
- Secret 认证支持改动后已通过真实 MongoDB 远程采集回归，10 个原有 MVP 脚本全部 `success`
- 已补充 MongoDB `resource-exhaustion`、`latency-spike`、`data-hotspot` 场景资产
- 已补充 P3 测试闭环基础目录：fixtures、replay、scores
- 已补充 MongoDB 第一批 replay fixture：baseline、replica-inconsistency、connection-failure
- 已补充 MongoDB remote run / incident 到 fixture 的冻结工具
- validator 已支持 MongoDB fixture 最小文件集校验
- 已补充 MongoDB fixture replay 摘要工具
- 已补充 MongoDB score summary 工具
- 已补充 MongoDB score comparison runner，支持基于 replay analysis 生成结构化评分文件
- MongoDB score comparison runner 已支持 `--min-level` 最小评分阈值门禁
- 已补充最小 MongoDB 本地 analyse runner
- MongoDB analyse runner 已能基于领域资产 metadata 生成场景匹配的知识沉淀候选
- MongoDB replay 已支持 `--run-analyse` 并对比 expected/actual 一级归因
- 已补充本地 CLI 适配层 `start/analyse/review`，用于验证 incident 文件流转
- 本地 CLI `analyse` 已支持消费已完成的远程采集结果目录，归并脚本输出并生成 incident 分析结果
- 本地 CLI `analyse` 已支持通过 `.local` remote config 调用远程执行入口执行真实只读采集后继续分析
- 本地 CLI `review` 已能基于 `analysis.yaml` 生成五维评分和改进建议
- 已补充 `plugins/cursor/` Cursor 集成源实现、`/midstack:*` 命令和自动化适配器冒烟回归
- 已补充 Cursor 固定 sandbox 测试入口 `/home/stephen/AI/midstack-sandbox`
- 已补充 Kubernetes runtime 通用信号 taxonomy 和 `runtime-classification` validator，防止故障分类点对点实现
- 已补充 MongoDB Kubernetes scheduling 故障 fixture，并验证未知场景下可归因为 `kubernetes-scheduling`

### 2. 首个领域样例

- 已落地 MongoDB 样例
- 已落地 `replica-inconsistency` 场景样例
- 已落地 1 个 runbook、1 个 command、1 个 skill 样例
- 已落地 `connection-failure` 场景样例
- 已落地第二组 runbook、command、skill 样例
- 已落地 `resource-exhaustion`、`latency-spike`、`data-hotspot` 场景样例

## 之前提过、暂时记账的事项

- 补齐仓库目录骨架
- ~~补一版 `docs/architecture.md`~~（已有 [architecture.md](../concepts/architecture.md) 与 [architecture-overview.md](../concepts/architecture-overview.md)）
- 后续讨论如何在 Claude Code 官方标准下兼容 Cursor 和 Codex
