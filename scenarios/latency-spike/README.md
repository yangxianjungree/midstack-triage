# Latency Spike

跨中间件延迟突增场景。

本场景只描述共性故障模式，不存放具体产品资产。

## 典型表现

- 业务请求变慢
- 慢查询或慢请求日志增加
- 超时比例上升
- 延迟只影响部分分片、分区、节点或租户
- 延迟与资源压力、拓扑变化或热点数据相关

## MongoDB 路由

MongoDB 领域资产见：

- `domains/mongodb/runbooks/mongos/latency-spike/`
- `domains/mongodb/commands/mongos/check-latency-signals/`
- `domains/mongodb/skills/mongos/triage-latency-spike/`
