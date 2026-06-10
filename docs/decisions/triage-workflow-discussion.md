---
status: archived
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

> ⚠️ 已归档的历史讨论稿。结论以 `docs/specs/` 为准，本文内容可能已过时。

# Triage Workflow Discussion

本文件用于记录排障主流程的专项讨论。

记录原则：

- 按 5 个主流程分章节
- 每个主流程下继续按子主题记录讨论细节
- 已确认结论、待继续讨论、外部参考都尽量落在对应章节下
- 与流程无直接关系的其他讨论仍保留在 [docs/DISCUSSIONS.md](discussions-archive.md)

## 1. 受理与启动

### 已确认结论

- 排障起点应采用“最小可启动输入模型”，而不是假设一开始就有完整上下文。
- 当前最小必填输入包括：
  - 中间件类型
  - K8s 环境 IP
  - 账号
  - 密码
- 客户提供的原始故障线索属于高价值输入，但不强制要求一定存在。
- 如果客户提供多个 IP，默认以第一个 IP 作为排障入口和跳板机。
- 端口不是必填项，默认可按 22 处理；客户提供非默认端口时再记录。

### 原始故障线索处理

- 不应将该字段狭义命名为“日志”，更合适的抽象是“客户提供的故障线索”或“原始报障信息”。
- 线索可能是：
  - 日志
  - 现象描述
  - 组件状态信息
  - 告警内容
  - 其他客户原话
- 初始受理阶段只保存原文，不改写、不提前下结论。
- 后续分析阶段再做分类、摘要、关键词提取和富化。

### 富化框架

当前已讨论出一套 10 项富化框架，分为核心项和可选项。

核心项：

1. `raw_text`
2. `clue_type`
3. `normalized_summary`
4. `keywords`

可选项：

5. `source`
6. `reported_time`
7. `suspected_scope`
8. `suspected_objects`
9. `severity_hint`
10. `confidence`

### 已确认的小枚举

`clue_type`：

- `log`
- `symptom`
- `status`
- `alert`
- `change`
- `unknown`

`severity_hint`：

- `high`
- `medium`
- `low`
- `unknown`

### 处理原则

- `keywords` 采用轻量提取，少而准，建议 3-8 个。
- `normalized_summary` 应是一句简短、可检索的标准问题描述。
- 原始线索与派生信息同时保留，避免二次加工覆盖第一手证据。

### 待继续讨论

- 受理阶段最终要产出哪些明确输出
- 是否还需要补充“报障来源”“报障人”“业务影响描述”等字段

### 本轮收敛提案

#### 阶段职责

`受理与启动` 的职责不是解决问题，而是完成以下几件事：

- 让排障任务可以正式启动
- 保存第一手原始信息，避免证据丢失
- 确认是否具备进入环境的基本条件
- 形成一个最小但可执行的排障起点

#### 不属于本阶段的事情

以下内容不应在本阶段强行完成：

- 完整拓扑识别
- 目标集群的最终确认
- 根因判断
- 大量环境信息补录
- 深入技术分析

#### 输入

最小必填输入：

- 中间件类型
- K8s 环境 IP
- 账号
- 密码

高价值可选输入：

- 客户提供的原始故障线索
- 端口

#### 典型动作

本阶段建议至少完成以下动作：

1. 建立排障条目
   - 为本次报障建立唯一记录
2. 记录最小接入信息
   - 保存 IP、账号、密码、端口等接入信息
3. 保存原始故障线索
   - 不改写、不压缩原文
4. 做轻量线索富化
   - 仅补充最基础的 `clue_type`、`normalized_summary`、`keywords`
5. 判断是否具备启动条件
   - 至少能判断“是否可以尝试进入环境”
6. 列出当前已知与未知
   - 明确哪些信息已经有，哪些需要在后续阶段补齐

#### 建议输出

本阶段结束时，至少应产出：

- 一个已建立的排障任务记录
- 一份最小接入信息
- 一份原始故障线索原文
- 一份轻量富化结果
- 一份待补充信息清单
- 一个启动状态：
  - `ready`
  - `blocked`

当前确认：

- 启动状态只保留两种：
  - `ready`
  - `blocked`
- 当前不引入第三种中间状态，避免受理阶段输出口径变模糊

#### 完成标准

满足以下条件时，可认为“受理与启动”完成：

- 已有最小必填输入
- 原始故障线索已保存或已明确暂时缺失
- 已能判断是否具备进入环境的基础条件
- 已形成下一阶段要补齐的信息列表

#### 当前倾向

- 本阶段更像“启动和建档”，不是“排障分析”
- 本阶段要严控范围，避免一上来就滑入环境排查和根因推理

### `blocked` 判定条件

当前已讨论出的典型 `blocked` 条件包括：

- 本地或执行环境缺少必要工具，例如 `sshpass`
- 无法通过提供的远程信息完成基础连通性验证，例如无法执行 `ssh ... echo ok`
- 远程环境中不存在 Kubernetes 环境
- 远程环境无法执行基础 Kubernetes 操作，例如 `kubectl exec`
- 远程环境中不存在目标中间件，或当前入口无法触达到目标中间件环境

当前理解：

- `blocked` 应优先表示“排障无法继续启动或无法继续进入下一阶段”
- `blocked` 条件应尽量设计为可执行、可验证，而不是抽象描述
- 优先围绕工具缺失、远程接入失败、Kubernetes 不可用、目标环境不存在这类硬阻塞条件判断

待继续讨论：

- 是否还要把“认证成功但权限不足”列入 `blocked`
- 是否需要区分“临时阻塞”和“明确无效输入”

### `ready` 最小判定条件

当前已确认的 `ready` 最小条件包括：

- 已提供远程环境信息
- 已验证远程环境信息有效
- 可执行基础的 Kubernetes 操作
- 已明确需要排查哪个中间件
- 已提供的故障线索可以被理解

当前理解：

- `ready` 不要求已经掌握完整架构和完整拓扑
- `ready` 只要求已经具备进入环境并进入下一阶段的基础条件
- 只要可以开始做“环境确认与对象盘点”，就应判定为 `ready`

## 2. 环境确认与对象盘点

### 已确认结论

- 这一阶段的重点是避免查错环境、查错集群、查错对象。
- 在 PaaS 中间件场景里，多集群、多组件、多实例、多入口是高频现实问题。
- 需要确认：
  - 目标环境
  - 目标集群
  - 目标实例组
  - 部署架构
  - 相关组件、Pod、节点、Service、PVC 等对象

### 待继续讨论

- 这一阶段的最小完成标准是什么
- 多套集群如何标准化标识
- 不同中间件的“对象盘点”应抽象到什么程度

### 基于 MongoDB 经验的补充

当前补充的真实经验包括：

- 需要先确认到底是哪一套 MongoDB 集群
- 常见情况之一：
  - 报障人提供的环境里只有一套 MongoDB 分片集群
  - 默认在 `mongo` 命名空间
  - 部署架构通常是 Bitnami 提供的分片集群
- 复杂情况之一：
  - 环境里可能存在两套 MongoDB
  - 部署方式是 operator + CRD
  - 需要从报障人提供的信息中抽取 namespace 或其他实例信息，才能确定具体是哪一套集群

故障场景上的差异：

- 有些场景下，Pod 会整体重启或拉不起来
- 有些场景下，Pod 是 Running 状态，但仍需连接 `mongos`、`mongod` 服务才能发现问题

当前经验归纳：

- 第 2 段的核心首先是确认“哪一套集群”
- 然后需要拿到：
  - 集群 topology 信息
  - 各节点的 Pod 运行状态
  - 成员状态
- 这些信息应尽量带上采集时间戳
- 基于这些信息才能初步判断是否存在异常，并决定是否进入下一阶段的信号治理

### 本轮收敛提案

#### 通俗版完成标准

第 2 段做到下面这个程度，就算基本完成：

- 已经知道这次查的是哪一套集群
- 已经知道这套集群大概是怎么部署的
- 已经把这套集群里关键对象摸出来了
- 已经看到关键对象当前是否明显异常

#### 更具体的完成标准

对 MongoDB 来说，本阶段至少应确认：

- 目标 namespace
- 目标集群或实例组
- 部署方式
  - 例如 Bitnami 分片集群
  - 或 operator + CRD
- 集群 topology
  - 例如 shard、config server、mongos、replica set 关系
- 关键 Pod 的运行状态
- 关键成员状态
- 关键状态对应的采集时间戳

#### 当前倾向

- 第 2 段不要求已经定位根因
- 但至少要能回答“查的是谁、它长什么样、现在表面状态怎么样”
- “现在表面状态怎么样”应尽量带时间戳，避免后续无法对齐时间线

### MongoDB 关键对象最小集合

当前针对 MongoDB 在第 2 段的最小对象集合建议如下。

#### 1. 环境与集群标识对象

- namespace
- 集群名或实例组标识
- 部署方式
  - 例如 Bitnami
  - 或 operator + CRD

用途：

- 确认到底是哪一套 MongoDB
- 区分多套集群场景

#### 2. 拓扑对象

- `mongos`
- `config server`
- `shard`
- `replica set`

用途：

- 确认分片集群 topology
- 识别各类组件之间的关系

#### 3. Kubernetes 运行对象

- Pod
- Node
- Service
- PVC

用途：

- 确认对象是否存在
- 确认运行状态和调度位置
- 识别是否存在基础运行层异常

#### 4. MongoDB 成员对象

- PRIMARY
- SECONDARY
- ARBITER
- 其他异常成员状态

用途：

- 确认副本集成员角色分布
- 确认成员状态是否正常

#### 5. 时间信息

对上述关键对象的状态采集，应尽量带上：

- 采集时间戳
- 如可获得，最近变化时间

#### 当前倾向

- 第 2 段先关注“关键对象最小集合”
- 不要求一开始枚举所有 MongoDB 内部对象
- 只要足够支撑“确认目标集群、确认拓扑、确认表面状态”即可
- 上述最小集合中的关键对象都属于必查项，而不是可选项

#### 补充要求

- 如果已经收敛到具体某个 Pod，则还需要拿到该 Pod 最近的日志
- 最近日志应作为第 2 段中“对象盘点”和“表面状态确认”的补充证据
- 这类日志不等于深入分析，但足以帮助判断该对象是否已经存在明显异常

### 第 2 段到第 3 段的留存边界

当前已确认：

- 除日志类信息外，第 2 段获取到的其他信息通常体量较小，应整体留存并带入第 3 段
- 这些信息包括但不限于：
  - 集群标识信息
  - namespace
  - 部署方式
  - topology 信息
  - Pod / Node / Service / PVC 状态
  - 成员状态
  - 采集时间戳

#### 节点故障场景补充

如果已经判断可能是具体节点故障，则第 2 段还需要补充获取：

- 该节点上的相关 Pod 信息
- 对应 `StatefulSet` 控制器等编排 YAML 详情

用途：

- 判断是否可能存在 OOM
- 判断是否可能存在资源调度问题
- 判断编排层是否存在明显异常

#### 日志留存原则

- 日志信息原则上先完整保留
- 如果 Pod 一直重启，需要同时获取：
  - 重启前日志
  - 重启后日志
- 由于日志体量可能较大，不要求第 2 段就完成完整分析
- 进入第 3 段前，应对日志做过滤和降噪
- 过滤降噪后的日志结果应作为第 3 段的重要输入留存

#### 当前倾向

- 第 2 段负责“把该带走的原始证据先带走”
- 第 3 段再重点处理日志降噪、信号治理和更系统的关联分析

## 3. 信号采集与治理

### 已确认结论

- 这一阶段不应只理解为“收集事实”，而应明确包括信号治理。
- 需要显式加入：
  - 去噪
  - 归类
  - 关联
  - 范围收敛
  - 时间线重建

### 当前理解

信号可能包括：

- 状态
- 日志
- 监控
- 报错
- 变更

并且应与以下对象建立关联：

- 组件
- 实例
- Pod
- 节点
- 服务

### 待继续讨论

- 在本项目里，什么算“信号”
- 信号治理的最小动作集合是什么
- 哪些信号优先级最高
- 时间线如何组织

### 外部参考带来的启发

基于当前已归档的外部参考资料，第 3 段可以先这样理解：

- Google SRE 强调：
  - 先从 telemetry 和 logs 观察系统当前状态
  - 再基于这些观察形成假设并验证
- Azure / Microsoft 强调：
  - 不只是“搜日志”，而是 gathering evidence → hypothesis generation → validation → conclusion
  - 日志、指标、追踪、资源属性、活动记录需要做关联
  - 所有原始数据尽量带时间戳
- IBM 强调：
  - 需要回答问题发生在哪里、什么时候发生、在什么条件下发生
  - 需要建立详细时间线
- Datadog 强调：
  - 时间线应成为调查主轴
  - 需要按时间顺序记录动作、变化、证据和判断
- PagerDuty 强调：
  - 历史事件模式可以帮助缩小范围，但不能替代当前证据

#### 当前收敛理解

因此，本项目里的“信号治理”不只是收集信号，而是至少包括：

- 采集
- 时间对齐
- 对象关联
- 过滤降噪
- 粗分类
- 为后续推理诊断准备证据链

### 参考资料里的常见做法

基于当前参考资料，外部常见做法大致是：

1. 收集上下文和原始证据
   - Google SRE：从问题报告出发，查看 telemetry 和 logs
   - Azure：聚合 metrics、logs、deployment history、activity logs、resource properties
2. 按时间组织
   - IBM：围绕“问题何时发生”建立详细时间线
   - Datadog：将 timeline 作为调查主轴，按时间顺序记录证据和动作
3. 做信号关联
   - Azure：关联日志、指标、资源属性和活动记录
   - Azure Monitoring：通过 correlation information / activity ID 将分散数据合并
4. 过滤、清洗、归并
   - Azure Monitoring：通过独立服务对 instrumentation data 做 consolidates、filters、cleans
   - Google SRE：日志应支持不同 verbosity，便于在细节与噪音之间切换
5. 为推理诊断准备证据链
   - Azure SRE Agent：evidence gathering → hypothesis generation → validation → conclusion
   - PagerDuty：可参考历史模式，但不能替代当前证据

#### 可借鉴的动作顺序

结合这些资料，第 3 段可参考的动作顺序可以先定为：

1. 汇总所有已获取信号
2. 给信号补时间戳或统一时间基准
3. 将信号绑定到具体对象
4. 对日志和重复状态做过滤降噪
5. 做粗粒度分类和归并
6. 形成可供第 4 段使用的证据链和时间线

当前确认：

- 第 3 段“信号采集与治理”当前采用这 6 个动作作为主顺序
- 后续对 MongoDB、Kafka、Redis 等中间件的具体实现，可以在此顺序下做适配，但不轻易改变主顺序

### 基于 MongoDB 的信号清单补充

当前已补充的 MongoDB 典型信号包括：

#### 1. Kubernetes 对象状态信号

- `StatefulSet` 状态
- Pod 状态
  - 创建时间
  - 重启次数
  - 上一次重启时间
- Node 状态

这些信号主要用于判断：

- 是否存在调度异常
- 是否存在频繁重启
- 是否存在节点侧异常
- 是否存在编排层异常

#### 2. 分片集群与副本集 topology 信号

- 各分片 topology 信息
- 各副本集 topology 信息
- `rs.status()` 中的节点状态
- 选举时间
- 任期
- 主从同步时延

这些信号主要用于判断：

- 副本集角色分布是否正常
- 是否发生过选主或频繁选举
- 是否存在复制延迟
- 分片集群整体 topology 是否异常

#### 3. 日志信号

- Pod 最近日志
- 如存在重启，重启前后的日志
- MongoDB 组件日志中的异常、告警和错误信息

这些信号主要用于判断：

- 是否存在启动失败
- 是否存在连接异常
- 是否存在复制异常
- 是否存在资源或存储相关报错

#### 当前结论

对于 MongoDB 来说，至少以下内容应明确视为“信号”：

- `StatefulSet`、Pod、Node 的状态信息
- 分片和副本集的 topology 信息
- `rs.status()` 相关成员状态和复制状态
- 选举、任期、同步时延等副本集行为信息
- 组件和 Pod 的日志信息

### 参考资料中的通用信号类型

基于当前参考资料，外部常见的信号类型通常包括：

- Metrics / 状态值
- Logs / 日志
- Traces / 调用链
- Changes / 变更事件
- Activity / Event / Alert
- Resource state / Topology / Dependency
- Timeline entries / 时间线条目

当前理解：

- “信号”不是日志的同义词
- 信号本质上是排障过程中可被采集、可被关联、可被用于推理的证据
- 本项目在中间件场景下，尤其重视对象状态、topology、日志、事件、变更和时间线信号

### MongoDB 第 3 段信号分类表

#### 1. 对象状态信号

包括：

- `StatefulSet` 状态
- Pod 状态
- Pod 创建时间
- Pod 重启次数
- Pod 上一次重启时间
- Node 状态
- Service 状态
- PVC 状态

主要用途：

- 判断编排层是否异常
- 判断调度和运行层是否异常
- 判断是否存在频繁重启或基础设施层异常

#### 2. Topology 信号

包括：

- 分片 topology
- 副本集 topology
- shard / config server / `mongos` / `mongod` 关系
- 集群中各关键组件分布

主要用途：

- 判断目标集群结构是否完整
- 判断关键组件关系是否异常
- 为后续对象关联和根因推理提供结构基础

#### 3. 副本集行为信号

包括：

- `rs.status()` 节点状态
- PRIMARY / SECONDARY / ARBITER 分布
- 选举时间
- 任期
- 主从同步时延
- 异常成员状态

主要用途：

- 判断是否发生选主
- 判断是否存在频繁选举
- 判断复制链路和成员健康是否异常

#### 4. 日志信号

包括：

- Pod 最近日志
- 重启前日志
- 重启后日志
- `mongos` / `mongod` 组件日志中的异常、告警和错误信息

主要用途：

- 判断启动失败、连接异常、复制异常、存储异常等具体表现
- 为第 4 段深入验证提供高价值证据

#### 5. 事件与变更信号

包括：

- K8s Event
- 最近部署或重启行为
- 编排 YAML 变化
- 调度变化

主要用途：

- 判断异常是否与最近变更相关
- 为时间线重建提供锚点

#### 6. 时间线信号

包括：

- 采集时间戳
- Pod 创建时间
- 上一次重启时间
- 选举时间
- 故障线索中提及的时间
- 事件发生时间

主要用途：

- 对齐不同信号
- 重建故障演化过程
- 辅助判断先后顺序和因果路径

### MongoDB 信号治理优先级建议

当前建议按“先快速缩小范围，再解释内部异常，最后处理高体量细节”的原则治理 MongoDB 信号。

#### 默认优先级

1. 对象状态信号
2. 时间线信号
3. Topology 信号
4. 副本集行为信号
5. 事件与变更信号
6. 日志信号

#### 默认优先级的理由

- 先看对象状态，最快判断运行层是否直接异常
- 再对齐时间，避免后续信号解释混乱
- 再确认 topology，防止把异常挂错对象或挂错集群结构
- 在此基础上再看副本集行为，理解 MongoDB 内部机制异常
- 事件与变更有助于解释“为什么现在开始异常”
- 日志量最大、噪音最多，默认放在后面治理更稳

#### 例外场景

如果故障场景属于以下类型：

- Pod 拉不起来
- Pod `CrashLoopBackOff`
- 容器反复重启

则日志信号的优先级应临时前置。

建议顺序调整为：

1. 对象状态信号
2. 时间线信号
3. 日志信号
4. 事件与变更信号
5. Topology 信号
6. 副本集行为信号

#### 当前结论

- MongoDB 默认采用“状态 → 时间 → 结构 → 行为 → 变更 → 日志”的治理顺序
- 启动失败、重启类场景可采用“状态 → 时间 → 日志优先”的例外顺序

### 节点系统日志信号

当前建议将节点系统日志视为第 3 段中的补充信号来源，而不是默认基础采集项。

#### 适用场景

以下场景下，节点系统日志通常具备较高价值：

- 节点异常
- `NotReady`
- `DiskPressure`
- `OOM`
- container runtime 异常
- kubelet 异常
- Pod 重启与节点状态变化时间接近

#### 使用原则

- 默认不做全量采集
- 按条件触发
- 优先按时间窗口裁剪
- 优先提取关键系统日志后再决定是否保留原始内容

#### 当前倾向

- 节点系统日志应纳入“信号”体系
- 但不应作为所有场景的默认基础采集项
- 后续结构化记录中可考虑单独设置 `node_system_logs` 分块，而不是混入普通 `raw_logs`

### MongoDB 第 3 段的主辅模式建议

当前建议将 MongoDB 第 3 段的实现模式分为主模式和辅模式。

#### 主模式

1. 实体 / 拓扑关联驱动
2. 时间线驱动
3. 规则 / 阈值驱动

#### 辅模式

4. 先过滤，再用 LLM 做轻理解
5. AI 建议 + 人工确认

#### 当前结论

- MongoDB 本身属于强拓扑系统，因此应以对象和拓扑关系作为治理骨架
- MongoDB 故障往往与状态变化和时间演化强相关，因此时间线应作为治理主轴之一
- 重启次数、成员状态、同步时延、PVC 异常、Node 状态等信号适合先做规则化处理
- LLM 更适合做摘要、归类、候选假设生成和证据链总结
- 在生产环境中，不建议让 LLM 直接统治整个信号治理过程

#### 一句话总结

对 MongoDB 来说，第 3 段建议采用：

“以对象拓扑为骨架，以时间线为主轴，以规则判定为第一轮筛选，再用 LLM 做轻理解和人工辅助确认。”

### MongoDB 分片集群的基础拓扑骨架

当前已确认的 MongoDB 分片集群正常基础结构为：

- 多个 `mongos`
- 一个 `configsvr` 副本集
  - 一主多从
- 多个分片
  - 每个分片都是一个副本集
  - 每个副本集通常是一主多从

#### 当前理解

因此，在第 3 段做对象与拓扑关联时，MongoDB 的基础骨架至少应包括：

- `mongos`
- `configsvr` 副本集
- 各个 shard 副本集
- 各副本集内的 PRIMARY / SECONDARY 成员关系

#### 后续待继续讨论

- 如何把这套 MongoDB 拓扑骨架映射到 Kubernetes 对象
- 如何表达 shard、replica set、Pod、Node 之间的关系

### MongoDB 拓扑骨架到 Kubernetes 对象的映射

当前已确认：MongoDB 拓扑骨架到 Kubernetes 对象的映射方式，必须依赖具体部署架构，不能写死为单一模式。

#### 1. operator + CRD 部署方式

`mongos`：

- 通常是一个 `mongos` 对应一个 `StatefulSet`
- 一个 `StatefulSet` 对应一个 `mongos` Pod
- 每个 `mongos` 通常有独立的 `NodePort` 和 `Service`

`configsvr` 和 shard 副本集：

- 常见情况：
  - 一个 `StatefulSet` 对应多个 Pod
  - 这些 Pod 共同构成一个副本集成员集合
  - 整个副本集通常共用一个 `Service`
- 特殊情况：
  - 一个 `StatefulSet` 只对应一个 Pod
  - 一个 Pod 对应副本集中的一个成员
  - 每个成员拥有独立的 `NodePort`
  - 每个成员也拥有独立的 `Service`

#### 2. Bitnami 部署方式

- 所有组件通常共用一个 `Service`
- `mongos` 通常是一个 `StatefulSet` 对应多个 `mongos` Pod
- `configsvr` 通常是一个 `StatefulSet` 对应一个副本集的所有成员 Pod
- 每个 shard 通常也是一个 `StatefulSet` 对应该副本集的所有成员 Pod

#### 当前理解

因此，在第 3 段做对象拓扑关联时，至少要先判断：

- 当前是 `operator + CRD` 还是 `Bitnami`
- `mongos`、`configsvr`、shard 与 `StatefulSet` 的映射关系是什么
- 副本集成员是“单个 `StatefulSet` 多 Pod”，还是“单成员独立 `StatefulSet` / 独立 `Service`”
- `Service` 和 `NodePort` 是共享还是独立

#### 当前结论

- MongoDB 的 K8s 对象映射必须以部署架构识别为前提
- 如果部署架构识别错误，后续对象盘点、信号关联和故障归因都会偏掉

### MongoDB 对象识别顺序

当前已确认 MongoDB 在进入环境后的对象识别顺序如下：

1. `namespace`
2. `部署架构`
3. `mongos / configsvr / shard` 这些组件
4. `StatefulSet`
5. `Pod`
6. `Service / NodePort`
7. `Node`
8. `副本集成员状态`

#### 当前理解

- 这个顺序既适用于第 2 段“环境确认与对象盘点”，也适用于第 3 段“信号采集与治理”的对象关联入口
- 顺序的核心逻辑是：
  - 先确定范围
  - 再确定结构
  - 再确定 Kubernetes 对象
  - 最后再进入 MongoDB 内部成员状态

### MongoDB 对象识别顺序的最小采集要求

#### Kubernetes 资源

对于 `StatefulSet`、Pod、Service 等 Kubernetes 资源，当前建议：

- 获取 YAML 编排内容

用途：

- 保留编排层原始信息
- 支撑后续判断资源配置、调度、探针、存储等问题

#### Node

对于 Node，当前建议至少获取：

- Node 状态
- Node IP
- Node labels

用途：

- 判断节点是否异常
- 判断调度位置
- 判断节点属性是否影响调度和运行

#### 副本集成员状态

对于副本集成员状态，当前建议至少获取：

- 每个 Pod 内执行 `rs.status()` 后，对应 self 节点的信息

补充规则：

- 如果某个 Pod 内执行失败，则该处信息先留白
- 可尝试从其他节点补全该成员信息

当前理解：

- 成员状态信息以“每个 Pod 自视角的 self 信息”为基础更稳
- 如果直接缺失，应允许部分留白，而不是因为单点失败阻塞整体盘点

### MongoDB 对象识别步骤的最小采集字段（第一部分）

以下字段用于约束第 2 段和第 3 段前半段的最小采集内容。

#### 1. namespace

最小采集字段：

- namespace 名称
- 识别来源
  - 例如客户提供
  - 例如环境扫描确认
- 采集时间戳

用途：

- 锁定排障范围
- 区分多套集群场景

#### 2. 部署架构

最小采集字段：

- 架构类型
  - `operator + CRD`
  - `Bitnami`
  - `unknown`
- 判定依据
  - 例如 CRD 存在
  - 例如资源命名模式
  - 例如 chart / label 信息
- 采集时间戳

用途：

- 决定对象映射方式
- 决定后续盘点路径

#### 3. `mongos / configsvr / shard` 组件

最小采集字段：

- 组件类型
  - `mongos`
  - `configsvr`
  - `shard`
- 组件标识
- 组件所属关系
  - 例如属于哪个 shard
  - 例如属于哪个副本集
- 采集时间戳

用途：

- 建立 MongoDB 基础拓扑骨架
- 明确后续对象挂载关系

#### 4. `StatefulSet`

最小采集字段：

- `StatefulSet` 名称
- 对应组件类型
- 副本数
- 选择器
- YAML 编排内容
- 采集时间戳

用途：

- 确认组件到 K8s 编排对象的映射
- 为后续排查资源、探针、调度和存储问题保留基础信息

#### 5. Pod

最小采集字段：

- Pod 名称
- 所属 `StatefulSet`
- 所属组件类型
- 所在 Node
- Pod 状态
- 创建时间
- 重启次数
- 上一次重启时间
- YAML 关键编排内容或完整 YAML
- 采集时间戳

用途：

- 确认运行层对象状态
- 支撑后续日志采集、节点关联和异常定位

#### 6. `Service / NodePort`

最小采集字段：

- `Service` 名称
- `Service` 类型
  - 例如 `ClusterIP`
  - `NodePort`
  - `LoadBalancer`
- 对应组件类型
- 关联 Pod 或 `StatefulSet`
- 暴露端口信息
- 如存在 `NodePort`，记录 `NodePort` 端口
- 采集时间戳

用途：

- 确认访问入口
- 确认组件与服务暴露关系
- 支撑后续连通性和路由方向判断

#### 7. Node

最小采集字段：

- Node 名称
- Node 状态
- Node IP
- Node labels
- 承载的相关 Pod 列表
- 采集时间戳

用途：

- 确认调度位置
- 判断节点异常是否影响相关 Pod
- 判断节点属性是否与故障有关

#### 8. 副本集成员状态

最小采集字段：

- 副本集标识
- 成员 Pod 名称
- `rs.status()` 中 `self` 节点的状态信息
- 成员角色
  - PRIMARY
  - SECONDARY
  - ARBITER
  - 其他异常状态
- 任期
- 最近选举相关时间
- 同步时延
- 采集时间戳
- 采集是否成功

补充规则：

- 如果某个 Pod 内执行 `rs.status()` 失败，则对应字段允许留白
- 如可行，应从其他成员视角补全该成员信息
- 留白必须显式标记为“采集失败”或“待补全”，不能默默缺失

用途：

- 确认副本集成员状态
- 确认选主和同步行为
- 为后续第 3 段信号治理和第 4 段推理诊断提供基础事实

### MongoDB 结构化记录格式选择

当前已确认：

- 先采用“方案 4：摘要 + 明细”
- 在 `details` 内部结合“方案 2：按对象分类分块”

#### 当前理解

也就是说，MongoDB 的结构化记录先采用两层组织：

1. `summary`
   - 放关键摘要信息
2. `details`
   - 按对象分类分块存放完整明细

#### 当前建议的 `details` 分块

- `cluster_info`
- `components`
- `statefulsets`
- `pods`
- `services`
- `nodes`
- `replica_members`
- `raw_logs`
- `processed_logs`

#### 当前倾向

- 先避免一上来就设计成复杂图模型
- 先保证人可读、脚本可处理、后续易扩展
- 等 MongoDB、Kafka 等多中间件都跑通后，再考虑是否演进到对象主表 + 关系表模式

### MongoDB 结构化记录草案

当前建议 MongoDB 的结构化记录先采用如下轮廓：

```yaml
summary:
  cluster_id:
  namespace:
  deployment_architecture:
  topology_summary:
  key_object_status:
  key_replica_status:
  key_findings:
  current_scope:
  collected_at:

details:
  cluster_info:
  components:
  statefulsets:
  pods:
  services:
  nodes:
  replica_members:
  raw_logs:
  processed_logs:
```

#### `summary` 的定位

`summary` 用于快速回答：

- 当前查的是哪一套 MongoDB
- 部署架构是什么
- 基础拓扑是什么
- 哪些关键对象当前异常
- 哪些副本集成员状态异常
- 当前已经看到的关键发现是什么
- 当前影响范围大致在哪里
- 这些结论对应的采集时间是什么时候

#### `details` 的定位

`details` 用于保存完整明细，供第 3 段和第 4 段继续使用。

各分块当前建议含义如下：

- `cluster_info`
  - 集群标识、namespace、架构识别、来源信息
- `components`
  - `mongos`、`configsvr`、shard 的结构化列表
- `statefulsets`
  - `StatefulSet` 对象明细和编排信息
- `pods`
  - Pod 对象明细、状态、重启信息
- `services`
  - `Service` / `NodePort` 明细
- `nodes`
  - Node 状态、IP、labels、承载 Pod 信息
- `replica_members`
  - 各副本集成员状态、自视角 `rs.status()` 结果、采集成功情况
- `raw_logs`
  - 原始日志内容
- `processed_logs`
  - 过滤降噪后的日志结果

#### 当前倾向

- `summary` 保持短、稳、便于快速浏览
- `details` 保持完整、面向后续分析
- 日志原文与处理结果同时保留

### MongoDB `summary` 草案细化

当前建议 `summary` 保留以下字段：

#### 1. `cluster_id`

含义：

- 当前确认的目标集群标识

建议内容：

- cluster 名称或实例组标识

#### 2. `namespace`

含义：

- 当前排障对象所在 namespace

#### 3. `deployment_architecture`

含义：

- 当前识别出的部署架构

建议内容：

- `operator + CRD`
- `Bitnami`
- `unknown`

#### 4. `topology_summary`

含义：

- 用一句简短描述当前 MongoDB 拓扑骨架

建议内容：

- `2 mongos + 1 configsvr rs + 3 shard replica sets`

#### 5. `key_object_status`

含义：

- 关键 Kubernetes 对象的摘要状态

建议内容：

- Pod 是否全部 Running
- 是否存在异常 Node
- 是否存在异常 PVC
- 是否存在异常 `StatefulSet`

#### 6. `key_replica_status`

含义：

- 关键副本集成员状态摘要

建议内容：

- PRIMARY / SECONDARY 分布是否正常
- 是否存在异常成员状态
- 是否存在明显复制延迟
- 是否发生最近选举

#### 7. `key_findings`

含义：

- 当前阶段已经看到的关键异常点或关键发现

建议内容：

- 使用短列表表达，不展开长分析

#### 8. `current_scope`

含义：

- 当前故障影响范围的初步判断

建议内容：

- 单 Pod
- 单副本集
- 单 shard
- 多 shard
- 整个分片集群
- 业务侧连接范围

#### 9. `collected_at`

含义：

- 当前 `summary` 对应的采集时间

#### 当前倾向

- `summary` 不放长日志、不放大段 YAML、不放过多原始输出
- `summary` 只保留对后续判断最关键的摘要信息
- 每个字段尽量保持短、结构清晰、易被人和 Agent 快速读取

### MongoDB `summary` 字段的必填与留空规则

当前建议将 `summary` 的字段区分为“字段必须存在”和“字段值允许暂时未知”两层要求。

#### 字段必须存在

以下字段当前建议都应在 `summary` 中存在：

- `cluster_id`
- `namespace`
- `deployment_architecture`
- `topology_summary`
- `key_object_status`
- `key_replica_status`
- `key_findings`
- `current_scope`
- `collected_at`

#### 值应尽量填写的核心字段

以下字段当前建议优先保证有明确值：

- `cluster_id`
- `namespace`
- `deployment_architecture`
- `collected_at`

原因：

- 这几个字段是识别对象和定位时间的基础
- 缺失后会显著影响后续第 3 段和第 4 段使用

#### 值允许暂时未知的字段

以下字段在信息不足时允许先填写为 `unknown`、`partial` 或简短占位说明：

- `topology_summary`
- `key_object_status`
- `key_replica_status`
- `key_findings`
- `current_scope`

#### 当前结论

- `summary` 的结构应完整存在
- 但不要求所有字段在第一时间都填满细节
- 对于暂时未知的信息，应显式标记，而不是直接缺字段

### MongoDB `details.cluster_info` 草案

当前建议 `details.cluster_info` 先保留以下字段：

#### 建议字段

- `cluster_id`
- `namespace`
- `middleware`
- `deployment_architecture`
- `architecture_evidence`
- `topology_type`
- `entry_ips`
- `entry_port`
- `entry_role`
- `identification_source`
- `collected_at`

#### 字段含义

`cluster_id`

- 当前确认的目标集群标识

`namespace`

- 当前目标集群所在 namespace

`middleware`

- 固定为 `mongodb`

`deployment_architecture`

- 当前识别出的部署架构
- 例如：
  - `operator + CRD`
  - `Bitnami`
  - `unknown`

`architecture_evidence`

- 判定部署架构的依据
- 例如：
  - 存在某类 CRD
  - 资源命名模式
  - label / chart 信息

`topology_type`

- 当前识别出的拓扑类型
- 例如：
  - `sharded_cluster`
  - `replica_set`
  - `standalone`
  - `unknown`

`entry_ips`

- 当前排障入口 IP 列表

`entry_port`

- 当前使用的入口端口

`entry_role`

- 当前入口角色
- 例如：
  - `jumpserver`
  - `k8s entry`
  - `node`
  - `unknown`

`identification_source`

- 集群识别来源
- 例如：
  - 客户提供
  - 环境扫描确认
  - namespace 推断

`collected_at`

- 当前 `cluster_info` 的采集时间

#### 当前倾向

- `cluster_info` 负责回答“查的是谁、从哪进、为什么认定它是这套集群”
- 不在这一块放组件明细、Pod 明细、成员状态明细

### MongoDB `details.components` 草案

当前建议 `details.components` 用于保存 MongoDB 组件级结构信息，而不是 Kubernetes 运行对象明细。

#### 建议字段

每个组件条目当前建议至少包含：

- `component_type`
- `component_id`
- `parent_component`
- `topology_role`
- `statefulset_refs`
- `service_refs`
- `member_count`
- `status_hint`
- `collected_at`

#### 字段含义

`component_type`

- 组件类型
- 例如：
  - `mongos`
  - `configsvr`
  - `shard`
  - `replica_set`

`component_id`

- 当前组件的唯一标识

`parent_component`

- 当前组件所属的上级组件
- 例如某个 `replica_set` 属于某个 shard

`topology_role`

- 当前组件在拓扑中的角色
- 例如：
  - `router`
  - `config`
  - `data_shard`
  - `replica_group`

`statefulset_refs`

- 当前组件关联的 `StatefulSet` 列表

`service_refs`

- 当前组件关联的 `Service` / `NodePort` 列表

`member_count`

- 当前组件下的成员数量
- 例如副本集成员数或 `mongos` Pod 数

`status_hint`

- 当前组件级别的状态摘要
- 例如：
  - `healthy`
  - `partial`
  - `unhealthy`
  - `unknown`

`collected_at`

- 当前组件信息的采集时间

#### 当前倾向

- `components` 负责表达 MongoDB 逻辑组件结构
- `statefulsets`、`pods`、`services` 负责表达 Kubernetes 物理对象
- 一个组件可关联多个 `StatefulSet`、多个 Pod、多个 Service，但不在本块展开所有细节

### MongoDB `details.statefulsets` 草案

当前建议 `details.statefulsets` 用于保存 `StatefulSet` 级别的编排和运行摘要信息。

#### 建议字段

每个 `StatefulSet` 条目当前建议至少包含：

- `name`
- `namespace`
- `component_ref`
- `replicas_desired`
- `replicas_ready`
- `selector`
- `service_name`
- `pod_refs`
- `yaml`
- `status_hint`
- `collected_at`

#### 字段含义

`name`

- `StatefulSet` 名称

`namespace`

- 所属 namespace

`component_ref`

- 对应的 MongoDB 组件引用

`replicas_desired`

- 期望副本数

`replicas_ready`

- 当前就绪副本数

`selector`

- `StatefulSet` 选择器

`service_name`

- 关联的 `Service` 名称

`pod_refs`

- 关联的 Pod 名称列表

`yaml`

- 原始 YAML 编排内容或标准化后的关键 YAML 内容

`status_hint`

- `StatefulSet` 级别的状态摘要
- 例如：
  - `healthy`
  - `partial`
  - `unhealthy`
  - `unknown`

`collected_at`

- 当前 `StatefulSet` 信息采集时间

#### 当前倾向

- `statefulsets` 既要保留编排信息，也要保留最基本运行摘要
- 详细运行状态仍以下沉到 `pods` 为主
- YAML 内容在此块保留，避免散落到多个地方

### MongoDB `details.pods` 草案

当前建议 `details.pods` 用于保存 Pod 级别的运行状态、重启信息和日志入口信息。

#### 建议字段

每个 Pod 条目当前建议至少包含：

- `name`
- `namespace`
- `component_ref`
- `statefulset_ref`
- `node_ref`
- `pod_ip`
- `phase`
- `ready`
- `created_at`
- `restart_count`
- `last_restart_at`
- `container_status`
- `yaml`
- `log_refs`
- `status_hint`
- `collected_at`

#### 字段含义

`name`

- Pod 名称

`namespace`

- 所属 namespace

`component_ref`

- 对应的 MongoDB 组件引用

`statefulset_ref`

- 所属 `StatefulSet`

`node_ref`

- 所在 Node 引用

`pod_ip`

- Pod IP

`phase`

- Pod Phase
- 例如：
  - `Running`
  - `Pending`
  - `Failed`
  - `Succeeded`
  - `Unknown`

`ready`

- Pod 是否 Ready

`created_at`

- Pod 创建时间

`restart_count`

- 重启次数

`last_restart_at`

- 上一次重启时间

`container_status`

- 容器状态摘要

`yaml`

- Pod YAML 内容或关键字段摘要

`log_refs`

- 关联日志引用
- 例如最近日志、重启前日志、重启后日志

`status_hint`

- Pod 级别状态摘要

`collected_at`

- 当前 Pod 信息采集时间

#### 当前倾向

- `pods` 是运行层状态的核心分块
- 如果已收敛到具体故障 Pod，这一块应成为第 2 段和第 3 段的重点入口

### MongoDB `details.services` 草案

当前建议 `details.services` 用于保存 `Service` 和 `NodePort` 级别的访问入口信息。

#### 建议字段

每个 `Service` 条目当前建议至少包含：

- `name`
- `namespace`
- `component_ref`
- `service_type`
- `cluster_ip`
- `ports`
- `node_ports`
- `selector`
- `endpoint_refs`
- `status_hint`
- `collected_at`

#### 字段含义

`name`

- `Service` 名称

`namespace`

- 所属 namespace

`component_ref`

- 对应的 MongoDB 组件引用

`service_type`

- `Service` 类型

`cluster_ip`

- `ClusterIP`

`ports`

- `Service` 暴露端口列表

`node_ports`

- 如存在，记录 `NodePort` 端口列表

`selector`

- `Service` selector

`endpoint_refs`

- 关联的 Pod 或 endpoint 引用

`status_hint`

- `Service` 级别状态摘要

`collected_at`

- 当前 `Service` 信息采集时间

#### 当前倾向

- `services` 负责表达访问入口和服务暴露关系
- 不在这里重复记录 Pod 运行状态

### MongoDB `details.nodes` 草案

当前建议 `details.nodes` 用于保存 Node 级别状态和调度承载关系。

#### 建议字段

每个 Node 条目当前建议至少包含：

- `name`
- `status`
- `internal_ip`
- `external_ip`
- `labels`
- `taints`
- `pod_refs`
- `condition_summary`
- `status_hint`
- `collected_at`

#### 字段含义

`name`

- Node 名称

`status`

- Node 总体状态

`internal_ip`

- 内部 IP

`external_ip`

- 外部 IP，如存在

`labels`

- Node labels

`taints`

- Node taints

`pod_refs`

- 当前承载的相关 Pod 列表

`condition_summary`

- Node conditions 摘要

`status_hint`

- Node 级别状态摘要

`collected_at`

- 当前 Node 信息采集时间

#### 当前倾向

- `nodes` 主要服务于调度、节点异常、资源归因方向
- 如怀疑节点问题，这一块应被优先关注

### MongoDB `details.replica_members` 草案

当前建议 `details.replica_members` 用于保存副本集成员状态和复制行为信息。

#### 建议字段

每个成员条目当前建议至少包含：

- `replica_set_id`
- `member_name`
- `pod_ref`
- `self_view`
- `role`
- `health`
- `state_str`
- `term`
- `election_time`
- `sync_lag`
- `optime_date`
- `source_pod`
- `collection_status`
- `collected_at`

#### 字段含义

`replica_set_id`

- 所属副本集标识

`member_name`

- 成员名或成员地址标识

`pod_ref`

- 对应 Pod 引用

`self_view`

- 是否来自该成员自身 `rs.status()` 视角

`role`

- 成员角色

`health`

- 成员健康值

`state_str`

- 成员状态字符串

`term`

- 当前任期

`election_time`

- 最近选举相关时间

`sync_lag`

- 同步时延

`optime_date`

- 当前 optime 时间

`source_pod`

- 本条成员状态是从哪个 Pod 采集到的

`collection_status`

- 采集状态
- 例如：
  - `success`
  - `partial`
  - `failed`

`collected_at`

- 当前成员状态采集时间

#### 当前倾向

- `replica_members` 是 MongoDB 内部状态最关键的结构化分块之一
- 允许部分成员留白，但必须显式标记采集状态

### MongoDB `details.raw_logs` 草案

当前建议 `details.raw_logs` 用于保存原始日志内容和日志来源信息。

#### 建议字段

每条日志记录当前建议至少包含：

- `log_id`
- `pod_ref`
- `component_ref`
- `log_type`
- `time_range`
- `source`
- `content`
- `collection_status`
- `collected_at`

#### 字段含义

`log_id`

- 日志记录标识

`pod_ref`

- 对应 Pod 引用

`component_ref`

- 对应组件引用

`log_type`

- 日志类型
- 例如：
  - `recent`
  - `before_restart`
  - `after_restart`

`time_range`

- 本段日志覆盖的时间范围

`source`

- 日志来源
- 例如容器标准输出或其他来源

`content`

- 原始日志内容

`collection_status`

- 采集状态

`collected_at`

- 日志采集时间

#### 当前倾向

- `raw_logs` 保留原始证据
- 不在这里做过滤、摘要和归因

### MongoDB `details.processed_logs` 草案

当前建议 `details.processed_logs` 用于保存过滤降噪后的日志结果。

#### 建议字段

每条处理后日志记录当前建议至少包含：

- `processed_log_id`
- `raw_log_ref`
- `pod_ref`
- `keywords`
- `normalized_summary`
- `log_snippets`
- `severity_hint`
- `noise_reduction_method`
- `processed_at`

#### 字段含义

`processed_log_id`

- 处理后日志记录标识

`raw_log_ref`

- 对应的原始日志引用

`pod_ref`

- 对应 Pod 引用

`keywords`

- 提取出的关键词

`normalized_summary`

- 一句话日志摘要

`log_snippets`

- 保留下来的关键日志片段

`severity_hint`

- 当前日志严重度提示

`noise_reduction_method`

- 使用的过滤或降噪方法

`processed_at`

- 处理时间

#### 当前倾向

- `processed_logs` 服务于第 3 段信号治理和第 4 段推理诊断
- 原始日志与处理后日志必须可追溯关联

## 4. 推理诊断与深入验证

### 已确认结论

- 这一阶段采用假设驱动方式推进。
- 历史经验检索不应只是临时参考，而应作为正式输入。
- 真实排障中，“经验检索、假设生成、验证”通常是来回穿插的，不必机械线性推进。

### 当前理解

这一阶段通常包括：

- 检索历史故障记录和专家经验
- 形成多个候选假设
- 执行验证
- 排除错误假设
- 收敛最可信路径

### 待继续讨论

- 假设的标准表达形式是什么
- 验证动作和验证结果如何结构化
- 历史经验如何与当前故障建立引用关系

### 假设的结构化表达草案

当前建议第 4 段中的每条“假设”至少包含以下内容：

#### 建议字段

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

#### 字段含义

`hypothesis_id`

- 假设标识

`title`

- 对假设的简短描述

`overview`

- 对假设的简短说明或一句话解释

`scope`

- 当前假设影响的范围
- 例如：
  - 单 Pod
  - 单副本集
  - 单 shard
  - 整个分片集群

`suspected_root`

- 当前怀疑的问题方向
- 例如：
  - 节点异常
  - 存储异常
  - 复制异常
  - 选举异常
  - 调度异常
  - 网络异常

`causal_path`

- 如果该假设成立，问题是如何一步一步发展出来的因果路径
- 例如：
  - 节点异常
  - Pod 重启
  - `mongod` 恢复失败
  - 成员进入 `RECOVERING`
  - 业务连接超时

`supporting_evidence`

- 当前支持该假设的证据列表

`contradicting_evidence`

- 当前与该假设相矛盾的证据列表

`falsification_conditions`

- 什么情况会推翻该假设
- 也就是该假设的反证条件

`evidence_gaps`

- 当前为了进一步支持或否定该假设，还缺哪些关键证据

`sources`

- 当前假设引用的证据来源
- 例如：
  - 某条日志
  - 某个 Pod 状态
  - 某个 `rs.status()` 结果
  - 某条历史经验记录

`validation_actions`

- 为验证该假设准备执行或已经执行的动作列表

`validation_status`

- 当前验证状态
- 例如：
  - `pending`
  - `supported`
  - `contradicted`
  - `inconclusive`

`confidence`

- 当前对该假设的置信度
- 例如：
  - `high`
  - `medium`
  - `low`

`next_step`

- 如果继续推进该假设，下一步该做什么

#### 当前倾向

- 假设不应只是脑中的猜想，而应具备证据、反证和验证动作
- 每条假设都应可被支持、被否定或暂时悬置
- 假设结构尽量短而清楚，便于人和 Agent 共同推进

### MongoDB 假设样例

以下示例基于前面 `mongo-prod-sharded-01` 的排障样例。

```yaml
hypothesis_id: "hyp-001"
title: "worker-03 节点异常导致 shard-02 成员重启并进入 RECOVERING"
overview: "当前怀疑 worker-03 节点异常引发 mongo-shard2-data-1 重启，进而导致 shard-02 副本集成员恢复缓慢和复制延迟。"
scope: "single shard replica set"
suspected_root: "node anomaly"
causal_path:
  - "worker-03 became NotReady"
  - "mongo-shard2-data-1 restarted multiple times"
  - "mongod recovery was interrupted or slowed"
  - "member entered RECOVERING state"
  - "replication lag increased within shard-02"
supporting_evidence:
  - "node worker-03 status is NotReady"
  - "pod mongo-shard2-data-1 restarted 4 times in the last 30 minutes"
  - "mongo-shard2-data-1 state_str is RECOVERING"
  - "shard-02 replica set observed recent election and sync lag"
contradicting_evidence:
  - "other pods on worker-03 are not yet confirmed abnormal"
falsification_conditions:
  - "worker-03 remained Ready during the entire failure window"
  - "mongo-shard2-data-1 restart reason is confirmed to be configuration or storage-only issue unrelated to node state"
  - "same symptoms are observed on pods not scheduled to worker-03"
evidence_gaps:
  - "missing full node event timeline for worker-03"
  - "missing kubelet or container runtime level evidence for the restart cause"
sources:
  - "kubectl get node worker-03"
  - "kubectl describe pod mongo-shard2-data-1"
  - "rs.status() from mongo-shard2-data-0"
  - "mongo-shard2-data-1 restart logs"
validation_actions:
  - "collect worker-03 events and recent node condition changes"
  - "check whether other pods on worker-03 showed restart or readiness anomalies"
  - "confirm pod restart reason from describe output and kubelet-related evidence"
validation_status: "inconclusive"
confidence: "medium"
next_step: "补齐 worker-03 节点事件和同节点其他 Pod 状态，再判断节点异常是否为主因。"
```

### `validation_actions` 结构化草案

当前建议每条验证动作至少包含以下字段：

#### 建议字段

- `action_id`
- `purpose`
- `target_objects`
- `method`
- `expected_signal`
- `result`
- `status`
- `performed_at`

#### 字段含义

`action_id`

- 验证动作标识

`purpose`

- 这条动作是为了验证什么

`target_objects`

- 本次动作涉及的目标对象
- 例如：
  - Pod
  - Node
  - replica set member
  - `StatefulSet`

`method`

- 验证方法
- 例如：
  - 执行命令
  - 对比状态
  - 查看日志
  - 查看事件
  - 关联时间线

`expected_signal`

- 如果假设成立，预期应该看到什么信号

`result`

- 当前动作得到的实际结果摘要

`status`

- 当前动作状态
- 例如：
  - `pending`
  - `done`
  - `failed`

`performed_at`

- 动作执行时间

#### 当前倾向

- 验证动作应尽量短小、原子化
- 每条动作只验证一个明确点
- 不建议把多个验证意图塞进同一条动作

### MongoDB `validation_actions` 样例

以下示例仍基于前面的 `hyp-001`。

```yaml
validation_actions:
  - action_id: "act-001"
    purpose: "验证 worker-03 是否在故障窗口内出现节点异常"
    target_objects:
      - "node/worker-03"
    method: "查看 node 状态和事件时间线"
    expected_signal: "如果假设成立，应看到 worker-03 在 pod 异常前后出现 NotReady 或相关异常事件"
    result: "worker-03 在 15:20 左右进入 NotReady，与 pod 最近一次重启时间接近"
    status: "done"
    performed_at: "2026-06-07T15:30:00+08:00"

  - action_id: "act-002"
    purpose: "验证 mongo-shard2-data-1 的重启是否与节点问题相关"
    target_objects:
      - "pod/mongo-shard2-data-1"
      - "node/worker-03"
    method: "对比 pod describe 信息、重启时间和 node 状态变化"
    expected_signal: "如果假设成立，pod 重启时间应与 node 异常时间有明显相关性"
    result: "pod 最后一次重启时间与 node NotReady 时间接近，但仍缺少 kubelet 级直接证据"
    status: "done"
    performed_at: "2026-06-07T15:33:00+08:00"

  - action_id: "act-003"
    purpose: "验证同节点其他 Pod 是否也出现异常，以增强节点方向假设"
    target_objects:
      - "node/worker-03"
    method: "查看同节点其他相关 Pod 的状态和重启情况"
    expected_signal: "如果节点异常是主因，同节点其他 Pod 可能也会出现 readiness 或 restart 异常"
    result: "尚未完成同节点其他 Pod 的全量检查"
    status: "pending"
    performed_at: null
```

#### 补充结论

- 第 4 段默认应同时维护多条假设，而不是只保留单条假设
- 多条假设可以并行存在，并随着验证过程被支持、被否定或被悬置
- 当前阶段的目标不是尽快只剩一个假设，而是有序收敛出最可信路径

### 参考资料中的多假设做法

基于当前参考资料，外部常见做法不是只维护单一假设，而是普遍允许多条假设并行存在，再逐步收敛。

#### Azure SRE Agent

- 明确采用 hypothesis-driven investigation
- 会先形成多个 theories，再逐条验证
- 官方示例中存在：
  - `Hypothesis 1` 被 invalidated
  - `Hypothesis 2` 被 validated

可借鉴点：

- 多假设并行
- 每条假设都应有验证结果
- 最终结论来自逐条排除和支持，而不是一开始押注单一路径

#### Amazon CloudWatch Investigations

- 支持 multi-resource hypotheses
- 提供 hypothesis visualization，用节点和关系展示跨资源假设

可借鉴点：

- 假设可以天然带对象关系
- 分布式问题适合做可视化或结构化关系表达

#### Amazon OpenSearch Investigation Agent

- 会生成 structured hypotheses
- 假设按 likelihood 排序
- 每条假设带 supporting evidence
- 同时展示 primary hypothesis 和 alternative hypotheses

可借鉴点：

- 多假设应允许排序
- 每条假设应带证据
- 应区分主假设与备选假设

#### Google Cloud Assist Investigations

- 调查结果包含 one or more hypotheses
- 每条假设包含 overview 和 recommended fixes / next troubleshooting steps

可借鉴点：

- 假设不仅要说明“是什么”
- 还要说明“接下来怎么继续证伪或证实”

#### 当前结论

- 多条假设并行是常见做法
- 对假设做排序或优先级管理也是常见做法
- 假设应尽量带：
  - 支持证据
  - 反证或未满足点
  - 下一步验证动作
  - 当前状态或置信度

#### 当前选择

- 第 4 段当前先支持多假设并行
- 暂时不引入假设优先级或排序机制
- 先保证假设结构清晰、验证路径清晰，再考虑后续是否引入主假设和备选假设区分

### `validation_status` 与 `confidence` 枚举初稿

当前建议先采用轻量枚举，避免第 4 段一开始就设计得过重。

#### `validation_status`

当前建议取值为：

- `pending`
  - 假设已提出，但还未开始验证
- `supported`
  - 当前证据支持该假设
- `contradicted`
  - 当前证据与该假设明显矛盾
- `inconclusive`
  - 已做验证，但当前证据仍不足以明确支持或否定

#### `confidence`

当前建议取值为：

- `high`
- `medium`
- `low`

#### 当前倾向

- `validation_status` 用于表达“验证推进到哪一步”
- `confidence` 用于表达“当前对该假设的信任程度”
- 两者不要混用

### 对“因果路径 / 反证条件 / 深入分析 / 代码路径 / 复现脚本”做法的理解

当前讨论到的一种较强方法是：

- 每条假设带因果路径
- 每条假设带反证条件
- 对每条假设做深入分析
- 明确认领假设、执行验证、输出三态结果
- 当假设验证基本完成后，再做基线扫描
- 再进一步进入代码逻辑分析、代码路径追踪
- 最后尝试生成复现脚本

#### 当前判断

这套方法整体是强的，尤其适合：

- 平台侧复杂问题
- 怀疑中间件控制面或 Operator 逻辑异常
- 怀疑平台自动化脚本、编排逻辑、接入逻辑存在缺陷
- 需要把问题推进到工程修复层面，而不仅是现场定位层面

但当前也需要注意边界：

- 对 PaaS 中间件生产排障来说，不是所有问题都需要进入代码逻辑分析和复现脚本阶段
- 很多问题会在对象状态、拓扑、日志、成员状态、变更和环境层面就已足够定位
- 代码路径追踪和复现脚本更适合作为第 4 段的后半段分支能力，而不是默认必经步骤

#### 与参考资料的对照

外部参考中，以下做法与这套思路高度一致：

- Azure SRE Agent：
  - 强调 hypothesis-driven investigation
  - 强调 evidence chain
  - 强调逐条 invalidated / validated
- Amazon OpenSearch Investigation Agent：
  - 生成 structured hypotheses
  - 每条假设有 data evidence
  - 同时保留 primary hypothesis 和 alternative hypotheses
  - 支持 Accept / Rule out
- Google Cloud Assist：
  - 支持 multiple hypotheses
  - 每条假设附带 next troubleshooting steps / recommended fixes

而以下部分在公开参考里相对没有被统一强调为“默认步骤”：

- 统一做基线扫描
- 统一追踪代码路径
- 统一生成复现脚本

当前理解：

- 这些更像“高级深入分析分支”
- 在怀疑平台逻辑、控制器逻辑、代码缺陷时应进入
- 不应对所有中间件生产故障默认强制执行

#### 当前建议

第 4 段可以拆成两层：

1. 通用层
   - 多假设
   - 因果路径
   - 反证条件
   - 验证动作
   - 三态结果
2. 深入层
   - 基线扫描
   - 代码逻辑分析
   - 代码路径追踪
   - 复现脚本生成

其中“深入层”建议按条件触发，而不是默认对每次故障都执行

#### 当前选择

- 第 4 段当前先只保留“通用推理层”
- “深入层”暂不纳入当前实现范围
- 如果后续某些证据、日志或现象需要进入中间件源码分析、平台代码分析或知识库补充，可再设计独立能力
- 这类能力未来可考虑通过代码相关 MCP、代码检索接口或专用分析工具接入

### 第 3 / 第 4 段的脚本与 Agent 职责边界

当前建议采用以下分工：

#### 第 3 段更偏脚本

适合脚本承担的工作包括：

- 批量采集对象状态
- 拉取 YAML 编排信息
- 拉取 Pod / Node / Service / PVC 信息
- 执行中间件基础命令
  - 例如 `rs.status()`
  - `kubectl describe`
  - `pulsar-admin`
- 收集原始日志
- 整理时间戳
- 执行初步过滤降噪
- 输出结构化记录

#### 第 4 段更偏 Agent

适合 Agent 承担的工作包括：

- 基于证据链生成多条假设
- 归纳 `causal_path`
- 归纳 `falsification_conditions`
- 提取 `evidence_gaps`
- 生成验证动作
- 汇总验证结果
- 输出阶段性结论

#### 一句话分工

- 脚本负责：采集、整理、标准化、结构化输出
- Agent 负责：理解、归纳、推理、生成下一步动作

#### 当前结论

- 第 3 段应优先设计为脚本友好
- 第 4 段应优先设计为 Agent 友好
- 两段都不是纯单边，但职责主轴应保持清晰

### 第 3 段到第 4 段的接口定义

当前建议第 3 段脚本结束后，至少输出以下三类内容，作为第 4 段 Agent 的输入：

1. `structured_record`
2. `signal_bundle`
3. `collection_report`

#### 1. `structured_record`

定位：

- 保存对象、拓扑、状态、日志等结构化明细

最小内容：

- `summary`
- `details`

#### 2. `signal_bundle`

定位：

- 保存信号治理后的结果，便于第 4 段直接进入推理

最小内容：

- 异常信号列表
- 信号与对象的关联结果
- 信号时间线摘要
- 过滤降噪后的关键日志摘要

#### 3. `collection_report`

定位：

- 保存采集过程本身的结果和缺口

最小内容：

- 执行过的采集动作列表
- 成功项
- 失败项
- 留白项
- 缺失证据说明

#### 当前结论

- 第 4 段 Agent 不应直接面对杂乱原始输出
- 第 3 段应先把现场结果整理成“可推理的结构化证据包”

### 三类接口输出的最小字段集

#### 1. `structured_record`

当前建议最小字段集：

- `summary`
- `details`
- `generated_at`

当前理解：

- `summary` 和 `details` 已在领域样例中展开
- `generated_at` 用于标识本次结构化记录生成时间

#### 2. `signal_bundle`

当前建议最小字段集：

- `signal_overview`
- `abnormal_signals`
- `object_signal_links`
- `timeline_summary`
- `processed_log_highlights`
- `generated_at`

字段含义：

`signal_overview`

- 当前信号治理的摘要说明

`abnormal_signals`

- 当前识别出的异常信号列表

`object_signal_links`

- 信号与对象的关联结果

`timeline_summary`

- 当前重建出的时间线摘要

`processed_log_highlights`

- 过滤降噪后的关键日志摘要

`generated_at`

- 当前 `signal_bundle` 生成时间

#### 3. `collection_report`

当前建议最小字段集：

- `collection_actions`
- `successful_items`
- `failed_items`
- `blank_items`
- `evidence_gaps`
- `generated_at`

字段含义：

`collection_actions`

- 本次执行过的采集动作列表

`successful_items`

- 已成功采集的项目

`failed_items`

- 采集失败的项目

`blank_items`

- 允许留白但尚未补齐的项目

`evidence_gaps`

- 当前已知的证据缺口

`generated_at`

- 当前 `collection_report` 生成时间

### 指标采集策略

当前建议指标采集采用“双来源策略”，但职责不同。

#### 优先顺序

1. 先从 `Prometheus` 或现有监控系统拉取历史监控数据
2. 再按需直连服务端补充实时确认

#### `Prometheus` / 监控系统的主要用途

- 查看历史趋势
- 重建故障时间线
- 对比故障前后变化
- 对比多实例、多节点、多组件行为
- 判断异常是瞬时还是持续

#### 直连服务端的主要用途

- 查看当前即时状态
- 补采监控系统未覆盖的内部指标
- 验证 exporter 或监控数据是否可信
- 获取更细粒度的服务内部信息

#### 当前结论

- 历史分析优先 `Prometheus`
- 实时确认和缺口补充按需直连服务端
- 两类指标都应带：
  - 时间戳
  - 来源标记

建议来源标记例如：

- `metrics_source: prometheus`
- `metrics_source: direct_service`

### 日志采集策略

当前建议日志采集采用分层顺序，而不是一开始就依赖日志系统。

#### 优先顺序

1. 先查现场容器级日志
   - 例如 `kubectl logs`
   - 如存在重启，优先补 `--previous`
2. 再查日志系统
   - 例如 Loki / Elasticsearch
3. 仅在怀疑节点级问题时，再补节点系统日志

#### 现场容器级日志的主要用途

- 快速确认当前 Pod 的直接异常
- 获取重启前后日志
- 补齐日志系统可能存在的延迟或缺口

#### 日志系统的主要用途

- 做历史时间窗口检索
- 做跨 Pod / 跨节点聚合
- 做关键词搜索和趋势对比
- 辅助时间线重建

#### 节点系统日志的主要用途

- 节点异常
- kubelet 异常
- container runtime 异常
- Pod 重启与节点状态变化时间接近

#### 当前结论

- 日志默认先查现场容器级日志
- 后查日志系统
- 节点系统日志仅作为节点级问题的补充信号

建议来源标记例如：

- `log_source: kubectl_logs`
- `log_source: loki`
- `log_source: elasticsearch`
- `log_source: node_system_log`

## 5. 结论整合与知识沉淀

### 已确认结论

- 这一阶段不应只停在“给出初步结论”，还应包含知识沉淀。
- 结论应形成可交接、可复盘、可升级的阶段性结果。
- 有效经验应回灌为后续可复用知识。

### 当前理解

输出内容通常包括：

- 当前现象
- 影响范围
- 关键证据
- 已验证结果
- 当前最可信结论
- 下一步建议
- 风险提示

知识沉淀通常包括：

- 新增或修订 runbook
- 补充历史案例
- 更新技能、命令或脚本
- 补充新的场景标签和经验索引

### 待继续讨论

- 这一阶段的输出模板应该长什么样
- 什么时候算“可以沉淀为知识”
- 如何避免低质量经验污染知识库

### 第 5 段结构化输出草案

当前建议第 5 段至少输出两部分内容：

1. `conclusion_summary`
2. `knowledge_candidates`

#### 1. `conclusion_summary`

用于表达本次排障的阶段性结论。

当前建议字段：

- `incident_scope`
- `current_findings`
- `validated_hypotheses`
- `rejected_hypotheses`
- `inconclusive_hypotheses`
- `most_likely_conclusion`
- `remaining_risks`
- `next_actions`
- `generated_at`

#### 字段含义

`incident_scope`

- 本次故障当前确认的影响范围

`current_findings`

- 已确认的关键事实和关键发现

`validated_hypotheses`

- 当前已被支持的假设列表

`rejected_hypotheses`

- 当前已被否定的假设列表

`inconclusive_hypotheses`

- 当前仍未明确支持或否定的假设列表

`most_likely_conclusion`

- 当前最可信的阶段性结论

`remaining_risks`

- 当前仍存在的风险或不确定性

`next_actions`

- 下一步建议动作

`generated_at`

- 当前结论生成时间

#### 2. `knowledge_candidates`

用于表达本次排障中，哪些内容值得沉淀到知识资产中。

当前建议字段：

- `candidate_type`
- `title`
- `source_scope`
- `why_reusable`
- `target_asset`
- `status`

#### 字段含义

`candidate_type`

- 候选知识类型
- 例如：
  - `runbook_update`
  - `new_runbook`
  - `case_record`
  - `skill_update`
  - `command_update`
  - `script_update`

`title`

- 候选知识条目的简短标题

`source_scope`

- 本次排障中对应的来源范围

`why_reusable`

- 为什么认为这条内容值得沉淀和复用

`target_asset`

- 计划沉淀到哪个知识资产中

`status`

- 当前处理状态
- 例如：
  - `identified`
  - `drafted`
  - `accepted`
  - `rejected`

#### 当前倾向

- 第 5 段不只是写一个结论段落
- 应同时考虑“这次排障有什么值得回灌进知识库”
- 结论输出和知识沉淀候选应分开表达，避免混杂

### MongoDB 第 5 段输出样例

以下示例仍基于前面 `mongo-prod-sharded-01` 的排障样例。

```yaml
conclusion_summary:
  incident_scope: "single shard replica set with possible node-level impact"
  current_findings:
    - "worker-03 entered NotReady during the failure window"
    - "mongo-shard2-data-1 restarted multiple times"
    - "shard-02 member entered RECOVERING state"
    - "replication lag increased in shard-02 after recent election"
  validated_hypotheses:
    - "hyp-001"
  rejected_hypotheses:
    - "hyp-002"
  inconclusive_hypotheses:
    - "hyp-003"
  most_likely_conclusion: "worker-03 node anomaly is the most likely trigger for shard-02 member restart and recovery lag"
  remaining_risks:
    - "direct kubelet-level evidence for restart cause is still missing"
    - "other pods on worker-03 have not been fully checked yet"
  next_actions:
    - "complete worker-03 related pod scan"
    - "review node event history and kubelet-side evidence"
    - "assess whether shard-02 requires recovery acceleration or temporary traffic mitigation"
  generated_at: "2026-06-07T16:10:00+08:00"

knowledge_candidates:
  - candidate_type: "new_runbook"
    title: "MongoDB shard member RECOVERING after node NotReady"
    source_scope: "mongodb sharded cluster / node anomaly / recovering member"
    why_reusable: "combines node anomaly, pod restart, recovering member, and replication lag into a repeatable troubleshooting path"
    target_asset: "domains/mongodb/runbooks/replica-set/member-recovering-after-node-anomaly"
    status: "identified"

  - candidate_type: "case_record"
    title: "worker-03 NotReady triggered shard-02 recovery lag"
    source_scope: "mongodb shard-02 / worker node anomaly"
    why_reusable: "useful as a historical reference for similar node-driven MongoDB failures"
    target_asset: "historical incident knowledge base"
    status: "identified"

  - candidate_type: "command_update"
    title: "Add node event and rs.status cross-check bundle"
    source_scope: "mongodb node anomaly investigation"
    why_reusable: "can reduce time to correlate node events, pod restarts, and member status changes"
    target_asset: "domains/mongodb/commands"
    status: "drafted"
```
