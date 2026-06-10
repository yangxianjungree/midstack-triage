---
status: draft
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# 实现进展

本文件统一维护"已实现 / 未实现 / 已验证"类项目状态断言（L3，允许滞后）。

规范文档（`docs/specs/`）只定义设计意图，不承载实现进展；此前散落在 `README.md`「稳定结论」与 `plugin-runtime.spec.md` §12 中的进展内容已迁移至此。

## 总体进展

- MongoDB MVP 第一批 11 个第 3 段脚本已完成合同级实现，并已通过真实 K8s 环境 smoke test
- 本地插件原型已能消费 fixture、incident 或已完成的 remote smoke 结果目录来验证 analyse/review 文件流转
- 本地插件原型已能通过 `.local` remote config 调度真实 MongoDB 只读采集并继续生成分析结果
- 本地插件 `review` 已能基于 `analysis.yaml` 生成五维评分和改进建议（原型级）
- Cursor 集成源实现已收敛到 `plugins/cursor/`，可安装到临时 Cursor 项目并自动化 smoke test

## 第一版已实现能力清单

### `/plugin:start`

- 接收启动输入
- 支持"参数可选 + 交互补全"
- 创建 `incident_id`
- 创建 incident 目录和基础文件
- 验证远程环境基础可达性
- 验证基础 Kubernetes 操作能力
- 判断并输出 `ready / blocked`
- 将新记录设为当前会话目标记录

### `/plugin:analyse`

- 基于当前目标记录继续执行
- 执行第 3 段信号采集与治理
- 输出：
  - `structured_record`
  - `signal_bundle`
  - `collection_report`
- 执行第 4 段通用推理
- 生成多条假设
- 生成验证动作
- 输出第 5 段阶段性结论
- 输出知识沉淀候选

### MongoDB

- 环境与对象盘点
- Kubernetes 对象采集
  - `StatefulSet`
  - Pod
  - `Service`
  - Node
- 分片集群 / 副本集基础 topology 识别
- `rs.status()` 基础成员状态采集
- Pod 日志采集
  - 当前日志
  - 重启前日志（如可用）
- 基础信号治理
  - 时间对齐
  - 对象关联
  - 初步过滤降噪

### MongoDB 第一批脚本

`/plugin:analyse` 的 MongoDB MVP 已完成 11 个第 3 段脚本的合同级实现（清单与执行顺序见[插件运行时规范](../specs/plugin-runtime.spec.md)，能力边界见 [Analyse MVP 规范](../specs/analyse-mvp.spec.md)）。

真实环境验证状态：

- 以上 11 个脚本已通过真实 K8s 环境 smoke test
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
- 五维评分与改进建议已有原型实现

## 第一版未实现能力清单

### `/plugin:analyse`

- `scope` 参数
- `force_recollect` 参数
- 复杂多记录切换命令
- 深入层能力：
  - 基线扫描
  - 代码逻辑分析
  - 代码路径追踪
  - 复现脚本生成

### `/plugin:review`

- 评分权重正式化
- 评分结果持久化归档细则

### MongoDB

- 更复杂的高级场景自动化分析
- 节点系统日志的完整实现
- 指标采集的完整实现
- 日志系统接入的完整实现

### 其他中间件

- Pulsar 正式支持
- Redis 正式支持
- Elasticsearch 正式支持
- Kafka 正式支持
