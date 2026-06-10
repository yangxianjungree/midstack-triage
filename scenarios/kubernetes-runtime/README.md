# Kubernetes Runtime Failure

跨中间件 Kubernetes 运行时故障场景。

本场景只描述 Kubernetes 运行时层故障的共性模式，不存放具体产品的 runbook、command 或 script。

## 典型表现

- Pod 长期 Pending / ContainerCreating / CrashLoopBackOff
- StatefulSet ready 副本数少于期望
- Kubernetes 事件报告调度、PVC 绑定或镜像拉取失败
- 容器反复重启或就绪/存活探针失败
- 中间件因节点、调度或卷问题不可用，而非自身进程问题

## 诊断目标

- 确认故障发生在调度、镜像、卷、探针还是控制器层
- 将 Kubernetes 运行时故障映射到受影响的中间件组件和影响范围
- 避免把 Kubernetes 运行时故障误判为中间件自身、网络或资源压力问题

## MongoDB 路由

MongoDB 领域资产见：

- `domains/mongodb/runbooks/kubernetes-runtime/kubernetes-runtime-failure/`
- `domains/mongodb/skills/kubernetes-runtime/triage-kubernetes-runtime-failure/`
- `domains/mongodb/commands/kubernetes-runtime/check-pod-resource-pressure/`
