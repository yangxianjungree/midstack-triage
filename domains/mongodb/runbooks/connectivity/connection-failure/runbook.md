# MongoDB Connection Failure

## 适用场景

当客户提供的信息表现为以下情况时使用本 runbook：

- 业务连接 MongoDB 超时
- 业务连接被拒绝或 reset
- 业务日志中出现认证失败
- 某个 MongoDB Service、NodePort、mongos 或 mongod 无法访问
- Pod 是 `Running`，但业务仍然无法连接

## 目标

- 确认连接失败发生在哪一段路径
- 区分 Kubernetes Service、Pod、网络、认证和 MongoDB 进程问题
- 在不修改生产环境的前提下给出下一步建议

## Step 1: 解析客户线索

从客户提供的信息中提取：

- 报错类型：timeout、refused、reset、authentication failed、DNS failure
- 报错时间
- 目标地址：Service、NodePort、Pod IP、域名或连接串
- 目标组件：mongos、configsvr、shard member 或未知
- 是否只有部分业务或部分节点失败

如果客户线索不能判断目标组件，先进入 Kubernetes 对象和 Service 路由检查。

## Step 2: 检查 Kubernetes Service 和 endpoints

执行：

```bash
kubectl get svc,endpoints,endpointslice -n <namespace> -o wide
```

检查：

- Service 是否存在
- Service 类型是否符合预期
- NodePort 是否存在且端口正确
- endpoints 是否为空
- endpoints 是否指向预期 Pod
- EndpointSlice 中的 ready 状态是否异常

判断逻辑：

- 如果 endpoints 为空，优先检查 selector、Pod readiness 和 Service 配置。
- 如果 endpoints 指向非预期 Pod，优先检查 selector 或部署架构识别是否错误。
- 如果 Service 正常但连接失败，继续检查目标 Pod。

## Step 3: 检查目标 Pod 状态

执行：

```bash
kubectl get pod -n <namespace> -o wide
kubectl describe pod -n <namespace> <pod>
```

检查：

- Pod 是否 `Running`
- Ready 是否为 true
- 最近是否重启
- 是否存在 readiness/liveness probe 失败
- Pod 所在 Node 是否异常
- 事件中是否有调度、镜像、OOM、探针或网络相关问题

判断逻辑：

- 如果 Pod 未 Ready，优先归类为 Pod readiness 或进程状态问题。
- 如果 Pod 频繁重启，继续查看当前日志和 previous 日志。
- 如果 Pod Ready 但连接失败，继续做 Pod 内连接检查。

## Step 4: 在 Pod 内检查 MongoDB 服务可达性

对 mongos 或目标 mongod Pod 执行：

```bash
kubectl exec -n <namespace> <pod> -- mongosh --eval 'db.runCommand({ ping: 1 })'
```

如果需要认证，按当前部署架构获取认证来源：

- Bitnami：优先从 Pod 环境变量或密码文件环境变量读取
- operator+CRD：后续从 Secret 读取，第一版仅作为预留

检查：

- `mongosh` 是否存在
- `ping` 是否成功
- 是否出现认证失败
- 是否连接到错误端口或错误数据库
- 是否只有某个 Pod 内失败

判断逻辑：

- Pod 内 ping 成功但业务失败，优先检查 Service、NodePort、网络路径或业务连接串。
- Pod 内 ping 失败且 Pod Ready，优先检查 MongoDB 进程、认证或端口监听。
- 认证失败需要单独归类，不要误判为网络失败。

## Step 5: 检查日志和时间线

重点查看报错时间附近：

- mongos 日志
- 目标 mongod 日志
- Pod previous 日志
- Kubernetes 事件

关注：

- authentication failed
- connection accepted / ended
- network timeout
- socket error
- too many connections
- process restart
- readiness probe failed

## Step 6: 输出结论

按以下格式输出：

```text
失败路径: <client -> service -> pod -> mongos/mongod>
失败类型: <service-routing|pod-readiness|network|authentication|process-state|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步建议: <next action>
```

## 安全说明

本 runbook 只做只读诊断。

不在本 runbook 内执行：

- 修改 Service 或 selector
- 重启 Pod
- 修改认证 Secret
- 修改网络策略
- 修改 MongoDB 配置
