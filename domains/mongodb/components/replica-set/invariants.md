# MongoDB Replica Set Invariants

本文记录 MongoDB replica set 排障中可复用的领域不变量和经验判断，用于辅助 Phase 4 假设生成、`deepening_findings` 和只读验证请求。

这些知识只能作为假设来源或验证路径来源。当前故障结论仍必须由本次 incident 的 `structured_record.yaml`、`signal_bundle.yaml`、`collection_report.yaml`、日志或脚本产物支撑。

## Multi-View Invariants

健康副本集在多个成员视角下通常应满足这些约束：

- PRIMARY 视图一致：同一个 replica set 在同一有效多数派视图中不应长期存在多个互相冲突的 PRIMARY。
- 配置版本一致：健康成员看到的 `config_version` 和 `config_term` 不应明显分叉。
- 成员列表一致：健康成员看到的 members 列表、host、votes、priority 不应出现互斥差异。
- Quorum 一致：`voting_members_count`、可投票成员数和多数派判断应与 members 配置一致。
- 心跳状态一致：如果 A 认为 B 不健康，但当前 A 到 B 的 TCP/27017 和 DNS 均正常，应继续检查 MongoDB heartbeat、认证、进程内状态和配置视图。
- 同步来源合理：SECONDARY 的 sync source 应来自同一健康多数派视图中的成员。

这些不变量不是直接结论。它们用于判断当前证据是否已经从“现象”推进到“机制”或“使故障发生的条件”。

## Split-Brain Deepening

识别 split-brain 后，不应停止在“发生脑裂”这一层。继续区分：

- 纯连通性分区：成员之间 DNS、TCP 或 overlay 网络仍异常，MongoDB heartbeat 失败与网络证据一致。
- 配置或成员视图分叉：不同成员看到的 `config_version`、members 列表或 quorum 不一致，即使当前 TCP 已恢复，也可能残留互斥决策视图。
- 进程内或认证问题：TCP 正常但 MongoDB heartbeat 失败，可能涉及 mongod 状态、认证、证书、keyFile、hostname 或 replica set 配置。
- 历史瞬时分区后遗留：当前网络已恢复，但历史 election、restart 或 reconfig 造成的状态仍未自动收敛。

Phase 4 应把这些分支写成候选假设，并用当前证据支持、反驳或标记为 insufficient。

## Read-Only Evidence

优先使用仓库内一等只读资产：

- `mongodb.collect.replicaset.rs_status`：采集多个成员视角的 `rs.status()`。
- `mongodb.collect.network.overlay`：当存在网络或 DNS 症状时采集 overlay、DNS 和 pod connectivity。
- `mongodb.collect.dns.coredns`：当存在服务解析、mongos startup DNS 错误或 kube-dns 连接异常时采集 DNS 证据。
- `mongodb.collect.logs.previous`：采集重启前日志，寻找 election、heartbeat、startup 和 fatal 线索。
- `mongodb.collect.logs.discover_sink`、`mongodb.collect.logs.file_tail`、`mongodb.collect.logs.node_file_tail`：当 `kubectl logs` 不足以覆盖 MongoDB 文件日志时使用。

二等临时只读验证可包括：

- 在各 mongod 成员上执行 `rs.conf()` 并比较 members、votes、priority、version 和 settings。
- 只读查询 `rs.status()` 中 election、term、optime、heartbeat message 和 sync source 字段。
- 只读查询 `config.shards` 或 mongos `getShardMap`，确认 mongos 广播的 shard host 是否与副本集视图一致。
- 从 MongoDB 日志中搜索 election、heartbeat、reconfig、stepdown、network timeout、auth failed 等关键词。

所有临时命令必须先经过只读 guardrail，不得写入数据库、修改 replica set 配置或改变 Kubernetes 资源。

## Counter-Evidence

这些证据会削弱常见错误假设：

- 当前所有相关 Pod 之间 TCP/27017 成功：削弱“持续网络分区仍在发生”的假设，但不能排除历史瞬时分区。
- 节点 CPU、内存、磁盘 IO 正常：削弱“资源打满导致副本不可用”的假设，但不能排除短时历史峰值。
- DNS 当前解析正常：削弱“当前 DNS 故障”的假设，但不能排除启动期 DNS 故障。
- 多个成员看到不同 `config_version` 或 members 列表：削弱“只是单个成员心跳误报”的假设。

反证应写入 `counter_evidence` 或 `deepening_findings.refutes`，避免报告继续把已削弱路径作为无条件下一步。

## Safety Boundary

诊断阶段禁止自动执行：

- `rs.reconfig()`，包括 force reconfig。
- `rs.stepDown()`、`replSetStepDown` 或强制重新选举。
- 删除 Pod、删除 PVC、清理数据目录、重建副本。
- 写入数据库或修改 Kubernetes 对象的命令。

如果后续进入处置阶段，必须先确认权威数据侧、业务写入路径、备份状态和回滚方案。
