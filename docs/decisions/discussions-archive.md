---
status: archived
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

> ⚠️ 已归档的历史讨论稿。结论以 `docs/specs/` 为准，本文内容可能已过时。

# Discussions

本文件用于记录项目讨论过程中的结论、分歧点和后续待继续的话题，便于后续翻阅。

## 2026-06-06

### 主题：项目目标

已讨论结论：

- 本项目用于自动排查 PaaS 中间件故障，覆盖 MongoDB、Elasticsearch、Redis，以及后续的 Kafka、Pulsar 等中间件。
- 项目需要沉淀生产环境 `runbook`，收录中间件专家的排查命令、工具、脚本、技能和经验。
- 项目的实现基线是 Claude Code 插件官方标准。
- 项目需要尽量兼容 `Cursor`、`Codex` 等其他 Agent 或厂商运行环境。

相关文档：

- [README.md](../../README.md)

### 主题：仓库结构总体方向

已讨论结论：

- 仓库按三层组织：共性层、领域层、场景层。
- 共性层负责通用规范、模板、共享诊断能力和接口约定。
- 领域层按具体中间件拆分，存放专属知识和资产。
- 场景层按跨中间件通用故障场景拆分，用于统一命名、分类和路由。

### 主题：需要收敛的结构点

本轮明确了以下边界：

- `scenarios/` 和 `domains/*/scenarios/` 二选一，最终保留 `scenarios/`，取消 `domains/*/scenarios/`。
- `scenarios/` 只定义场景，不存产品专属 runbook、命令或脚本。
- `domains/<product>/` 只存具体中间件资产。
- `plugins/` 不在主仓库存放具体厂商实现，主仓库只保留接口定义。
- `core/shared/` 严格限制为跨中间件复用的基础诊断能力。
- 中间件大类和具体产品的分级设计暂不展开，只在 metadata 中预留空间。
- runbook 只存一份，物理上按组件组织，逻辑上按场景检索。

相关文档：

- [docs/architecture.md](../concepts/architecture.md)

### 主题：MongoDB 样例落地

已讨论结论：

- 以 MongoDB 作为首个样例验证仓库结构。
- 选择 `replica-inconsistency` 作为跨中间件场景样例。
- 选择 `replica-set` 作为 MongoDB 组件入口样例。
- 样例资产包含：
  - 1 个场景定义
  - 1 个 MongoDB 领域元数据
  - 1 个 command 资产
  - 1 个 skill 资产
  - 1 个 runbook 资产

相关文档：

- [scenarios/replica-inconsistency/scenario.yaml](../../scenarios/replica-inconsistency/scenario.yaml)
- [domains/mongodb/metadata.yaml](../../domains/mongodb/metadata.yaml)
- [domains/mongodb/commands/replica-set/check-rs-status/command.md](../../domains/mongodb/commands/replica-set/check-rs-status/command.md)
- [domains/mongodb/skills/replica-set/triage-replica-member-not-healthy/skill.md](../../domains/mongodb/skills/replica-set/triage-replica-member-not-healthy/skill.md)
- [domains/mongodb/runbooks/replica-set/replica-member-not-healthy/runbook.md](../../domains/mongodb/runbooks/replica-set/replica-member-not-healthy/runbook.md)

### 主题：已记账、暂不继续推进的事项

当前已决定先记录、后续再讨论或实现的事项包括：

- 补齐仓库目录骨架
- 继续完善 `docs/architecture.md`
- 讨论 Claude Code 官方标准下如何兼容 Cursor 和 Codex
- 补齐 schema、模板、接口定义和工具链
- 继续扩展 MongoDB 资产或平移到其他中间件验证结构

相关文档：

- [docs/TODO.md](../project/todo.md)

### 主题：排障步骤框架（初稿）

本轮提出了一版统一排障步骤框架，作为后续 runbook 和 skill 设计的基线候选。

当前提案：

1. 接警与问题定义
   - 明确现象、开始时间、影响范围、影响对象和业务症状。
2. 风险与边界确认
   - 判断当前是只读诊断阶段还是处置阶段，确认是否允许高风险动作。
3. 场景归类
   - 先将问题归入标准场景，例如连接失败、延迟升高、副本异常、资源耗尽、消费积压。
4. 中间件与组件定位
   - 明确具体中间件以及问题落在哪个组件，例如 MongoDB 的 replica-set、Kafka 的 consumer。
5. 基础健康检查
   - 先看存活性、角色分布、连接状态、核心指标和错误日志。
6. 共性层排查
   - 检查 Kubernetes、Linux、网络、存储、观测信号等跨中间件问题。
7. 领域层深挖
   - 使用对应中间件专属命令、脚本和技能进一步确认根因。
8. 根因分类
   - 将问题归类为拓扑、网络、资源、配置、数据积压、依赖异常等一级原因。
9. 输出结论与建议
   - 输出受影响对象、证据、初步结论、下一步建议和风险提示。
10. 进入处置或升级
   - 如果需要执行变更动作，必须显式确认；如果无法闭环，则升级给专家或人工介入。

当前倾向：

- 先做“诊断流程标准化”，再做“处置流程标准化”
- 先要求所有 runbook 和 skill 都能映射到上述步骤
- 保持前半段尽量跨中间件统一，后半段允许进入产品专属路径

待继续讨论：

- 这 10 步是否过长，是否需要压缩为更少的主阶段
- “场景归类”应该早于“中间件定位”还是并行进行
- “共性层排查”和“领域层深挖”是否需要更明确的切换条件

### 主题：排障步骤框架（基于真实生产经验的修正方向）

本轮补充了更贴近真实生产排障的一版主线，重点不再是技术分类本身，而是围绕“信息收集、范围收敛、环境确认、经验检索、假设推理、验证闭环、结论输出”推进。

用户口述的关键思路包括：

1. 先收集基础信息
   - 用户报障背景
   - 报错日志
   - 故障时间
   - 集群信息
   - Kubernetes 环境接入信息，例如主机 IP、账号密码等远程信息
2. 明确预设部署架构
   - 例如 MongoDB 一般是分片集群，并运行在 Kubernetes 环境中
   - 可能只有一套集群，也可能有多套集群
   - 如果有多套，需要先确认具体报障的是哪一套
3. 继续补充更多有助于缩小排障范围的信息
   - 原则是越详细越有助于缩小范围
4. 进入环境做故障信息关联
   - 将故障与中间件实例、组件、节点、服务、模块等建立关联
   - 将这些信息填充到预定义的排障表格中
5. 查询历史经验
   - 到历史故障记录、记录系统等搜索类似问题
6. 进行推理诊断
   - 整理假设和猜想
7. 执行验证
   - 验证这些假设和猜想，开展深入分析
8. 产出初步结论报告
   - 根据验证过程、执行结果和证据整理初步结论

当前收敛方向：

- 排障流程应围绕“证据收集与范围收敛”设计，而不是只围绕技术分层设计
- 应把“部署架构识别”和“目标集群确认”前置
- 应显式引入“历史经验检索”这一步，而不是隐含在推理过程中
- 应该有一份结构化排障表格，作为整个诊断过程的中间载体
- 最终输出不只是口头判断，而是结构化的初步结论报告

待继续讨论：

- “基础信息采集表”和“初步结论报告”应该长什么样
- 接入信息中哪些字段应该进入标准化表单，哪些字段不应直接落库
- 历史经验检索与实时诊断之间如何建立引用关系

### 主题：真实起始输入的进一步澄清

本轮进一步明确了排障开始时，实际最常收到的输入信息比理想状态更少。

用户补充的真实起始输入通常包括：

- 客户已经说明是哪个中间件出了故障
- 环境 IP
- 登录账号和密码
- 有时会附带一段业务侧报障日志

这意味着：

- 排障流程不能假设一开始就有完整的架构、拓扑和影响范围信息
- “报障受理与基础信息采集”阶段应先围绕最小输入启动
- 环境信息、架构信息、目标集群确认、组件关联等内容，很多时候需要排障人员进入环境后再补齐
- 业务日志应被视为高价值初始证据，需要在最早阶段结构化记录

当前收敛方向：

- 报障起点应设计为“最小可启动输入模型”，而不是“理想完整输入模型”
- 最小输入至少包括：
  - middleware
  - access endpoint
  - credentials
  - business error log
- 后续流程再逐步补齐拓扑、范围、对象关联和历史经验

进一步明确：

- 中间件报障类型是必须项
- Kubernetes 环境 IP 是必须项
- 登录账号密码是必须项
- 客户提供的故障线索属于高价值输入，但不应被狭义命名为“业务报障日志”

进一步修正：

- 客户给出的输入可能是日志，也可能是一段现象描述，例如“某个 Pod 起不来”
- 因此初始受理单中不应将该字段命名为“日志”
- 更合适的抽象是“客户提供的故障线索”或“原始报障信息”
- 该字段的内容类别需要由排障系统或排障人员进一步分析识别

### 主题：初始受理单字段如何确定

本轮进一步明确了字段设计不应靠感觉堆积，而应按“是否阻塞排障启动”和“是否属于第一手原始证据”来判断。

当前建议的判定标准：

- 必填项：缺失后会直接阻塞排障启动，无法进入环境或无法判断排查对象
- 高价值可选项：缺失后不阻塞启动，但会明显降低排障效率
- 后置补全项：通常需要进入环境后才能确认，不应强塞进初始受理单

按该标准，当前收敛为：

- 必填项：
  - 中间件类型
  - K8s 环境 IP
  - 账号
  - 密码
- 高价值可选项：
  - 客户提供的故障线索
- 后置补全项：
  - 集群名
  - namespace
  - 部署架构
  - 组件列表
  - 实例映射
  - 影响范围

### 主题：初始受理单最小字段草案

本轮给出了一版可直接落表的最小字段草案，目标是保证“能启动排障”，而不是一开始就收集完整信息。

当前草案：

- `middleware`
  - 必填
  - 表示本次报障对应的中间件类型
- `k8s_access_ips`
  - 必填
  - 表示进入排障环境的 Kubernetes 入口 IP、运维入口 IP 或跳板入口 IP 列表
- `username`
  - 必填
  - 表示登录账号
- `password`
  - 必填
  - 表示登录密码或认证信息
- `port`
  - 可选
  - 表示登录端口，默认通常为 22，但某些环境会使用其他端口
- `customer_clue`
  - 可选
  - 表示客户提供的原始故障线索，可能是日志、现象描述、告警内容或组件异常信息

这版草案的设计原则：

- 初始受理单只负责启动排障
- 不把进入环境后才能确认的字段提前塞进来
- 原始线索先保留原文，不要求客户先做结构化整理

进一步明确：

- `k8s_access_ips` 允许多个
- 如果客户提供多个 IP，默认以第一个 IP 作为排障入口和跳板机
- 其他 IP 可以在进入环境后继续推导和确认其角色
- 密码当前阶段直接存储，不额外引入凭据抽象
- 端口不是必填项，默认可按 22 处理；只有客户提供了非默认端口时才填写

### 主题：`customer_clue` 字段的处理建议

本轮讨论了初始受理单中的 `customer_clue` 应如何落地，目标是在不过度设计的前提下，保留原始证据并支持后续分析。

当前建议：

- `customer_clue` 保留原文，不在初始受理阶段改写
- `customer_clue` 可以是任意文本，可能是：
  - 错误日志
  - 现象描述
  - 组件状态信息
  - 告警内容
  - 其他客户原话
- 初始阶段不强制客户做结构化输入

建议在后续分析阶段，由排障系统或排障人员补充派生字段：

- `clue_type`
  - 表示线索类型，例如：
    - `log`
    - `symptom`
    - `pod_status`
    - `alert`
    - `connectivity`
    - `unknown`
- `suspected_objects`
  - 表示线索中初步指向的对象，例如：
    - pod
    - service
    - replica-set
    - shard
    - node
- `keywords`
  - 从原始线索中提取的关键字
- `normalized_summary`
  - 对原始线索做一句话归纳，用于后续检索和历史经验匹配

当前倾向：

- 初始受理单只存 `customer_clue` 原文
- 分类、摘要、对象提取放到后续分析阶段
- 原文与派生信息要同时保留，避免二次加工覆盖第一手证据

进一步讨论：

- 需要避免为 `customer_clue` 设计过多固定派生字段
- 故障类型和场景很多样，过早枚举太多字段会让模型僵化

当前收敛方向：

- 采用“少量核心字段 + 可扩展富化”的方式
- 核心字段保持稳定、跨中间件通用
- 其余分析结果作为可选补充，不强制每次都填满

进一步决定：

- `customer_clue` 的富化字段先按 10 项定义
- 这 10 项作为统一分析框架存在，但不要求每次都全部填满
- 其中应区分核心项和可选项，避免字段多导致受理和分析流程过重

当前建议的 10 项为：

1. `raw_text`
   - 原始线索原文
2. `clue_type`
   - 线索粗分类，例如日志、现象、告警、状态、未知
3. `source`
   - 线索来源，例如客户口述、工单、聊天记录、截图转录
4. `reported_time`
   - 客户描述中涉及的故障时间或报障时间
5. `normalized_summary`
   - 一句话标准化摘要
6. `keywords`
   - 提取出的关键词
7. `suspected_scope`
   - 初步怀疑影响范围，例如单 Pod、单实例、单集群、业务侧
8. `suspected_objects`
   - 初步指向的对象，例如 pod、service、replica-set、node
9. `severity_hint`
   - 从线索中推断出的严重度提示，例如高、中、低、未知
10. `confidence`
   - 当前对线索理解和归纳的置信度

进一步收敛：

- 10 项统一存在，但分为“核心项”和“可选项”

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

当前设计原则：

- 核心项优先保证可用，支撑最基本的检索、分类和推理
- 可选项用于在信息充足时继续富化，不要求每次补齐

### 主题：`clue_type` 枚举初稿

本轮开始收敛 `customer_clue` 的 `clue_type` 取值范围，原则是先小后大，避免一开始分类过细。

当前建议的枚举为：

- `log`
  - 明确是一段错误日志、异常栈、组件日志
- `symptom`
  - 现象描述，例如“连接超时”“读写失败”“服务不可用”
- `status`
  - 状态类信息，例如“某个 Pod 起不来”“实例不健康”“副本异常”
- `alert`
  - 告警类信息，例如监控告警、平台告警、阈值告警
- `change`
  - 变更类线索，例如升级、扩容、配置变更、迁移、重启
- `unknown`
  - 无法明确归类或信息过少

当前收敛方向：

- 不单独拆 `pod_status`、`connectivity` 这类更细类型，先并入更粗粒度类型
- 先保证不同中间件、不同来源的线索都能落进这 6 类之一
- 后续如果历史案例证明某类线索长期混淆，再考虑扩枚举

### 主题：`severity_hint` 枚举初稿

本轮进一步收敛 `severity_hint` 的取值范围，目标是作为初始严重度提示，而不是最终定级结论。

当前建议的枚举为：

- `high`
  - 明确影响业务可用性，或核心组件不可用
- `medium`
  - 有明显异常，但看起来不是全面不可用
- `low`
  - 局部异常、边缘问题，或当前影响较小
- `unknown`
  - 当前线索不足以判断严重度

当前收敛方向：

- `severity_hint` 只作为初始提示
- 允许在进入环境后根据更多证据修正
- 不在当前阶段引入更复杂的严重度分级体系

### 主题：`keywords` 与 `normalized_summary` 的处理建议

本轮进一步收敛了 `customer_clue` 富化中的 `keywords` 和 `normalized_summary`。

`keywords` 的当前原则：

- 每条线索提取少量关键词，建议控制在 3-8 个
- 优先提取高信号词，包括：
  - 错误词
  - 状态词
  - 组件词
  - 动作词
  - 资源词
- 尽量做轻量标准化
- 避免保留低价值泛词
- 中间件专有词允许保留，不强制泛化

`normalized_summary` 的当前原则：

- 只写一句标准化描述
- 尽量简短
- 尽量保留“对象 + 异常 + 影响”三个核心元素
- 去掉客户原话中的情绪、口语和重复信息
- 不直接下根因结论，除非证据已经非常明确
- 目标是形成可检索、可快速阅读的标准问题描述

当前状态：

- `customer_clue` 的处理方式暂时定稿
- 下一步讨论可切换到 `环境补全表`

### 主题：讨论优先级调整

本轮对讨论顺序做了纠偏。

已达成共识：

- 不应过早深入表单和字段细节
- 应先把排障主流程定下来
- `初始受理单`、`环境补全表`、`诊断工作表`、`初步结论报告` 都应从主流程中派生

当前收敛方向：

- 下一步优先讨论“排障主流程”
- 流程定稿后，再回头收敛各阶段所需表单和字段

### 主题：排障主流程压缩为 5 段的候选方案

本轮开始讨论是否将 7 个阶段进一步压缩为 5 个主阶段，以便后续作为统一流程骨架。

当前候选的 5 段方案：

1. 受理与启动
   - 接收最小输入
   - 保存客户原始故障线索
   - 获得环境访问入口
2. 环境确认与对象盘点
   - 确认目标环境、目标集群、目标实例组
   - 识别部署架构
   - 盘点组件、节点、Pod、服务和相关对象
3. 事实采集与范围收敛
   - 收集状态、日志、监控和错误信息
   - 将故障与具体对象建立关联
   - 收敛影响范围
4. 经验检索、假设生成与验证
   - 检索历史经验
   - 形成假设
   - 执行验证并持续收敛
5. 初步结论与下一步建议
   - 输出现象、证据、结论、影响范围和后续建议

当前倾向：

- 将“环境进入”“目标确认”“架构识别”“对象盘点”合并为一段
- 将“历史经验检索”和“假设验证”合并为一段
- 保留“初步结论输出”为独立结束阶段

### 主题：外部流程调研结论

本轮基于公开资料对业界常见的排障/故障诊断流程做了调研，重点参考了 Google SRE、Microsoft、IBM、Datadog、PagerDuty 的公开文档。

主要观察：

- Google SRE 的方法强调：
  - 一开始要有结构化的问题报告
  - 先做 triage，再 examine，再 diagnose
  - 诊断过程是典型的 hypothesis-driven investigation
  - 需要保留证据，并避免把相关性误判为因果
- IBM 的方法强调：
  - 第一件事是完整描述问题
  - 要回答 symptom / where / when / conditions / reproducible
  - 要建立时间线，并检查最近变更
- Microsoft 的方法强调：
  - 需要聚合和关联来自日志、指标、追踪、部署、基础设施的证据
  - 需要 reconstruct chronology
  - 需要足够的 instrumentation 和 correlation ID
- Azure SRE Agent 的方法强调：
  - 不应停留在“搜日志”
  - 应采用 evidence gathering → hypothesis generation → validation → conclusion 的链路
  - 应回忆历史相似事件及其修复方式
- Datadog 的方法强调：
  - 有效调查始于 incident identification / categorization
  - 然后是 comprehensive data collection 和 timeline construction
  - 要能在 signals、services、dependencies 之间快速 pivot
- PagerDuty 的方法强调：
  - 可以利用历史事件模式推断 probable origin
  - 历史模式有助于缩小影响半径并减少无效排查

当前结论：

- 我们当前的 5 段主流程总体方向是合理且可落地的
- 业界共识最强的部分是：
  - 先收集和结构化问题信息
  - 再收集和治理多源信号
  - 再做假设驱动诊断和验证
  - 最后形成带证据链的结论
- 我们相对于通用流程需要保留的特色是：
  - 明确前置“环境确认与对象盘点”
  - 因为 PaaS 中间件场景里，多集群、多组件、多实例、多入口是高频现实问题
- 当前一个可参考的映射方式是：
  - 受理与启动 ≈ collect information
  - 环境确认与对象盘点 + 事实采集与范围收敛 ≈ signal governance
  - 经验检索、假设生成与验证 ≈ reasoning diagnosis + deep analysis
  - 初步结论与下一步建议 ≈ conclusion integration

## 记录约定

后续讨论统一记录到本文件，建议按以下方式追加：

- 记录日期
- 记录主题
- 区分“已讨论结论”和“待继续讨论”
- 尽量附上对应文档链接

## 2026-06-07

### 主题：插件对外使用流程（初稿）

当前提出的插件对外使用流程为：

1. 用户从插件库下载插件
2. 用户执行 `/xx:start`
   - 开启一轮排障
   - 插件引导用户输入所需信息
   - 进入第 1 段和第 2 段
   - 判断 `ready / blocked`
   - 如果 `blocked`，继续引导用户纠正信息
3. 用户执行 `/xx:analyse`
   - 开始第 3、4、5 段
   - 前面阶段的已有内容不再允许修改
   - 直接生成阶段性结论和知识沉淀候选
4. 用户执行 `/xx:review`
   - 对插件排障表现做评价和打分

当前收敛方向：

- 对外入口应尽量少
- 内部仍保持 5 段主流程
- `/xx:analyse` 直接覆盖第 3、4、5 段并产出结论
- `/xx:review` 不负责结论输出，而是用于插件反馈与打分

补充想法：

- `/xx:review` 可增加对当前分析结果和阶段性结论的评分
- 评分结果可用于后续插件效果优化和能力迭代

当前建议草案：

- `/xx:review` 输出：
  - 质量评分
  - 评分原因
  - 改进建议

### 主题：编码前候选方案 - 状态机与单次排障记录目录结构

当前提出了一版编码前候选方案，优先用于收敛插件实现基线。

#### 候选状态机

当前建议状态包括：

- `created`
  - 已创建排障记录，但尚未完成启动校验
- `blocked`
  - 启动受阻，缺少条件或验证失败
- `ready`
  - 已满足启动条件，可进入分析
- `analysing`
  - 正在执行第 3、4、5 段
- `analysed`
  - 已完成一轮分析，已产出结论和报告
- `reviewed`
  - 已完成一次针对插件效果的 review / 打分
- `closed`
  - 本次排障记录已结束，不再继续推进

当前建议迁移关系：

- `/plugin:start`
  - 进入 `created`
  - 校验失败进入 `blocked`
  - 校验成功进入 `ready`
- `/plugin:analyse`
  - 从 `ready` 进入 `analysing`
  - 完成后进入 `analysed`
- `/plugin:review`
  - 从 `analysed` 进入 `reviewed`
  - 不改变分析结论，只补充反馈结果

当前决定：

- `reviewed` 和 `closed` 两个状态都保留
- `review` 结果不单独使用 `review.yaml`
- `review` 结果并入 `analysis.yaml`

#### 候选目录结构

当前建议采用“一次排障一个目录”的方式。

目录草案：

```text
incidents/
  <incident_id>/
    meta.yaml
    input.yaml
    structured_record.yaml
    signal_bundle.yaml
    collection_report.yaml
    analysis.yaml
    logs/
      raw/
      processed/
```

各文件当前建议定位：

- `meta.yaml`
  - 记录状态、时间、插件版本、中间件类型、incident_id
- `input.yaml`
  - 保存启动输入和原始故障线索
- `structured_record.yaml`
  - 第 3 段结构化记录
- `signal_bundle.yaml`
  - 第 3 段信号治理结果
- `collection_report.yaml`
  - 第 3 段采集报告和缺口
- `analysis.yaml`
  - 第 4 段假设、验证动作、阶段性推理结果
  - 第 5 段结论
  - review / feedback 评分结果
- `logs/raw/`
  - 原始日志
- `logs/processed/`
  - 处理后日志

当前倾向：

- 先用目录和 YAML 跑通
- 不急于引入数据库
- review 结果并入 `analysis.yaml`，减少文件分散

#### `meta.yaml` 草案

当前建议 `meta.yaml` 只承担记录级元信息，不承载分析内容。

建议字段：

- `incident_id`
- `middleware`
- `status`
- `created_at`
- `updated_at`
- `plugin_version`
- `current_command`
- `namespace`
- `cluster_id`
- `owner`

当前结论：

- `meta.yaml` 只做总入口和导航
- 假设、结论、评分、原始线索、结构化明细不放进 `meta.yaml`

#### `input.yaml` 草案

当前建议 `input.yaml` 用于保存一次排障的启动输入和原始线索，不承载后置分析结果。

建议字段：

- `middleware`
- `k8s_access_ips`
- `username`
- `password`
- `port`
- `customer_clue`
- `clue_enrichment`
- `input_source`
- `received_at`

字段说明：

- `middleware`
  - 本次排障对应的中间件类型
- `k8s_access_ips`
  - 进入排障环境的 IP 列表
- `username`
  - 登录账号
- `password`
  - 登录密码或认证信息
- `port`
  - 登录端口，默认可按 22 处理
- `customer_clue`
  - 客户提供的原始故障线索原文
- `clue_enrichment`
  - 对 `customer_clue` 的轻量富化结果
  - 当前建议至少包括：
    - `raw_text`
    - `clue_type`
    - `normalized_summary`
    - `keywords`
- `input_source`
  - 输入来源
  - 例如：
    - `interactive`
    - `command_args`
    - `ticket`
    - `api`
- `received_at`
  - 本次输入接收时间

当前倾向：

- `input.yaml` 负责保留启动时的第一手输入
- 前面阶段的基础输入默认冻结，不在后续阶段随意修改
- 如果后续需要纠正输入，应记录为修订动作，而不是默默覆盖原值

### 主题：`incident_id` 规则

当前已确认 `incident_id` 采用如下格式：

`<middleware>-<YYYYMMDD>-<HHMMSS>-<rand4>`

示例：

- `mongodb-20260607-213045-a7k2`
- `pulsar-20260607-213112-m4q9`

当前结论：

- 规则需要同时满足唯一性和可读性
- 不将 `cluster_id` 放入 `incident_id`
- `incident_id` 应在 `/start` 阶段即可生成，不依赖后续环境确认

### 主题：插件命令输入方式

当前已确认：

- `/plugin:start`
  - 采用“参数可选 + 交互补全”的方式
  - 支持用户直接传参数启动
  - 如果参数不全，则进入交互引导补齐

- `/plugin:analyse`
  - 默认作用于当前 incident
  - 不强制要求显式传 `incident_id`
  - 仅在存在多个未结束 incident 或用户想分析历史记录时，才需要补充选择

- `/plugin:review`
  - 默认作用于最近一次已完成分析的 incident
  - 仅在存在多个候选记录或用户想 review 历史记录时，才需要补充选择

当前结论：

- `start` 偏输入采集，兼容命令式和交互式使用
- `analyse` 偏执行，默认分析当前记录
- `review` 偏反馈，默认 review 最近分析结果

### 主题：`/plugin:start` 参数草案

当前已确认 `/plugin:start` 先支持以下参数：

- `middleware`
- `ips`
- `username`
- `password`
- `port`
- `clue`

当前规则：

- `middleware`
  - 必填
- `ips`
  - 必填
  - 支持一个或多个值
- `username`
  - 必填
- `password`
  - 必填
- `port`
  - 可选
  - 不传默认按 `22`
- `clue`
  - 可选
  - 支持直接传客户原始故障线索

当前结论：

- `/plugin:start` 采用“能直接传就直接传，传不全就交互补齐”的方式

### 主题：MVP 范围

当前已确认的 MVP 范围如下：

#### 1. 中间件范围

- 第一版只正式支持 `MongoDB`

#### 2. `/plugin:review`

- 第一版只保留命令入口占位
- 暂不实现完整评分和反馈能力

#### 3. `/plugin:analyse`

第一版可覆盖以下能力：

- Kubernetes 对象采集
- 日志采集
- 基础状态判断
- 多假设生成
- 阶段性结论输出

#### 4. 未实现能力的处理原则

- 第一版必须显式记录哪些能力尚未实现
- 不允许让用户误以为插件已经支持所有已讨论能力
- 对于未实现项，应在输出、文档或命令反馈中明确标识

### 主题：`/plugin:analyse` 与 `/plugin:review` 参数草案

当前建议 `/plugin:analyse` 和 `/plugin:review` 保持少参数设计。

#### `/plugin:analyse`

当前建议支持的参数：

- `incident_id`
  - 可选
  - 默认分析当前 incident

当前倾向：

- 没有显式 `incident_id` 时，默认分析当前记录
- 如存在多个未结束 incident，默认使用当前会话记忆里最近一次使用的记录
- 对于刚执行 `/plugin:start` 创建的记录，默认将其视为当前目标记录
- 第一版不建议加入过多高级参数
- `scope` 放到后续版本，第一版不实现
- `force_recollect` 放到后续版本，第一版不实现

#### `/plugin:review`

当前建议支持的参数：

- `incident_id`
  - 可选
  - 默认 review 最近一次已 `analysed` 的 incident
- `mode`
  - 可选
  - 第一版可先预留，不必实现
  - 例如：
    - `quick`
    - `full`

当前倾向：

- `/plugin:review` 第一版只保留入口占位
- 参数先尽量少，避免后续实现前反复改命令形态
- 没有显式 `incident_id` 时，默认 review 当前会话记忆里最近一次已分析的目标记录

### 主题：当前目标记录的会话记忆规则

既然 `/plugin:analyse` 和 `/plugin:review` 默认依赖“当前会话记忆里的最近目标记录”，当前建议补充以下规则：

#### 候选规则

- 执行 `/plugin:start` 成功创建记录后：
  - 自动将该 `incident_id` 设为当前目标记录
- 执行 `/plugin:analyse` 时：
  - 如果用户显式传入 `incident_id`，则切换当前目标记录为该 `incident_id`
  - 如果未显式传入，则使用当前目标记录
- 执行 `/plugin:review` 时：
  - 如果用户显式传入 `incident_id`，则切换当前目标记录为该 `incident_id`
  - 如果未显式传入，则使用当前目标记录中的最近已 `analysed` 记录

#### 当前倾向

- 当前目标记录应是“会话级概念”，而不是全局唯一概念
- 不建议第一版实现复杂的多记录切换命令
- 第一版只要保证“最近 start 创建的记录”和“最近 analyse 完成的记录”可被默认命中即可

当前结论：

- 当前目标记录按会话级维护
- `/plugin:start` 成功创建后自动设为当前目标记录
- `/plugin:analyse` 和 `/plugin:review` 在显式传入 `incident_id` 时可切换当前目标记录
- 第一版不实现复杂的多记录切换命令

### 主题：命令状态校验与提示规则

当前建议三个命令遵循以下状态校验与提示规则。

#### `/plugin:start`

- 不依赖当前目标记录
- 始终允许新建
- 成功创建后覆盖当前目标记录为新建 incident

#### `/plugin:analyse`

如果没有当前目标记录：

- 提示：
  - `当前没有可分析的 incident，请先执行 /plugin:start`

如果当前目标记录状态为：

- `blocked`
  - 提示：
    - `当前 incident 仍处于 blocked，请先补齐或修正启动信息`
- `created`
  - 提示：
    - `当前 incident 尚未完成启动校验，请先完成 start 阶段`
- `analysing`
  - 提示：
    - `当前 incident 正在分析中，请等待完成或查看当前进度`
- `analysed`
  - 允许继续 analyse
  - 提示：
    - `当前 incident 已分析过，将基于已有记录继续分析`
- `closed`
  - 提示：
    - `当前 incident 已关闭，请新建或显式指定其他 incident`

#### `/plugin:review`

如果没有当前目标记录：

- 提示：
  - `当前没有可 review 的 incident，请先完成一次 analyse`

如果当前目标记录状态为：

- `ready`
- `blocked`
- `created`
  - 提示：
    - `当前 incident 尚未完成 analyse，无法执行 review`
- `analysing`
  - 提示：
    - `当前 incident 仍在分析中，请待 analyse 完成后再执行 review`
- `analysed`
  - 允许 review
- `reviewed`
  - 允许再次 review
  - 提示：
    - `当前 incident 已有 review 记录，将追加或刷新 review 结果`
- `closed`
  - 默认允许 review 已关闭但已有 analyse 结果的历史 incident

#### 当前结论

- `start` 最宽松
- `analyse` 要求前置状态正确
- `review` 要求至少已经 `analysed`

#### `analysis.yaml` 草案

当前建议 `analysis.yaml` 用于承载第 4 段、第 5 段以及 `review` 反馈结果。

建议骨架：

```yaml
hypotheses:
validation_actions:
conclusion_summary:
knowledge_candidates:
review:
generated_at:
updated_at:
```

字段说明：

- `hypotheses`
  - 多条假设列表
  - 每条假设包含：
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

- `validation_actions`
  - 验证动作列表
  - 每条动作至少包括：
    - `action_id`
    - `purpose`
    - `target_objects`
    - `method`
    - `expected_signal`
    - `result`
    - `status`
    - `performed_at`

- `conclusion_summary`
  - 第 5 段阶段性结论

- `knowledge_candidates`
  - 第 5 段知识沉淀候选

- `review`
  - 对插件排障表现的反馈结果
  - 当前建议至少包括：
    - `scores`
    - `score_reasons`
    - `improvement_suggestions`
    - `reviewed_at`

- `generated_at`
  - 当前 `analysis.yaml` 首次生成时间

- `updated_at`
  - 当前 `analysis.yaml` 最近更新时间

当前倾向：

- `analysis.yaml` 是 incident 目录里最核心的“推理与结论文件”
- `review` 并入 `analysis.yaml`，但作为独立顶层分块存在
- 假设、验证、结论、review 四类内容应并存但不要混写

#### `signal_bundle.yaml` 草案

当前建议 `signal_bundle.yaml` 用于承载第 3 段信号治理后的结果，而不是原始采集明细。

建议骨架：

```yaml
signal_overview:
abnormal_signals:
object_signal_links:
timeline_summary:
processed_log_highlights:
generated_at:
updated_at:
```

字段说明：

- `signal_overview`
  - 当前信号治理阶段的摘要说明
  - 用于快速回答：
    - 当前有哪些主要异常方向
    - 当前信号是否已经足够进入第 4 段

- `abnormal_signals`
  - 当前识别出的异常信号列表
  - 每条信号当前建议至少包括：
    - `signal_id`
    - `signal_type`
    - `source`
    - `summary`
    - `severity_hint`
    - `timestamp`

- `object_signal_links`
  - 信号与对象的关联结果
  - 当前建议至少包括：
    - `signal_id`
    - `object_type`
    - `object_ref`
    - `relation`

- `timeline_summary`
  - 当前重建出的关键时间线摘要
  - 当前建议至少包括：
    - `timestamp`
    - `event`
    - `related_objects`
    - `source`

- `processed_log_highlights`
  - 过滤降噪后的关键日志摘要
  - 当前建议至少包括：
    - `log_ref`
    - `pod_ref`
    - `keywords`
    - `normalized_summary`
    - `severity_hint`

- `generated_at`
  - 当前 `signal_bundle.yaml` 首次生成时间

- `updated_at`
  - 当前 `signal_bundle.yaml` 最近更新时间

当前倾向：

- `signal_bundle.yaml` 负责表达“治理后的信号”
- 不重复存放大段原始日志和大段对象明细
- 它是第 4 段 Agent 最直接的输入之一

#### `collection_report.yaml` 草案

当前建议 `collection_report.yaml` 用于承载第 3 段采集过程本身的结果、失败和缺口。

建议骨架：

```yaml
collection_actions:
successful_items:
failed_items:
blank_items:
evidence_gaps:
generated_at:
updated_at:
```

字段说明：

- `collection_actions`
  - 本次执行过的采集动作列表
  - 每条动作当前建议至少包括：
    - `action_id`
    - `name`
    - `target`
    - `method`
    - `status`
    - `performed_at`

- `successful_items`
  - 已成功采集的项目列表

- `failed_items`
  - 采集失败的项目列表
  - 每条当前建议至少包括：
    - `item`
    - `reason`
    - `impact`

- `blank_items`
  - 允许留白但尚未补齐的项目
  - 每条当前建议至少包括：
    - `item`
    - `why_blank`
    - `possible_backfill_source`

- `evidence_gaps`
  - 当前已知证据缺口
  - 当前建议至少包括：
    - `gap`
    - `related_stage`
    - `why_important`

- `generated_at`
  - 当前 `collection_report.yaml` 首次生成时间

- `updated_at`
  - 当前 `collection_report.yaml` 最近更新时间

当前倾向：

- `collection_report.yaml` 负责回答“采到了什么、没采到什么、为什么没采到”
- 它不是分析文件，而是采集质量和证据缺口文件
- 第 4 段 Agent 应显式读取它，避免把“没看到”误判成“没有异常”

建议先使用维度评分，而不是单一总分。

建议评分维度包括：

- `evidence_completeness`
  - 证据完整度
- `hypothesis_coverage`
  - 假设覆盖度
- `validation_depth`
  - 验证深度
- `conclusion_confidence`
  - 结论可信度
- `knowledge_reusability`
  - 知识复用价值

当前倾向：

- 每个维度先采用 `high / medium / low`
- 每个维度都附一条简短原因说明

## 2026-06-07

### 主题：MongoDB 第一版脚本目录与命名规范

已讨论结论：

- 第一版只规范 `domains/mongodb/scripts/` 下的第 3 段脚本。
- 当前不在 `scripts/` 中放第 4 段推理脚本，避免把脚本采集职责和 Agent 推理职责混写。
- MongoDB 第一版脚本目录当前收敛为：
  - `collect/`
  - `normalize/`
  - `helpers/`

职责边界：

- `collect/`
  - 负责单一采集动作
  - 直接面向 Kubernetes、MongoDB 服务端、日志入口或监控入口取数
- `normalize/`
  - 负责时间对齐、对象关联、日志降噪、异常摘要和信号归并
- `helpers/`
  - 负责共享函数、命令封装、解析辅助和公共校验
  - 不直接作为主采集入口暴露

命名规则：

- 当前建议采用 `<phase>-<target>-<action>`
- `phase` 第一版只使用：
  - `collect`
  - `normalize`
- 文件名不重复 `mongodb` 前缀，因为目录本身已经限定在 `domains/mongodb/scripts/`
- 一个脚本只做一类动作，不在一个脚本里混采集、治理和推理

示例：

- `collect-pods-state.sh`
- `collect-statefulsets-yaml.sh`
- `collect-replicaset-rs-status.sh`
- `collect-logs-current.sh`
- `collect-logs-previous.sh`
- `normalize-logs-highlights.py`
- `normalize-signals-bundle.py`

相关文档：

- [docs/TRIAGE_WORKFLOW_SPEC.md](../specs/triage-workflow.spec.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [domains/mongodb/scripts/README.md](../../domains/mongodb/scripts/README.md)

### 主题：脚本资产源文件与插件运行时脚本的边界

已讨论结论：

- 主仓库中的 `domains/<product>/scripts/` 应视为脚本资产源文件目录。
- 插件安装后不应直接依赖主仓库源码路径执行这些脚本。
- 插件真正执行的脚本应位于各自插件包内部，并由构建或发布流程从主仓库脚本资产复制或打包生成。

当前收敛原则：

- 主仓库继续作为脚本资产的单一事实来源
- 插件运行时只访问自己包内的脚本
- 各厂商插件可以有自己的包内目录布局
- 但脚本 ID、能力语义和来源资产应保持可追踪

当前建议的最小 `script_id` 规则：

- 采用 `<middleware>.<phase>.<target>.<action>`
- 示例：
  - `mongodb.collect.pods.state`
  - `mongodb.collect.replicaset.rs_status`
  - `mongodb.collect.logs.current`
  - `mongodb.normalize.logs.highlights`

当前不建议第一版采用：

- 运行时动态查找用户本地主仓库路径
- 要求用户额外配置仓库源码目录
- 插件安装后临时下载脚本资产

后续待继续收敛：

- 是否定义统一的脚本 manifest 文件
- 插件包内脚本目录是否需要最小约定
- 主仓库到插件包的打包清单如何表达

相关文档：

- [README.md](../../README.md)
- [docs/architecture.md](../concepts/architecture.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)

### 主题：脚本资产清单采用单中间件 manifest

已讨论结论：

- 当前采用“单中间件一个 `manifest.yaml`”的方案。
- `manifest.yaml` 位于 `domains/<product>/scripts/` 下。
- 一个 manifest 登记多个脚本入口，不为每个脚本单独建 metadata 文件。

当前目录示例：

- `domains/mongodb/scripts/manifest.yaml`
- `domains/mongodb/scripts/collect/`
- `domains/mongodb/scripts/normalize/`
- `domains/mongodb/scripts/helpers/`

当前建议最小字段包括：

- `script_id`
- `source`
- `phase`
- `target`
- `action`
- `runtime`
- `readonly`
- `default_packaged`
- `mvp`

当前原则：

- `script_id` 是稳定标识
- `source` 只表示主仓库中的资产路径
- `helpers/` 中的共享脚本默认不进入 manifest
- manifest 当前只解决打包和运行时映射问题，不提前引入复杂依赖或参数 schema

相关文档：

- [README.md](../../README.md)
- [docs/architecture.md](../concepts/architecture.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [domains/mongodb/scripts/README.md](../../domains/mongodb/scripts/README.md)

### 主题：插件侧脚本运行时映射文件

已讨论结论：

- 插件包内应维护一份独立运行时映射文件。
- 当前建议文件名为 `script-runtime-map.yaml`。
- 该文件负责将 `script_id` 映射到插件包内部的真实脚本路径。

当前建议最小字段：

- `plugin`
- `version`
- `generated_at`
- `scripts`

其中每条脚本映射当前建议至少包括：

- `script_id`
- `runtime_path`
- `runtime`
- `readonly`

当前原则：

- 插件运行时优先查映射文件，不直接依赖主仓库源码路径
- `runtime_path` 只表示插件包内部相对路径
- 插件不应在运行时通过扫描目录来猜测 `script_id`

相关文档：

- [README.md](../../README.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [interfaces/plugin/README.md](../../interfaces/plugin/README.md)
- [interfaces/plugin/script-runtime-map.example.yaml](../../interfaces/plugin/script-runtime-map.example.yaml)

### 主题：MongoDB 第一批实现脚本清单

已讨论结论：

- 当前 `/plugin:analyse` 的 MongoDB MVP 第一批脚本收敛为 10 个。
- 目标是先保证对象盘点、拓扑确认、成员状态、日志采集和基础信号治理闭环。

当前清单：

1. `mongodb.collect.pods.state`
2. `mongodb.collect.statefulsets.yaml`
3. `mongodb.collect.services.yaml`
4. `mongodb.collect.nodes.state`
5. `mongodb.collect.mongos.get_shard_map`
6. `mongodb.collect.replicaset.rs_status`
7. `mongodb.collect.logs.current`
8. `mongodb.collect.logs.previous`
9. `mongodb.normalize.logs.highlights`
10. `mongodb.normalize.signals.bundle`

当前执行顺序：

1. 先采 Pod 状态
2. 再采 StatefulSet 编排
3. 再采 Service / NodePort 映射
4. 再采 Node 状态
5. 先从 `mongos` 采 shard map
6. 再采 `rs.status()`
7. 再采当前日志
8. 对重启 Pod 补采前一轮日志
9. 对日志做摘要和降噪
10. 最后做信号打包

当前明确暂不纳入第一批：

- 事件采集脚本
- 指标采集脚本
- 节点系统日志脚本
- 高级诊断脚本

相关文档：

- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [domains/mongodb/scripts/README.md](../../domains/mongodb/scripts/README.md)
- [domains/mongodb/scripts/manifest.yaml](../../domains/mongodb/scripts/manifest.yaml)
- [interfaces/plugin/script-runtime-map.example.yaml](../../interfaces/plugin/script-runtime-map.example.yaml)

### 主题：第 3 段脚本最小调用合同

已讨论结论：

- 当前建议第 3 段脚本统一采用：
  - `--context-file`
  - `--output-file`
  - `--artifact-dir`
- 机器可读结果只写 `output-file`，不依赖 `stdout`

当前建议最小状态集：

- `success`
- `partial`
- `blocked`

当前原则：

- 当脚本按合同成功写出 `output-file` 时，退出码为 `0`
- 非 `0` 退出码只表示脚本自身执行失败或违反调用合同
- `partial` 和 `blocked` 通过 `output-file.status` 表达，不应直接用退出码表达

### 主题：MongoDB `mongos.get_shard_map` 的结构化落点

已讨论结论：

- `mongodb.collect.mongos.get_shard_map` 的主要落点当前定为：
  - `structured_record.details.shard_map`
- 该分块用于表达从 `mongos` 视角看到的分片路由和 shard 拓扑。

当前建议字段包括：

- `source_component_ref`
- `source_pod_ref`
- `source_method`
- `config_server_ref`
- `shards`
- `collection_status`
- `collected_at`

当前原则：

- `components` 继续表达 MongoDB 逻辑组件
- `shard_map` 补充表达 `mongos` 视角的分片映射
- `replica_members` 继续表达各副本集成员状态

相关文档：

- [README.md](../../README.md)
- [docs/TRIAGE_WORKFLOW_SPEC.md](../specs/triage-workflow.spec.md)
- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [domains/mongodb/scripts/README.md](../../domains/mongodb/scripts/README.md)
- [domains/mongodb/examples/triage-record.example.yaml](../../domains/mongodb/examples/triage-record.example.yaml)

### 主题：MongoDB 基础采集脚本的 `context-file` 约定

已讨论结论：

- 当前 MongoDB 第一批基础采集脚本在最小公共字段之外，共享以下 `context-file` 字段：
  - `deployment_architecture`
  - `topology_type`
  - `access`
  - `targets`
  - `capabilities`

当前建议：

- `access`
  - `primary_ip`
  - `candidate_ips`
  - `username`
  - `password`
  - `port`
- `targets`
  - `namespace`
  - `statefulset_refs`
  - `service_refs`
  - `pod_refs`
  - `node_refs`
  - `mongos_pod_ref`
- `capabilities`
  - `kubectl_available`
  - `kubectl_exec_available`
  - `mongosh_in_pod_available`

5 个基础采集脚本的专属字段当前建议为：

- `mongodb.collect.pods.state`
  - `pod_query.mode`
- `mongodb.collect.statefulsets.yaml`
  - `statefulset_query.include_yaml`
- `mongodb.collect.services.yaml`
  - `service_query.include_nodeport`
- `mongodb.collect.nodes.state`
  - `node_query.resolve_from_pods`
- `mongodb.collect.mongos.get_shard_map`
  - `mongos_query.shell`
  - `mongos_query.database`
  - `mongos_query.command`

当前原则：

- 先定义共享字段，再允许脚本追加少量专属字段
- 第一版先不把全部领域字段抽成统一总 schema
- 第一版先保证 MongoDB 基础采集脚本之间输入口径一致

### 主题：真实 K8s 环境的脚本测试方式

已讨论结论：

- 当前建议把“脚本逻辑”和“远程执行”分层处理。
- 第 3 段脚本本身不负责 SSH 登录、跳板机选择或凭据管理。
- 插件运行时或测试执行器负责进入远程环境，脚本只假定自己运行时已经处在远程执行环境中。
- 远程执行环境通常只要求有 `kubectl` 这类控制工具。
- `mongosh` 等中间件工具默认通过 `kubectl exec` 在目标 Pod 内调用。

当前建议原则：

- 多个入口 IP 默认以第一个 IP 作为跳板入口
- 真实账号密码不写入仓库
- 本地私有测试配置建议放在：
  - `.local/test-envs/mongodb-k8s.yaml`
- 远程测试执行器负责：
  - SSH 连通性验证
  - 基础命令能力验证
  - 在远程环境执行脚本
  - 拉回 `output-file` 和产物目录

当前建议最小测试步骤：

1. 验证 SSH 可达
2. 验证远程环境存在 `kubectl`
3. 验证基础 Kubernetes 操作可执行
4. 生成本次测试用 `context-file`
5. 在远程环境执行脚本
6. 拉回 `output-file` 和 `artifact-dir`
7. 检查结果是否符合脚本合同

当前理解：

- 这套原则既适用于人工脚本验证，也适用于后续插件运行时接入真实远程环境
- 先不把真实 IP、账号密码写入任何仓库内文档

### 主题：Remote Executor 作为正式执行层

已讨论结论：

- 排障命令当然要远程执行。
- 远程执行能力应明确建模为 `remote executor`。
- `remote executor` 属于插件运行时执行层，不属于领域脚本本身。

当前职责边界：

- `remote executor`
  - 接收环境信息
  - 默认使用第一个 IP 作为跳板入口
  - 建立远程连接
  - 验证 `kubectl`、`kubectl exec` 等能力
  - 在远程环境执行脚本
  - 拉回 `output-file` 和 `artifact-dir`
- `script`
  - 只负责采集和治理逻辑
  - 不负责 SSH 登录、跳板机选择或凭据管理

工具位置原则：

- `kubectl` 这类控制工具通常要求远程执行环境可用
- `mongosh`、`redis-cli`、`kafka-topics.sh` 这类中间件工具默认按 Pod 内工具处理
- 中间件命令优先通过 `kubectl exec` 在目标 Pod 内执行

当前理解：

- 以后真实跑 `collect-pods-state.sh`、`collect-mongos-get-shard-map.sh` 这类脚本时，都会先经过 `remote executor`
- 这样既能支持真实排障，也能支持真实 K8s 环境下的脚本验证

### 主题：MongoDB `output-file` 示例约定

已讨论结论：

- 当前建议 MongoDB 第 3 段脚本的 `output-file` 采用“结果概览 + patch + 产物引用”的结构。
- `collect/*` 脚本主要负责：
  - `structured_record_patch`
  - `collection_report_patch`
- `normalize/*` 脚本主要负责：
  - `signal_bundle_patch`

当前建议最小字段：

- `script_id`
- `status`
- `summary`
- `started_at`
- `finished_at`
- `artifacts`
- `structured_record_patch`
- `signal_bundle_patch`
- `collection_report_patch`
- `warnings`
- `evidence_gaps`

其中 `mongodb.collect.mongos.get_shard_map` 当前建议：

- `structured_record_patch` 主要写 `details.shard_map`
- `signal_bundle_patch` 第一版可以为空
- `collection_report_patch` 记录 `mongos` 采集动作、成功项和证据缺口

### 主题：Remote Executor 最小接口模型

已讨论结论：

- `remote executor` 需要独立的请求模型和结果模型，供 Claude Code、Codex、Cursor 等适配器复用。
- 请求模型描述一次脚本远程执行任务，至少包含：
  - `executor_id`
  - `incident_id`
  - `script_id`
  - `access`
  - `script`
  - `remote_workspace`
  - `required_capabilities`
  - `execution`
- 结果模型描述远程执行层的执行结果，至少包含：
  - `status`
  - `selected_ip`
  - `capability_checks`
  - `remote_paths`
  - `retrieved_files`
  - `process`
  - `error`
  - `warnings`

状态边界：

- 第 3 段脚本的 `output-file.status` 仍只使用：
  - `success`
  - `partial`
  - `blocked`
- `remote executor.status` 额外允许：
  - `failed`
- `failed` 只表达执行器自身异常、脚本合同失败或无法判断结果有效性。

错误分类：

- 第一版至少区分 SSH 不通、SSH 认证失败、缺少 `sshpass`、缺少 `kubectl`、K8s context 不可用、`kubectl exec` 不可用、目标 Pod 不存在、Pod 内工具缺失、脚本运行失败、脚本合同失败、结果回收失败。

相关文档：

- [docs/PLUGIN_RUNTIME_SPEC.md](../specs/plugin-runtime.spec.md)
- [interfaces/plugin/remote-executor-request.example.yaml](../../interfaces/plugin/remote-executor-request.example.yaml)
- [interfaces/plugin/remote-executor-result.example.yaml](../../interfaces/plugin/remote-executor-result.example.yaml)

### 主题：远程脚本投放目录

已讨论结论：

- 远程执行器不应假设脚本已经存在于跳板机。
- 更合理的方式是先把插件包内脚本投放到跳板机 `/tmp/<plugin_name>/` 下，再执行。
- 脚本投放目录建议保持插件包内相对路径，例如：
  - `/tmp/<plugin_name>/assets/scripts/mongodb/collect-pods-state.sh`
- 单次执行目录建议按 `incident_id` 和 `script_id` 隔离，例如：
  - `/tmp/<plugin_name>/runs/<incident_id>/<script_id>/`

目录职责：

- `assets/scripts/`
  - 保存本次插件需要投放到远程环境的脚本和 helper
- `runs/<incident_id>/<script_id>/`
  - 保存本次执行的 `context.yaml`
  - 保存脚本输出的 `output.yaml`
  - 保存脚本输出的 `artifacts/`

当前理解：

- 这种方式更接近真实插件安装后的运行方式。
- 远程执行失败时也更容易在跳板机上保留和复查现场。
- 主仓库源码路径、插件包内脚本路径、远程执行路径三者需要明确解耦。

### 主题：真实 K8s 环境 smoke test 发现

本轮使用真实测试环境验证了远程执行链路。

已确认：

- SSH 可达。
- 远程 `kubectl` 可用。
- K8s namespace 中存在 `psmdb-test`。
- 远程脚本投放到 `/tmp/midstack-triage/assets/scripts/...` 后可以执行。
- 单次执行目录 `/tmp/midstack-triage/runs/<incident_id>/<script_id>/` 可用。
- `mongodb.collect.pods.state` 已在真实环境跑通。
- `mongodb.collect.statefulsets.yaml` 已在真实环境跑通。
- `mongodb.collect.services.yaml` 已在真实环境跑通。
- `mongodb.collect.nodes.state` 已在真实环境跑通。
- `mongodb.collect.mongos.get_shard_map` 已在真实环境跑通。
- `mongodb.collect.replicaset.rs_status` 已在真实环境跑通。
- `mongodb.collect.logs.current` 已在真实环境跑通。
- `mongodb.collect.logs.previous` 已在真实环境跑通。
- `mongodb.normalize.logs.highlights` 已在真实环境跑通。
- `mongodb.normalize.signals.bundle` 已在真实环境跑通。

采集摘要：

- K8s 节点 3 个，均为 `Ready`。
- Node 状态采集识别到 3 个 MongoDB 相关 Pod 所在节点，均为 `healthy`。
- 目标 namespace 为 `psmdb-test`。
- MongoDB 相关 StatefulSet 3 个：
  - `bnmongo-configsvr`
  - `bnmongo-shard0-data`
  - `bnmongo-shard1-data`
- MongoDB 相关 Service 2 个：
  - `bnmongo`
  - `bnmongo-headless`
- MongoDB namespace 内 Pod 12 个。
- `mongos getShardMap` 采集到 2 个 shard：
  - `bnmongo-shard-0`
  - `bnmongo-shard-1`
- `rs.status()` 采集到 9 个成员 Pod：
  - `bnmongo-configsvr`：1 主 2 从
  - `bnmongo-shard-0`：1 主 2 从
  - `bnmongo-shard-1`：1 主 2 从
- 当前日志采集到 11 个 MongoDB 组件 Pod，原始日志作为 artifact 保存，结构化记录中只保留引用、行数和大小。
- previous 日志采集到 11 个 MongoDB 组件 Pod，原始日志作为 artifact 保存，结构化记录中只保留引用、行数和大小。
- 日志 highlights 从 22 个日志文件中提取到 63 条关键行，并已清理 ANSI 控制字符。
- signal bundle 已从 9 个上游脚本 output 中汇总出 inventory、topology、replica set 和 log signals。
- MongoDB MVP 第一批 10 个脚本已经全部通过真实 K8s 环境 smoke test。

### 主题：远程 smoke test 工具沉淀

已讨论结论：

- 临时 `.local/tools/remote-mongodb-smoke.py` 的能力已沉淀为正式工具：
  - `tools/remote-smoke/mongodb-smoke.py`
- 正式工具不保存账号密码。
- 真实环境信息继续放在 `.local/test-envs/*.yaml` 这类被忽略的本地文件中。
- 工具负责：
  - 读取本地忽略配置
  - SSH 进入跳板机
  - 投放 MongoDB MVP 脚本
  - 按顺序执行 10 个脚本
  - 回收 `output.yaml` 和 artifact
  - 输出每个脚本的状态摘要

验证结果：

- 已使用正式工具跑通 MongoDB MVP 第一批 10 个脚本。
- 最近一次结果目录：
  - `.local/remote-runs/mongodb-remote-smoke-20260607-170649`

运行时约束发现：

- 跳板机 Python 版本为 3.6 系列。
- 跳板机没有预装 `PyYAML`。
- 因此第 3 段脚本不能默认依赖 Python 3.7+ 语法或第三方 Python 包。

已收敛规则：

- 第 3 段脚本优先使用 Python 标准库。
- Python 语法兼容 Python 3.6。
- `context-file` 和 `output-file` 支持 JSON-compatible YAML，作为无 `PyYAML` 场景下的降级格式。

### 主题：MongoDB 命令认证来源

已讨论结论：

- MongoDB 运行命令一般需要账号密码认证信息。
- 认证信息来源要按部署方式区分。

Bitnami 部署：

- 认证信息通常可以从容器环境变量中获取。
- 例如 root 用户和 root 密码常见于 Pod 环境变量。
- 脚本应优先在 Pod 内使用环境变量完成认证，避免把密码拉回本地或写入 artifact。

operator+CRD 部署：

- 认证信息通常需要从 Kubernetes Secret 资源中获取。
- 第一版先预留 `secret_ref` 字段，后续再实现 Secret 解析逻辑。

当前脚本能力：

- 支持 `mongos_query.username`
- 支持 `mongos_query.password`
- 支持 `mongos_query.password_env`
- 支持 `mongos_query.password_file_env`
- 支持 `mongos_query.auth_database`
- 预留 `mongos_query.secret_ref`

安全原则：

- 密码不写入 `output-file`
- 密码不写入 artifact
- 密码不写入日志摘要
