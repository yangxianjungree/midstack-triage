# Data Hotspot

跨中间件数据热点场景。

本场景只描述共性故障模式，不存放具体产品资产。

## 典型表现

- 某个 shard、partition、node 或 key range 压力明显更高
- 延迟只影响部分数据或部分租户
- 数据分布不均衡
- 请求路由集中到少数节点

## MongoDB 路由

MongoDB 领域资产见：

- `domains/mongodb/runbooks/shard/data-hotspot/`
- `domains/mongodb/commands/shard/check-shard-distribution/`
- `domains/mongodb/skills/shard/triage-data-hotspot/`
