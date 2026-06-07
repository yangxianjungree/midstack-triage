# Triage MongoDB Data Hotspot

## Goal

判断 MongoDB 是否存在数据或请求热点，并定位受影响 shard、成员、集合或 key range。

## Workflow

1. 从客户线索中提取受影响业务、集合、租户、key range 或时间窗口。
2. 使用 `check-shard-distribution` command 收集 shard map、rs.status、Pod 和日志信号。
3. 判断异常是否集中在某个 shard、成员、Node 或集合。
4. 区分数据分布热点、请求路由热点、资源压力和拓扑异常。
5. 输出热点对象、热点类型、关键证据、证据缺口和下一步建议。

## Stop Conditions

- 已定位热点候选对象
- 已确认不是集群整体资源问题
- 已识别需要补充 chunk、balancer 或业务维度数据
- 已遇到高风险处置动作，需要显式确认

## Output

```text
热点对象: <shard/member/collection/key-range>
热点类型: <data-distribution|request-routing|resource|topology|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步: <next action>
```
