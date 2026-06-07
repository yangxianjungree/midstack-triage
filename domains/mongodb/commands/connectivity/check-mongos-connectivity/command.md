# Check MongoDB mongos Connectivity

## Purpose

快速判断 MongoDB 连接失败是否发生在 Kubernetes Service 路由、mongos Pod 状态、Pod 内 MongoDB 服务、认证或业务侧连接路径。

## Commands

检查 Service 和 endpoints：

```bash
kubectl get svc,endpoints,endpointslice -n <namespace> -o wide
```

检查 mongos Pod：

```bash
kubectl get pod -n <namespace> -o wide
kubectl describe pod -n <namespace> <mongos-pod>
```

在 Pod 内执行 ping：

```bash
kubectl exec -n <namespace> <mongos-pod> -- mongosh --eval 'db.runCommand({ ping: 1 })'
```

## What To Look For

- Service 是否存在且端口符合预期
- endpoints 是否为空
- endpoints 是否指向 Ready Pod
- mongos Pod 是否 Ready
- Pod 是否近期重启
- `mongosh ping` 是否成功
- 是否出现认证失败而不是网络失败

## Notes

- 这些命令均为只读检查。
- 如果需要认证，优先使用部署架构中已有的认证来源，不要在输出中记录密码。
