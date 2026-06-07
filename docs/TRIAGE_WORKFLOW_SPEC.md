# Triage Workflow Spec

本文件用于沉淀当前已经基本稳定的排障主流程规范，作为项目后续 `runbook`、`skill`、结构化记录、脚本和知识沉淀的基线。

讨论细节仍保留在 [docs/TRIAGE_WORKFLOW_DISCUSSION.md](/home/stephen/AI/midstack-triage/docs/TRIAGE_WORKFLOW_DISCUSSION.md)。

## 1. 主流程

当前排障主流程采用 5 段式：

1. `受理与启动`
2. `环境确认与对象盘点`
3. `信号采集与治理`
4. `推理诊断与深入验证`
5. `结论整合与知识沉淀`

## 2. 第 1 段：受理与启动

### 目标

- 让排障可以正式启动
- 保存最小输入和第一手原始线索
- 判断是否具备进入环境的基础条件

### 最小必填输入

- 中间件类型
- K8s 环境 IP
- 账号
- 密码

### 高价值可选输入

- 客户提供的原始故障线索
- 端口

### 输出状态

- `ready`
- `blocked`

### `ready` 最小条件

- 已提供远程环境信息
- 已验证远程环境信息有效
- 可执行基础 Kubernetes 操作
- 已明确需要排查哪个中间件
- 已提供的故障线索可以被理解

### 典型 `blocked` 条件

- 缺少必要工具，例如 `sshpass`
- 无法通过提供的远程信息完成基础连通性验证
- 远程环境没有 Kubernetes
- 无法执行基础 Kubernetes 操作，例如 `kubectl exec`
- 远程环境中不存在目标中间件，或当前入口无法触达目标环境

## 3. 第 2 段：环境确认与对象盘点

### 目标

- 确认目标环境和目标集群
- 识别部署架构
- 盘清关键对象和基础拓扑

### MongoDB 的对象识别顺序

1. `namespace`
2. `部署架构`
3. `mongos / configsvr / shard`
4. `StatefulSet`
5. `Pod`
6. `Service / NodePort`
7. `Node`
8. `副本集成员状态`

### MongoDB 分片集群的基础拓扑骨架

- 多个 `mongos`
- 一个 `configsvr` 副本集
- 多个 shard
- 每个 shard 都是一个副本集

### 部署架构依赖

MongoDB 拓扑骨架到 Kubernetes 对象的映射必须依赖部署架构识别，当前至少考虑：

- `operator + CRD`
- `Bitnami`

## 4. 第 3 段：信号采集与治理

### 目标

- 收集并治理多源信号
- 将信号与具体对象、时间线和拓扑建立关联
- 为第 4 段准备可用于推理的证据链

### 主顺序

1. 汇总所有已获取信号
2. 给信号补时间戳或统一时间基准
3. 将信号绑定到具体对象
4. 对日志和重复状态做过滤降噪
5. 做粗粒度分类和归并
6. 形成可供第 4 段使用的证据链和时间线

### MongoDB 的主辅模式

主模式：

1. 实体 / 拓扑关联驱动
2. 时间线驱动
3. 规则 / 阈值驱动

辅模式：

4. 先过滤，再用 LLM 做轻理解
5. AI 建议 + 人工确认

### MongoDB 的主要信号类型

- 对象状态信号
- Topology 信号
- 副本集行为信号
- 日志信号
- 节点系统日志信号
- 事件与变更信号
- 时间线信号

### MongoDB 的默认信号治理优先级

1. 对象状态信号
2. 时间线信号
3. Topology 信号
4. 副本集行为信号
5. 事件与变更信号
6. 日志信号

### MongoDB 的例外优先级

对于以下场景：

- Pod 拉不起来
- `CrashLoopBackOff`
- 容器反复重启

日志信号应前置。

### 节点系统日志原则

节点系统日志应视为第 3 段的补充信号来源。

适用场景包括：

- 节点异常
- `NotReady`
- `DiskPressure`
- `OOM`
- kubelet 或 runtime 异常
- Pod 重启与节点状态变化时间接近

使用原则：

- 默认不全量采集
- 按条件触发
- 优先按时间窗口裁剪
- 优先提取关键系统日志，再决定是否保留原始内容

### 第 3 段的执行主轴

第 3 段当前应优先设计为脚本友好，脚本负责：

- 采集
- 整理
- 时间对齐
- 初步过滤降噪
- 结构化输出

### MongoDB v1 脚本组织规则

第一版当前只规范 `domains/mongodb/scripts/` 下的第 3 段脚本。

目录建议：

```text
domains/mongodb/scripts/
  collect/
  normalize/
  helpers/
```

职责边界：

- `collect/`
  - 负责单一采集动作
  - 直接面向 Kubernetes、MongoDB 服务端、日志入口或监控入口取数
  - 产出原始结果或轻度结构化结果
- `normalize/`
  - 负责时间对齐、对象关联、日志降噪、异常摘要和信号归并
  - 产出 `structured_record`、`signal_bundle`、`collection_report` 需要的中间结果或最终片段
- `helpers/`
  - 负责共享函数、命令封装、解析辅助和公共校验
  - 不直接作为主采集入口暴露

当前不建议在 `scripts/` 中放入第 4 段推理脚本，避免把脚本采集职责和 Agent 推理职责混写。

### MongoDB v1 脚本命名规则

当前建议采用：

`<phase>-<target>-<action>`

说明：

- `phase`
  - 当前仅使用：
  - `collect`
  - `normalize`
- `target`
  - 表示采集或治理对象，例如：
  - `pods`
  - `statefulsets`
  - `services`
  - `nodes`
  - `replicaset`
  - `logs`
  - `signals`
- `action`
  - 表示具体动作，例如：
  - `state`
  - `yaml`
  - `rs-status`
  - `current`
  - `previous`
  - `highlights`
  - `bundle`

示例：

- `collect-pods-state.sh`
- `collect-statefulsets-yaml.sh`
- `collect-replicaset-rs-status.sh`
- `collect-logs-current.sh`
- `collect-logs-previous.sh`
- `normalize-logs-highlights.py`
- `normalize-signals-bundle.py`

命名原则：

- 文件名不重复 `mongodb` 前缀，因为目录本身已经限定在 `domains/mongodb/scripts/`
- 一个脚本只做一类动作，不在一个脚本里混采集、治理和推理
- 优先使用可读的动作名，不为追求短名牺牲可理解性

### 第 3 段脚本最小调用合同

当前建议第 3 段脚本统一采用以下 3 个入口参数：

- `--context-file`
- `--output-file`
- `--artifact-dir`

使用原则：

- `context-file`
  - 由插件运行时生成
  - 提供本次脚本执行所需的上下文输入
- `output-file`
  - 由脚本写出机器可读结果
  - 作为后续合并到 `structured_record`、`signal_bundle`、`collection_report` 的直接输入
- `artifact-dir`
  - 用于保存原始命令输出、原始日志、临时采集文件等附属产物

当前不建议将机器可读结果依赖在 `stdout` 中，避免插件实现和日志输出耦合。

### 指标采集策略

第 3 段的指标采集当前采用“双来源策略”：

1. 默认先从 `Prometheus` 或现有监控系统获取历史监控数据
2. 按需直连服务端做实时补充确认

原则：

- 历史分析优先 `Prometheus`
- 实时确认和缺口补充按需直连服务端
- 所有指标数据应尽量带时间戳和来源标记

### 日志采集策略

第 3 段的日志采集当前采用分层顺序：

1. 默认先查现场容器级日志
2. 再查日志系统
3. 仅在怀疑节点级问题时，再补节点系统日志

原则：

- 现场容器级日志优先用于快速确认当前异常和获取重启前后日志
- 日志系统优先用于历史窗口检索、聚合分析和时间线重建
- 节点系统日志仅作为节点级问题的补充信号

## 5. 第 4 段：推理诊断与深入验证

### 目标

- 基于证据链生成并维护多条假设
- 逐条验证、排除和收敛最可信路径

### 当前范围

当前先保留通用推理层，不纳入代码逻辑分析、代码路径追踪和复现脚本生成等深入层能力。

### 第 4 段的执行主轴

第 4 段当前应优先设计为 Agent 友好，Agent 负责：

- 假设生成
- 因果路径归纳
- 反证条件归纳
- 证据缺口提取
- 验证动作生成
- 阶段性结论整理

### 第 3 段到第 4 段的接口

第 3 段脚本当前建议至少输出以下三类内容，供第 4 段 Agent 使用：

1. `structured_record`
2. `signal_bundle`
3. `collection_report`

#### `structured_record`

用于保存结构化对象、拓扑、状态和日志明细。

#### `signal_bundle`

用于保存信号治理结果，例如：

- 异常信号列表
- 对象关联结果
- 时间线摘要
- 处理后日志摘要

#### `collection_report`

用于保存采集过程本身的结果和缺口，例如：

- 采集动作列表
- 成功项
- 失败项
- 留白项
- 缺失证据说明

### 三类接口输出的最小字段集

#### `structured_record`

- `summary`
- `details`
- `generated_at`

#### `signal_bundle`

- `signal_overview`
- `abnormal_signals`
- `object_signal_links`
- `timeline_summary`
- `processed_log_highlights`
- `generated_at`

#### `collection_report`

- `collection_actions`
- `successful_items`
- `failed_items`
- `blank_items`
- `evidence_gaps`
- `generated_at`

### 假设管理原则

- 默认维护多条假设
- 暂不引入优先级或排序机制
- 每条假设都应带证据、反证、验证动作和状态

### 假设建议字段

- `hypothesis_id`
- `title`
- `overview`
- `scope`
- `suspected_root`
- `causal_path`
- `supporting_evidence`
- `contradicting_evidence`
- `falsification_conditions`
- `evidence_gaps`
- `sources`
- `validation_actions`
- `validation_status`
- `confidence`
- `next_step`

### `validation_status`

- `pending`
- `supported`
- `contradicted`
- `inconclusive`

### `confidence`

- `high`
- `medium`
- `low`

### `validation_actions` 最小字段

- `action_id`
- `purpose`
- `target_objects`
- `method`
- `expected_signal`
- `result`
- `status`
- `performed_at`

## 6. 第 5 段：结论整合与知识沉淀

### 目标

- 形成可交接、可复盘、可升级的阶段性结论
- 识别并沉淀可复用知识

### 建议输出结构

1. `conclusion_summary`
2. `knowledge_candidates`

### `conclusion_summary` 建议字段

- `incident_scope`
- `current_findings`
- `validated_hypotheses`
- `rejected_hypotheses`
- `inconclusive_hypotheses`
- `most_likely_conclusion`
- `remaining_risks`
- `next_actions`
- `generated_at`

### `knowledge_candidates` 建议字段

- `candidate_type`
- `title`
- `source_scope`
- `why_reusable`
- `target_asset`
- `status`

## 7. MongoDB 结构化记录

当前 MongoDB 结构化记录采用：

- `summary`
- `details`

其中 `details` 当前建议分块为：

- `cluster_info`
- `components`
- `statefulsets`
- `pods`
- `services`
- `nodes`
- `replica_members`
- `raw_logs`
- `processed_logs`

MongoDB 结构化记录样例见：

- [domains/mongodb/examples/triage-record.example.yaml](/home/stephen/AI/midstack-triage/domains/mongodb/examples/triage-record.example.yaml)

## 8. 外部参考

当前外部参考归档见：

- [docs/REFERENCES.md](/home/stephen/AI/midstack-triage/docs/REFERENCES.md)
- [docs/SIGNAL_GOVERNANCE_PATTERNS.md](/home/stephen/AI/midstack-triage/docs/SIGNAL_GOVERNANCE_PATTERNS.md)
