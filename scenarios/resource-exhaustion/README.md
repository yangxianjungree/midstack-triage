# Resource Exhaustion

跨中间件资源耗尽场景。

本场景只描述资源类故障的共性模式，不存放具体产品的 runbook、command 或 script。

## 典型表现

- Pod OOMKilled
- Pod 反复重启
- 磁盘空间不足
- 磁盘 IO 饱和
- Node 存在 MemoryPressure、DiskPressure 或 PIDPressure
- 中间件日志出现存储层错误、无法写入、打开文件过多
- 复制延迟、查询延迟或连接失败伴随资源压力

## 诊断目标

- 确认资源压力发生在 Pod、容器、PVC、Node 还是中间件进程
- 将资源信号与具体中间件组件和拓扑成员关联
- 避免把资源导致的间接故障误判为网络或拓扑问题

## MongoDB 路由

MongoDB 领域资产见：

- `domains/mongodb/runbooks/storage/resource-exhaustion/`
- `domains/mongodb/commands/kubernetes-runtime/check-pod-resource-pressure/`
- `domains/mongodb/skills/storage/triage-resource-exhaustion/`
