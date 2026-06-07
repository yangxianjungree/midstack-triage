# Triage MongoDB Resource Exhaustion

## Goal

判断 MongoDB 故障是否由资源压力导致，并定位资源压力发生在 Pod、容器、PVC、Node 还是 MongoDB 进程层。

## Inputs

- 客户线索或业务症状
- namespace 或集群标识
- 可选：疑似 Pod、Node 或组件

## Workflow

1. 从客户线索中提取资源类关键词，例如 OOM、disk full、slow、restart、no space。
2. 使用 `check-pod-resource-pressure` command 检查 Pod、容器、Node 和日志信号。
3. 将资源信号与 MongoDB topology 关联，判断影响的是 mongos、configsvr 还是 shard。
4. 如果存在 previous 日志，优先使用重启前日志确认最后一次失败原因。
5. 输出资源类型、影响范围、关键证据、证据缺口和下一步 runbook。

## Stop Conditions

- 已确认资源压力类型
- 已确认资源压力影响范围
- 已确认证据不足，需要补充监控或系统日志
- 已识别到高风险处置动作，需要显式确认

## Output

```text
受影响对象: <pod/node/component>
资源类型: <memory|disk|io|fd|node-pressure|scheduling|unknown>
影响范围: <mongos|configsvr|shard|replica-member>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步: <next runbook or command>
```

## Safety Constraints

- 只执行只读检查。
- 不自动删除数据、重启 Pod、扩容 PVC 或修改资源限制。
