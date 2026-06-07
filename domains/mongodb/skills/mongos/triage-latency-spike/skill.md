# Triage MongoDB Latency Spike

## Goal

判断 MongoDB 延迟突增的来源，并将其归类为查询负载、路由、复制、资源、存储或热点问题。

## Workflow

1. 提取延迟时间窗口和影响范围。
2. 使用 `check-latency-signals` command 收集 mongos 日志、Pod 状态、shard map 和 rs.status。
3. 将延迟信号与资源、复制、shard 或热点信号关联。
4. 输出一级归因、关键证据、证据缺口和下一步建议。

## Stop Conditions

- 已确认延迟时间窗口
- 已确认主要受影响组件或 shard
- 已识别证据不足，需要补充监控或慢查询数据
- 已遇到高风险动作，需要显式确认

## Output

```text
延迟窗口: <time window>
影响范围: <component/shard/business>
一级归因: <query-workload|routing|replication|resource|storage|hotspot|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步: <next action>
```
