---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Implementation Plan

本文件用于把当前剩余工作收敛为可执行计划。

原则：

- 先补能支撑编码和验证的内容
- 不继续堆空目录
- 每项工作必须有产出物和验收条件
- MongoDB 继续作为第一版 MVP 验证对象

## P0: 最值得先做

### 1. 明确 `/plugin:analyse` 第一版能力边界

目标：

- 明确第一版 `analyse` 到底做什么、不做什么
- 避免后续实现时把第 3、4、5 段职责混在一起

产出物：

- `docs/specs/analyse-mvp.spec.md`

必须明确：

- 输入来源：会话级当前目标记录（唯一定义见 `docs/specs/plugin-runtime.spec.md` §4）
- 前置条件：incident 为 `ready`，或为 `analysed`（继续分析）
- 执行范围：MongoDB 第一批 11 个第 3 段脚本
- 第 3 段输出：`structured_record`、`signal_bundle`、`collection_report`
- 第 4 段输出：多假设、支持证据、反证条件、证据不足项、验证结果
- 第 5 段输出：初步结论、置信度、影响范围、下一步建议、知识沉淀候选
- 暂不实现：完整 `scope` 矩阵、`force_recollect`、高风险处置动作、自动修复、跨中间件联合诊断

验收条件：

- 能回答“第一版 analyse 跑完后用户能看到什么”
- 能回答“第一版 analyse 哪些能力明确不做”
- 能映射到现有 5 段流程和 3 个插件命令

### 2. 增加跨资产引用校验

目标：

- 让知识资产之间的引用可检查
- 防止 skill 引用不存在的 runbook 或 command
- 防止 metadata 中的 scenario 只写了字符串但没有场景定义

产出物：

- 扩展 `tools/validators/validate-mongodb-scripts.py`
- 更新 `tools/validators/README.md`

校验范围：

- `skill.metadata.required_assets[]` 指向的目录必须存在
- `runbook.metadata.scenario` 必须存在 `scenarios/<scenario>/scenario.yaml`
- `command.metadata.scenario` 必须存在 `scenarios/<scenario>/scenario.yaml`
- `skill.metadata.primary_scenario` 必须存在 `scenarios/<scenario>/scenario.yaml`
- `scenario.yaml.id` 必须与目录名一致
- `scenario.yaml.applicable_middleware` 必须包含当前 middleware

验收条件：

- 当前 MongoDB runbook、command、skill 样例通过校验
- validator 报错能指出具体缺失引用

当前状态：

- 已实现

### 3. 补 MongoDB 第二个场景样例

目标：

- 验证当前结构不是只为 `replica-inconsistency` 特化
- 验证场景层和领域层的职责边界是否稳定

优先场景：

- `connection-failure`

原因：

- 连接失败是 MongoDB、Redis、Kafka、Pulsar 都会遇到的共性场景
- MongoDB 下可关联 Kubernetes Service、Pod、mongos、认证、网络、客户端报错等多类信号
- 能覆盖“客户线索可能只是报错文本”的真实输入方式

产出物：

- `scenarios/connection-failure/scenario.yaml`
- `scenarios/connection-failure/README.md`
- `domains/mongodb/runbooks/connectivity/connection-failure/`
- `domains/mongodb/commands/connectivity/check-mongos-connectivity/`
- `domains/mongodb/skills/connectivity/triage-connection-failure/`

验收条件：

- 新场景资产通过 validator
- 不复制已有 `replica-inconsistency` 资产结构以外的特殊逻辑
- 能说明哪些内容在 `scenarios/`，哪些内容在 `domains/mongodb/`

当前状态：

- 已实现 `connection-failure` 场景样例

## P1: 工程化增强

### 1. 严格 schema 与 validator 分层

目标：

- 让轻量模型逐步升级为更严格、可复用的校验基础

产出物：

- 保留当前 `core/models/*.schema.yaml`
- 后续增加严格 schema 或专用校验器

验收条件：

- validator 规则不再散落为难以维护的硬编码
- taxonomies 成为枚举来源

当前状态：

- 已补充顶层 `tools/validators/validate-repo.py`，用于串联资产合同校验、fixture replay 和 score gate
- 领域级 MongoDB validator 仍保留，后续继续拆分严格 schema 或专用校验器

### 2. 生成器增强

目标：

- 降低新增中间件和场景资产的重复成本

产出物：

- 扩展 `tools/generators/generate-asset.py`

后续能力：

- 批量生成一个场景下的 runbook + command + skill
- 根据 `scenario.yaml` 自动填充 scenario 字段
- 支持 `--middleware`、`--component`、`--scenario` 的合法性校验

验收条件：

- 能一条命令生成 MongoDB 第二场景的基础资产骨架

当前状态：

- 已实现 `--kind bundle`

### 3. 导入器增强

目标：

- 支持把历史专家文档逐步纳入标准资产体系

产出物：

- 扩展 `tools/importers/`

后续能力：

- 导入 command
- 导入 skill
- 导入脚本说明或脚本资产
- 导入时生成待补 metadata

验收条件：

- 外部 Markdown runbook 能转换为标准目录
- 导入结果能通过 validator

当前状态：

- 已支持导入 runbook、command、skill 三类 Markdown 资产

### 4. 更细粒度模板

目标：

- 支撑第 4、5 段输出标准化

产出物：

- 分析模板
- review 模板
- 知识沉淀候选模板

验收条件：

- `/analyse` 规范能直接引用这些模板

当前状态：

- 已补充 analysis、review、knowledge candidate 模板

## P2: MongoDB 领域继续补

### 1. MongoDB 组件目录样例

目标：

- 让 MongoDB 领域资产按组件入口更清晰

优先组件：

- connectivity
- mongos
- configsvr
- shard
- replica-set
- storage
- kubernetes-runtime

验收条件：

- 每个组件目录职责明确
- runbook 仍只存一份，不因为多入口复制

当前状态：

- 已补充 MongoDB `components/` 组件入口索引

### 2. MongoDB 脚本 helpers 约定

目标：

- 为后续脚本复用公共解析、输出、时间处理和 kubectl 辅助逻辑做准备

产出物：

- `domains/mongodb/scripts/helpers/README.md` 完善
- 后续按需增加 helper，不提前抽象过度

验收条件：

- 当前 11 个脚本不强制重构
- 新脚本有明确 helper 使用边界

当前状态：

- 已完善 `domains/mongodb/scripts/helpers/README.md`

### 3. operator+CRD Secret 认证支持

目标：

- 支持 operator+CRD 部署下从 Kubernetes Secret 获取 MongoDB 认证信息

产出物：

- 扩展 MongoDB 认证约定
- 扩展相关采集脚本

验收条件：

- Bitnami env / password file 方式不被破坏
- Secret 读取结果不写入 output、artifact 或日志摘要

当前状态：

- 已在 `mongos getShardMap` 和 `replicaset rs.status` 采集脚本中支持 `secret_ref`
- 已通过真实 MongoDB 远程采集回归验证 Bitnami 现有认证路径未被破坏

### 4. MongoDB 更多场景

优先顺序：

1. `connection-failure`
2. `resource-exhaustion`
3. `latency-spike`
4. `data-hotspot`

验收条件：

- 每个新增场景至少包含 scenario、runbook、command、skill 样例
- 每个新增场景都能通过 validator

当前状态：

- 已补充 `connection-failure`
- 已补充 `resource-exhaustion`
- 已补充 `latency-spike`
- 已补充 `data-hotspot`

## 暂缓事项

以下事项继续保留，但不作为近期优先级：

- `/plugin:analyse --scope` 完整矩阵（当前仅支持 `full`、`collect` 与 `reason`）
- `/plugin:analyse --force_recollect`
- 自动修复和高风险处置动作
- Claude Code、Codex、Cursor 适配器是否从 `plugins/<agent>/` 进一步拆成独立仓库
- `review` 人工反馈系统正式实现

## P4: 更多中间件扩展

当前优先级最低。

暂缓扩展：

- Redis
- Elasticsearch
- Kafka
- Pulsar

进入条件：

- MongoDB analyse runner 已能跑通
- MongoDB fixture replay 已能形成稳定回归
- 插件命令和 incident 记录结构已经稳定

当前前置状态：

- 已补充本地 CLI 适配层用于验证 `start/analyse/review` 文件流转
- 本地 CLI `review` 已能基于 `analysis.yaml` 生成五维评分和改进建议
- 已补充 `plugins/cursor/` Cursor 集成源实现，可安装到临时 Cursor 项目并自动化适配器冒烟回归
- Cursor 安装投影已明确写入目标项目 `.cursor/`，源码仓库只保留 `plugins/cursor/` 源实现

扩展原则：

- 不为新中间件重新设计仓库结构
- 复用现有 core/models、templates、taxonomies 和工具链
- 每个新中间件至少先落地一个场景、一个 runbook、一个 command、一个 skill

## P3: 测试、验证与优化闭环

目标：

- 不依赖用户反馈作为主要优化来源
- 利用固定三节点测试环境生成真实基线
- 通过 fixture replay 提升迭代速度
- 通过评分结果观察插件能力是否退化或提升

### 1. 三节点环境 profile

目标：

- 将三节点 MongoDB K8s 环境作为固定测试环境使用
- 环境连接信息继续只放 `.local/`，不进入仓库

产出物：

- `.local/test-envs/mongodb-k8s.yaml`
- `src/execution/remote/executor.py` 继续作为真实环境远程采集验证入口

验收条件：

- 能稳定跑通 MongoDB MVP 11 个脚本
- 能生成一次完整远程采集 run 结果目录

### 2. Baseline fixture

目标：

- 从真实环境采集结果中冻结一份“正常基线”
- 后续 analyse 优先用 fixture 离线回放，不每次都连真实环境

建议目录：

```text
tests/fixtures/active/mongodb/baseline-sharded-cluster/
  input.yaml
  structured_record.yaml
  signal_bundle.yaml
  collection_report.yaml
  expected_analysis.yaml
```

验收条件：

- baseline fixture 能表达正常分片集群的对象、topology、成员状态和日志摘要
- analyse replay 能基于该 fixture 生成稳定输出

当前状态：

- 已补充 `tests/fixtures/active/mongodb/baseline-sharded-cluster/`
- 已补充 `tools/replay/mongodb-freeze-fixture.py`，可将 remote run 或 incident 冻结为离线 fixture

### 3. Incident replay

目标：

- 将历史故障、模拟故障、真实采集结果转成可反复回放的 incident case

第一批 case：

- `baseline-sharded-cluster`
- `replica-inconsistency-sample`
- `connection-failure-sample`

建议目录：

```text
tests/fixtures/active/mongodb/<case_id>/
  input.yaml
  structured_record.yaml
  signal_bundle.yaml
  collection_report.yaml
  expected_analysis.yaml
```

验收条件：

- 每个 case 都能离线跑 analyse
- 每个 case 都有期望结论或专家结论

当前状态：

- 已补充 baseline、replica-inconsistency、connection-failure 三个 fixture
- 已补充最小 fixture replay 摘要工具
- 已补充 remote run / incident 到 fixture 的冻结工具
- 已补充最小 MongoDB 本地 analyse runner
- replay 已支持生成 analysis 输出并对比 expected/actual 一级归因
- 本地 CLI analyse 已支持消费已完成的远程采集结果目录
- 本地 CLI analyse 已支持通过远程执行入口调度真实只读采集
- 完整插件 analyse runner 尚未实现正式 remote executor 调度

### 4. Score comparison

目标：

- 用结构化评分判断插件输出是否变好
- 避免只凭主观感觉优化 prompt 或脚本

评分维度：

- `evidence_completeness`
- `hypothesis_coverage`
- `validation_depth`
- `conclusion_confidence`
- `knowledge_reusability`

建议目录：

```text
tests/scores/mongodb/
  <case_id>.score.yaml
```

验收条件：

- 每次 replay 都能生成或更新评分结果
- 能对比新旧输出是否退化

当前状态：

- 已补充 baseline score 样例
- 已补充最小 score summary 工具
- 已补充最小 score comparison runner，默认输出到 `.local/scores/mongodb`
- 已补充最小评分阈值门禁 `--min-level`
- 完整历史趋势对比尚未实现

### 5. 最小回归链路

建议顺序：

1. 跑 validator
2. 跑 fixture replay
3. 跑 score comparison
4. 必要时跑真实远程采集回归

验收条件：

- 改脚本时必须至少跑 validator 和相关 replay
- 改远程执行或采集逻辑时必须跑真实远程采集回归
- 改推理、prompt、review 逻辑时必须跑 replay 和 score comparison

当前状态：

- 已补充 `tools/validators/validate-repo.py` 作为本地最小回归入口
- 已补充 `plugins/cursor/test-agent-cli.py`，在临时工作区自动化验证 Cursor workspace-local runtime adapter 的 analyse/review
- 已补充 `plugins/cursor/test-sandbox.py`，在 `/home/stephen/AI/midstack-sandbox` 安装并保留一个可被 Cursor 打开的测试项目
- 已补充 Kubernetes runtime 通用分类检查，要求 normalizer 发出的 K8s runtime signal 必须登记在 middleware-agnostic taxonomy
- 已补充 MongoDB Kubernetes scheduling 故障 fixture，用于回归验证未知场景下的通用运行时故障归因
