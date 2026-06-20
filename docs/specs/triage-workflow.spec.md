---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Triage Workflow Spec

本文件用于沉淀当前已经基本稳定的排障主流程规范，作为项目后续 `runbook`、`skill`、结构化记录、脚本和知识沉淀的基线。

讨论细节仍保留在[排障流程讨论](../decisions/triage-workflow-discussion.md)。

## 1. 主流程

当前排障主流程采用 5 段式：

1. `受理与启动`
2. `环境确认与对象盘点`
3. `信号采集与治理`
4. `推理诊断与深入验证`
5. `结论整合与知识沉淀`

## 2. 第 1 段：受理与启动

### 目标

- 判断本次输入应创建新的 incident，还是继续补齐已有 blocked incident
- 保存最小输入、第一手原始线索和会话上下文
- 记录用户声明的环境模式和接入场景

Phase 1 不直接负责 SSH、kubectl 或对象盘点是否可用；这些会进入 Phase 2
readiness gate。

### 最小必填输入

- 中间件类型
- 环境模式，默认 `remote`
- `remote` 模式下的 K8s 环境 IP
- `remote` 模式下的账号
- `remote` 模式下的密码

### 高价值可选输入

- 客户提供的原始故障线索
- 端口

### 故障时间语义

Phase 1 应在 `phase1-intake.yaml` 中记录 `incident_time`。当前支持：

- `current_active`：默认值，表示故障按“当前仍在发生”处理，后续 live
  collection 可用来验证现场状态。
- `historical_resolved`：用户线索明确表示故障发生在过去或已经恢复，例如
  “昨天发生过”“现在已恢复”。这种情况不能把当前 live 状态直接当作故障现场。

`historical_resolved` 不应抬高进入排障的门槛。Phase 2 继续执行当前
remote/local/offline readiness gate，但应输出 warning：当前 live collection
只能证明“现在状态”，不得单独用于推断过去故障根因。用户能提供故障时间窗口、
Kubernetes events、日志、监控截图/链接或已有 artifact 目录时，应作为后续证据
补充；缺失这些材料不阻断当前排障启动。

### 环境模式

- `remote`
  - 当前默认主路径：Agent/runtime 通过 SSH 进入跳板机或故障环境，再用远端 `kubectl` 做只读确认和采集。
- `local`
  - 表示 Agent/runtime 已经在故障集群或控制面机器上。当前仅完成 Phase 1 识别和引导，本地 live executor 完成前不得隐式回退到 SSH。
  - 当远程接入信息缺失或用户显式选择 `local` 时，Phase 1 可做轻量本地 `kubectl` context 探测，并把结果作为 `local_context` 提示；这只是 intake hint，不代表本地采集已实现。
- `offline`
  - 表示用户只有已有 incident、fixture、remote-run、日志、截图或手工命令输出。若提供完整离线证据目录，`/start` 可直接进入 `ready` 并转向离线分析。

### 接入场景分类

第 1 段除 `environment_mode` 外，还应在 `phase1-intake.yaml` 中记录
`intake_scenario`。`environment_mode` 只表达取证机制，`intake_scenario`
表达用户当前接入场景和证据来源。

当前分类：

- `remote_ssh`：当前主路径，Agent/runtime 可通过 SSH 进入目标环境。
- `local_fault_cluster`：runtime 已在故障集群或控制面机器上，当前仅识别并阻塞。
- `offline_existing_artifacts`：用户已有 incident、fixture、remote-run、日志或命令输出。
- `offline_production`：线上生产/SRE/告警类输入，当前按已有证据或平台产物引导。
- `manual_guided_offline`：ToDesk、远程桌面、手工粘贴命令输出或截图类输入。

### 输出状态

- `ready`
- `blocked`

### 续填规则

`blocked` 不是终止态。用户补充缺失信息时，应显式带上同一个
`incident_id` 再次执行 `/midstack:start`。第 1 段会复用既有
`input.yaml` 和 `remote-config.yaml` 中已确认的字段，只用新参数补齐缺口。
不带 `incident_id` 的 `/midstack:start` 始终创建新的排障记录。

### Phase 2 readiness gate

`/midstack:start` 会在创建/续填 incident 后继续调用 Phase 2 readiness gate。
Phase 2 负责持续从用户交互中补齐信息，并通过只读命令判断是否可以进入
后续分析。

`ready` 最小条件：

- 已明确需要排查哪个中间件
- 已提供当前执行模式所需的接入信息
- `remote` 模式下已验证远程环境信息有效
- `remote` 模式下可执行基础 Kubernetes 操作
- 已完成目标对象的基础盘点，或已有用户明确指定的 namespace/对象范围
- 如已提供故障线索，线索内容可以被理解（线索本身为可选输入，缺失不构成 `blocked`）
- `incident_time.mode` 可以是 `historical_resolved`；这种情况只增加证据边界
  warning，不作为 ready 阻断条件

当前 `ready` 适用于 `remote` 主路径、具备完整 `artifact_source` 的
`offline` 证据目录，以及显式 `local` 且本机 kubectl context 与对象盘点均通过
的启动路径。显式 `local` 的后续分析采集通过本地 transport 复用 Phase 3
脚本编排，不经过 SSH。

### 本地上下文提示

当用户未提供远程 IP，或显式选择 `local` 时，`/start` 可记录
`phase1-intake.yaml.local_context`。该字段只用于提示当前机器是否存在可用
Kubernetes context，帮助用户判断是否应切换到 `local`、继续提供 SSH 信息，
或改用 `offline` 证据路径。显式 `local` 模式会在 Phase 2 重新探测本机
context；context 可用且目标对象盘点通过时，`/start` 可返回 `ready` 并写入
`local-config.yaml`。`/analyse --execution-mode local` 读取该文件并在本机执行
只读采集脚本。如果 context 缺失、不可达，或 ready incident 缺少
`local-config.yaml`，应返回结构化 `blocked`，并在追问或 next action 中说明
本机 kubectl context 状态。

`local` 模式下，节点状态和调度相关证据优先通过 Kubernetes API 获取，例如
`kubectl get nodes`、`kubectl describe node`、Pod 的 `nodeName` 和事件。需要读
节点主机文件的证据，例如 kubelet 侧 Pod volume/file log 路径，不属于普通
local 能力；必须在 `local-config.yaml.access.node_access` 中显式开启对应节点访问。
默认 `node_access.mode=kubernetes_api_only` 且 SSH disabled，认证偏好为
`key_or_agent`。启用节点 SSH 后，优先使用集群节点间常见的 SSH key/agent 免密；
只有配置了 password 时才走 `sshpass`。缺少该能力时，相关脚本应返回结构化
`blocked` / evidence gap，不得在 local 模式下猜测凭据并 SSH 到节点。

### 典型 `blocked` 条件

- 缺少必要工具，例如 `sshpass`
- 无法通过提供的远程信息完成基础连通性验证
- 远程环境没有 Kubernetes
- 无法执行基础 Kubernetes 操作，例如 `kubectl exec`
- 显式 `local` 模式下，本机 kubectl context 缺失或不可达
- 显式 `local` analyse 时，ready incident 缺少 `local-config.yaml`
- 显式 `local` 下需要节点主机文件证据，但 `node_access` 未启用
- 远程环境中不存在目标中间件，或当前入口无法触达目标环境

## 3. 第 2 段：环境确认与对象盘点

### 目标

- 补齐 Phase 1 尚未拿到的必要输入
- 确认目标环境和目标集群
- 执行接入 readiness gate，例如 `sshpass`、SSH、kubectl client、Kubernetes context、kubectl exec 能力
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

### `script_id` 与文件名的关系

- 文件名采用 `<phase>-<target>-<action>`：用连字符，不含中间件前缀
- 资产登记用的 `script_id` 采用 `<middleware>.<phase>.<target>.<action>`：用点号，`action` 段用下划线
- 两者一一对应，例如文件 `collect-replicaset-rs-status.sh` 对应 `script_id` `mongodb.collect.replicaset.rs_status`
- `manifest.yaml` 以 `script_id` 为准登记，`source` 字段指向对应文件名

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

> 三类文件在 incident 记录中的落点与职责以[单次排障记录规范](incident-record.spec.md)为准。

#### `structured_record`

- `summary`
- `details`
- `generated_at`
- `updated_at`

#### `signal_bundle`

- `signal_overview`
- `abnormal_signals`
- `object_signal_links`
- `timeline_summary`
- `processed_log_highlights`
- `generated_at`
- `updated_at`

#### `collection_report`

- `collection_actions`
- `successful_items`
- `failed_items`
- `blank_items`
- `evidence_gaps`
- `generated_at`
- `updated_at`

### 假设管理原则

- 默认维护多条假设
- 暂不引入优先级或排序机制
- 每条假设都应带证据、反证、验证动作和状态

### 假设字段

基线字段（以 [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml) 为准，本清单为摘要）：

- `hypothesis_id`
- `statement`
- `causal_path`
- `supporting_evidence`
- `counter_evidence`
- `disconfirming_conditions`
- `evidence_gaps`
- `validation_actions`（基线子字段：`action`、`status`、`result`）
- `validation_result`

以下为**尚未进入设计基线**的候选扩展字段，按需讨论后先补入模板再使用：

- 假设描述类：`title`、`overview`、`scope`、`suspected_root`、`sources`
- 假设评估类：`confidence`（`high` / `medium` / `low`）、`next_step`
- 验证动作扩展：`action_id`、`purpose`、`target_objects`、`method`、`expected_signal`、`performed_at`

### `validation_result`

取值枚举见 [core/taxonomies/status-types.yaml](../../core/taxonomies/status-types.yaml) 的 `hypothesis_validation_result`：

- `supported`
- `refuted`
- `insufficient`

## 6. 第 5 段：结论整合与知识沉淀

### 目标

- 形成可交接、可复盘、可升级的阶段性结论
- 识别并沉淀可复用知识

### 建议输出结构

1. `conclusion_summary`
2. `knowledge_candidates`

### `conclusion_summary` 建议字段

设计基线（`core/templates/analysis.template.yaml`）当前采用：

- `statement`
- `confidence`
- `impact_scope`
- `primary_cause_category`
- `evidence`
- `limitations`

`next_actions` 不在 `conclusion_summary` 内，而是 `analysis.yaml` 的顶层块，与设计基线一致。

以下为 `conclusion_summary` 的可选扩展字段，按需使用：

- `current_findings`
- `validated_hypotheses`
- `rejected_hypotheses`
- `inconclusive_hypotheses`
- `most_likely_conclusion`
- `remaining_risks`
- `generated_at`

### `knowledge_candidates` 字段

完整模型以 [core/templates/knowledge-candidate.template.yaml](../../core/templates/knowledge-candidate.template.yaml) 为准；`analysis.yaml` 中的 `knowledge_candidates` 是其摘要子集，见 [core/templates/analysis.template.yaml](../../core/templates/analysis.template.yaml)。`candidate_type` 枚举见 [core/taxonomies/candidate-types.yaml](../../core/taxonomies/candidate-types.yaml)。

### `verification_requests` 字段

`analysis.yaml` 顶层可包含 `verification_requests`，用于记录 Phase 4 推理后仍需补采或验证的证据请求。该字段只表达计划，不表示已经执行。

- 仓库内声明为只读的脚本或结构化命令是一等资产，允许标记为 `asset_tier: first_class` 与 `execution_policy: auto_allowed`。
- 临时只读命令是二等资产，必须先经过只读 guardrail 后才能进入执行路径。
- 会改变 Kubernetes、数据库、文件系统、进程或网络状态的动作必须标记为 `execution_policy: blocked`，不得自动执行。
- 历史经验、runbook 和知识资产可以启发 `verification_requests`，但不能绕过当前故障证据和风险分级。

### `reasoning_timeline` 字段

`analysis.yaml` 顶层应包含 `reasoning_timeline`，用于把 Phase 3 的 `timeline_summary`、异常信号、Kubernetes events 和采集动作整理成可审计的推理时间线。

- `events` 按时间优先、未知时间靠后排序，事件需保留 `source`。
- 日志行只包含 `HH:MM:SS` 等本地时刻片段时，可记录 `time_precision: log_local_time`，但不得伪造成跨天/跨时区可比较的绝对时间。
- `findings` 只表达时间顺序观察以及它关联的假设，不得把历史经验或用户线索当作当前因果证据。
- `report.md` 应展示关键时间线，帮助读者看到“什么时间发生了什么关键事项”。
- 如果时间线缺失，应显式说明缺失，而不是伪造时间。

### `deepening_findings` 字段

`analysis.yaml` 顶层可包含 `deepening_findings`，用于记录 Phase 4 对已采证据做的机制深化检查。

- 该字段面向“为什么会发生”的追问，记录领域不变量冲突、当前证据反证和机制推进观察。
- 每条 finding 必须有 `evidence_refs`，只引用当前 incident 证据。
- finding 可以支持或反驳某个候选机制，但不能绕过 `hypotheses` 和 `conclusion_summary` 的证据边界。
- MongoDB 初始不变量包括 replica set config/member/quorum 多视角一致性，以及当前 TCP 连通性对持续网络分区假设的反证。

### 经验召回预留字段

`analysis.yaml` 顶层预留 `retrieval_context`、`experience_matches` 和 `source_boundaries`，用于未来接入历史经验或向量库召回。

- `retrieval_context` 从当前 incident 的 scenario、信号、对象和证据缺口生成召回上下文。
- `experience_matches` 在未实现真实召回前保持空列表。
- `source_boundaries` 必须说明历史经验、runbook、知识资产和用户线索只能作为假设来源或验证路径来源，不能直接作为当前故障结论证据。

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

- [domains/mongodb/examples/triage-record.example.yaml](../../domains/mongodb/examples/triage-record.example.yaml)

## 8. 外部参考

当前外部参考归档见：

- [外部参考资料](../references.md)
- [信号治理模式](../concepts/signal-governance.md)
