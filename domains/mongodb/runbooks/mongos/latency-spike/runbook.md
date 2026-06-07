# MongoDB Latency Spike

## 适用场景

当业务反馈 MongoDB 查询、写入或连接响应变慢，但服务未完全不可用时使用本 runbook。

## 目标

- 确认延迟发生的时间窗口
- 判断延迟来自 mongos 路由、查询负载、资源压力、复制异常、存储问题还是数据热点
- 输出只读诊断结论和下一步建议

## Step 1: 确认时间窗口和影响范围

从客户线索中提取：

- 延迟开始时间
- 受影响业务
- 连接入口或连接串
- 是否只影响读、写或特定集合
- 是否伴随 timeout 或连接失败

## Step 2: 检查 mongos 和 Pod 状态

执行：

```bash
kubectl get pod -n <namespace> -o wide
kubectl logs -n <namespace> <mongos-pod> --tail=500
```

关注：

- mongos 是否重启
- 是否有大量 connection、timeout、slow query、network 相关日志
- 是否集中在某个 mongos Pod

## Step 3: 关联 shard map 和副本集状态

执行：

```javascript
db.adminCommand({ getShardMap: 1 })
rs.status()
```

检查：

- 是否某个 shard 成员异常
- 是否 PRIMARY 发生变化
- 是否存在复制延迟
- 是否只有某个 shard 相关请求变慢

## Step 4: 关联资源信号

检查：

- Pod restart
- OOMKilled
- Node pressure
- disk / IO 相关日志
- previous 日志中的失败原因

## Step 5: 输出结论

```text
延迟窗口: <time window>
影响范围: <business/component/shard>
一级归因: <query-workload|routing|replication|resource|storage|hotspot|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步建议: <next action>
```

## 安全说明

本 runbook 只做只读诊断。

不执行：

- killOp
- 重启 Pod
- 修改索引
- 修改 balancer
- 修改连接池或业务配置
