# MongoDB Kubernetes Runtime

关注 MongoDB 在 Kubernetes 中的运行时状态。

典型对象：

- Namespace
- StatefulSet
- Pod
- Service
- Endpoint / EndpointSlice
- Node
- Event
- Probe

优先关注：

- Pod 是否 Running / Ready
- StatefulSet 副本数是否符合预期
- Pod 是否频繁重启
- Node 是否存在资源压力
- Service 是否能路由到正确 Pod
