---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Domain Record Comparison

本文件用于对不同中间件的结构化排障记录做横向对照，识别：

- 哪些字段和分块已经具备共性
- 哪些部分必须保留中间件专属结构
- 哪些地方后续可以继续抽象

当前先比较：

- MongoDB
- Pulsar

## 1. 总体结论

当前 MongoDB 和 Pulsar 的样例已经表明：

- `summary + details` 的两层结构是稳定的
- `details` 下按对象分类分块的方式是稳定的
- Kubernetes 运行层对象块已经具备较强共性
- 中间件内部成员状态和逻辑拓扑仍然需要保留领域专属结构

也就是说，当前最合理的方向不是“完全统一结构”，而是：

- 保留稳定的公共骨架
- 为中间件内部专属状态保留扩展槽位

## 2. `summary` 层对照

### 已经稳定的共性字段

以下字段当前在 MongoDB 和 Pulsar 之间都成立，建议视为跨中间件通用字段：

- `cluster_id`
- `namespace`
- `deployment_architecture`
- `topology_summary`
- `key_object_status`
- `key_findings`
- `current_scope`
- `collected_at`

### 需要轻微抽象的字段

MongoDB 当前使用：

- `key_replica_status`

Pulsar 当前使用：

- `key_component_status`

当前判断：

- 这说明“关键内部状态摘要”是共性需求
- 但命名不应绑定单一中间件语义

建议后续抽象方向：

- `key_internal_status`

当前阶段不强制修改样例，先保留现状，等更多中间件样例出现后再统一。

## 3. `details` 分块对照

### 已经稳定的公共分块

以下分块在 MongoDB 和 Pulsar 中都已经出现，且职责边界基本一致：

- `cluster_info`
- `components`
- `statefulsets`
- `pods`
- `services`
- `nodes`
- `raw_logs`
- `processed_logs`

当前判断：

- 这些分块已经可以视为结构化排障记录的公共骨架
- 后续扩 Kafka、Redis 时，优先沿用这些分块

### 需要保留领域专属的分块

MongoDB 当前专属：

- `replica_members`

Pulsar 当前专属：

- `bookie_members`

当前判断：

- 这类分块本质上都在表达“中间件内部核心成员状态”
- 但字段内容强烈依赖中间件内部机制

建议后续抽象方向：

- 上层概念可统一为：
  - `internal_members`
  - 或 `component_members`
- 具体字段继续按中间件自定义

当前阶段不建议强行统一字段，因为会损失领域表达能力。

## 4. Kubernetes 运行层对象共性

MongoDB 和 Pulsar 的样例都说明，以下对象具有明显跨中间件共性：

- `StatefulSet`
- Pod
- `Service`
- Node

这些对象上的典型共性字段包括：

- 名称
- namespace
- 组件引用
- 状态摘要
- 采集时间
- 关联对象引用
- YAML 或关键编排内容

当前判断：

- 这些对象未来可以优先抽成共享 schema
- 它们是跨中间件复用率最高的一层

## 5. 逻辑组件层共性

MongoDB 的逻辑组件包括：

- `mongos`
- `configsvr`
- `shard`
- `replica_set`

Pulsar 的逻辑组件包括：

- `broker`
- `bookie`
- `zookeeper`

尽管具体组件不同，但它们已经表现出稳定共性字段：

- `component_type`
- `component_id`
- `parent_component`
- `topology_role`
- `statefulset_refs`
- `service_refs`
- `member_count`
- `status_hint`
- `collected_at`

当前判断：

- `components` 已经具备较强的跨中间件通用性
- 这是后续最值得继续沉淀为共性模型的一层

## 6. 日志层共性

MongoDB 和 Pulsar 的样例都已经表明：

- `raw_logs` 与 `processed_logs` 分离是合理的
- “先保留原始日志，再进行过滤降噪”这条原则是稳定的

当前共性包括：

- `raw_logs`
  - 原始日志内容
  - 日志来源
  - 时间范围
  - 对象引用
- `processed_logs`
  - 关键词
  - 标准化摘要
  - 关键片段
  - 严重度提示
  - 降噪方法

当前判断：

- 日志层已经具备明确公共模式
- 后续可直接复用到更多中间件

## 7. 当前建议

基于 MongoDB 和 Pulsar 的对照，当前建议如下：

### 1. 先固化公共骨架

先把以下内容视为公共结构：

- `summary + details`
- `cluster_info`
- `components`
- `statefulsets`
- `pods`
- `services`
- `nodes`
- `raw_logs`
- `processed_logs`

### 2. 保留中间件内部状态专属分块

当前不要强行统一：

- `replica_members`
- `bookie_members`

因为这些块承载的是中间件内部机制，过早统一会导致表达能力下降。

### 3. 下一步抽象重点

后续如果继续抽象，优先考虑：

- `summary` 中的“关键内部状态摘要”字段命名
- `internal_members` 这一类上层概念
- Kubernetes 运行层对象的共享 schema

## 8. 结论

当前 MongoDB 和 Pulsar 的对照结果支持以下判断：

- 结构化排障记录的公共骨架已经初步成立
- 领域专属部分主要集中在“中间件内部成员状态”和“内部拓扑行为”
- 项目后续应坚持“共性骨架 + 专属扩展”的方向，而不是追求完全统一字段
