# MongoDB Kubernetes Runtime Failure

## Goal

确认 MongoDB 故障是否由 Kubernetes runtime 或编排层导致，并把通用 K8s 信号映射到 MongoDB 组件影响。

## Read-Only Checks

1. 查看 Pod 和控制器状态。

```bash
kubectl get pod -n <namespace> -o wide
kubectl get statefulset -n <namespace>
```

2. 查看目标 Pod 条件和事件。

```bash
kubectl get pod -n <namespace> <pod> -o yaml
kubectl describe pod -n <namespace> <pod>
kubectl get events -n <namespace> --sort-by=.lastTimestamp
```

3. 根据通用信号分类。

- `pod-unschedulable`：调度失败，需要看 scheduler message。
- `pod-node-selector-mismatch`：nodeSelector 或 affinity 与节点标签不匹配。
- `pod-volume-binding-failed`：PVC、PV、StorageClass 或挂载失败。
- `pod-resource-insufficient`：节点 CPU、内存或临时存储不足。
- `pod-image-pull-failed`：镜像、仓库、凭证或网络问题。
- `pod-crashloop`：容器启动后反复退出。
- `pod-not-ready`：Running 但探针或服务就绪失败。
- `statefulset-replicas-not-ready`：控制器 ready 副本少于期望副本。

## MongoDB Impact Mapping

- `mongos` 不可用通常影响连接入口。
- `configsvr` 成员异常可能影响元数据路径和分片管理。
- `shard` 成员异常会降低副本冗余，严重时影响读写或分片可用性。
- 无法 `kubectl exec` 到未调度 Pod 时，应从其他成员补充 `rs.status()`。

## Safety

本 runbook 只做只读诊断。修改 node label、删除 Pod、调整资源、修改 StatefulSet、扩容 PVC 都属于处置动作，需要单独确认。
