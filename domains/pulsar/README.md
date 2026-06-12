# Pulsar Domain

本目录存放 Apache Pulsar 专属排障资产。

当前已包含：

- 领域元数据
- 结构化排障记录样例
- `queue-backlog` 场景的首条 golden path 资产（runbook / skill / command / MVP 脚本）
- 离线 fixture：`tests/fixtures/pulsar/topic-backlog-sample`

后续如果继续扩展，建议优先覆盖：

- broker 不可用
- bookie 存储异常
- topic backlog
- ledger / under-replication
- zookeeper / metadata store 异常

仍然遵循：

- 物理对象与逻辑组件分层表达
- 先保留原始证据，再做信号治理
- 结论与知识沉淀分开输出
