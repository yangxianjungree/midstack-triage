# Triage MongoDB Connection Failure

## Goal

判断 MongoDB 连接失败发生在连接路径的哪一段，并将问题归类为 Service 路由、Pod readiness、网络、认证或 MongoDB 进程状态。

## Inputs

- 客户线索或业务报错文本
- namespace 或集群标识
- 可选：Service、NodePort、Pod、连接串或目标组件

## Workflow

1. 从客户线索中提取错误类型、时间戳和目标地址。
2. 如果目标地址不明确，先通过 Kubernetes Service 和 Pod 盘点定位候选 mongos 或 mongod。
3. 使用 `check-mongos-connectivity` command 检查 Service、endpoints、Pod readiness 和 Pod 内 ping。
4. 将信号归类到以下路径：
   - Service 或 endpoints 异常
   - Pod 未 Ready 或频繁重启
   - Pod 内 MongoDB 服务不可达
   - 认证失败
   - 业务侧连接路径或连接串异常
5. 输出失败路径、一级原因分类、关键证据、证据缺口和下一步 runbook。

## Stop Conditions

- 已定位连接路径上的第一个断点
- 已区分网络失败和认证失败
- 已确认需要用户补充目标地址或业务连接串
- 已识别到高风险处置动作，需要显式确认

## Output

```text
失败路径: <client -> service -> pod -> mongos/mongod>
一级归因: <service-routing|pod-readiness|network|authentication|process-state|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步: <next runbook or command>
```

## Safety Constraints

- 只执行只读检查。
- 不自动修改 Service、Secret、网络策略或 MongoDB 配置。
- 不自动重启 Pod。
