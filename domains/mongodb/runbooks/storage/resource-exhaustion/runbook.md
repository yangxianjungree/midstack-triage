# MongoDB Resource Exhaustion

## 适用场景

当 MongoDB 出现以下表现时使用本 runbook：

- Pod 反复重启
- Pod `Last State` 显示 `OOMKilled`
- 日志中出现 `No space left on device`
- Node 存在 MemoryPressure、DiskPressure 或 PIDPressure
- 复制延迟、连接失败或查询变慢同时伴随资源压力
- MongoDB 进程无法启动或启动后很快退出

## 目标

- 定位资源压力发生在哪一层
- 判断影响的是 mongos、configsvr、shard 还是 Kubernetes 运行层
- 输出只读诊断结论和下一步建议

## Step 1: 定位受影响对象

执行：

```bash
kubectl get pod -n <namespace> -o wide
kubectl get sts -n <namespace> -o wide
```

检查：

- 哪些 Pod 不 Ready
- 哪些 Pod 最近重启
- 重启集中在 mongos、configsvr 还是 shard
- 是否集中在同一个 Node

## Step 2: 检查 Pod 和容器状态

执行：

```bash
kubectl describe pod -n <namespace> <pod>
kubectl get pod -n <namespace> <pod> -o yaml
```

检查：

- `restartCount`
- `lastState`
- `reason: OOMKilled`
- readiness/liveness probe 失败
- container resource requests / limits
- recent events

判断逻辑：

- 如果 `OOMKilled` 明确存在，优先归类为内存压力。
- 如果探针失败伴随 CPU 或 IO 压力，继续检查 Node 和日志。
- 如果 Pod 无法调度，优先归类为调度或 Node 资源问题。

## Step 3: 检查 Node 状态

执行：

```bash
kubectl get node -o wide
kubectl describe node <node>
```

检查：

- MemoryPressure
- DiskPressure
- PIDPressure
- Allocated resources
- Node events
- 受影响 Pod 是否集中在同一 Node

## Step 4: 检查存储和日志信号

执行：

```bash
kubectl logs -n <namespace> <pod> --tail=300
kubectl logs -n <namespace> <pod> --previous --tail=300
```

关注：

- no space left
- WiredTiger error
- file open error
- too many open files
- OOM
- killed
- slow storage
- checkpoint or journal errors

## Step 5: 关联 MongoDB 拓扑

结合 `rs.status()` 和 shard map 判断：

- 资源压力是否影响 PRIMARY
- 是否影响 configsvr
- 是否影响单个 shard
- 是否导致复制延迟或成员状态异常

## Step 6: 输出结论

按以下格式输出：

```text
受影响对象: <pod/node/component>
资源类型: <memory|disk|io|fd|node-pressure|scheduling|unknown>
影响范围: <mongos|configsvr|shard|replica-member>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步建议: <next action>
```

## 安全说明

本 runbook 只做只读诊断。

不在本 runbook 内执行：

- 删除数据
- 重启 Pod
- 修改 resource limit
- 扩容 PVC
- 驱逐 Pod
- 修改 MongoDB 配置
