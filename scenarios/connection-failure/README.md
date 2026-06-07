# Connection Failure

跨中间件连接失败场景。

本场景只描述共性故障模式，不存放具体产品的 runbook、command 或 script。

## 典型表现

- 客户端连接超时
- 连接被拒绝
- 连接被 reset
- 认证失败
- Service、NodePort、Pod IP 或域名不可达
- 部分实例可连，部分实例不可连

## 诊断目标

- 确认失败发生在客户端、Kubernetes Service、Pod、网络、认证还是中间件进程
- 找到连接路径上的第一个断点
- 区分“Pod 运行中但服务不可用”和“Pod 本身异常”

## MongoDB 路由

MongoDB 领域资产见：

- `domains/mongodb/runbooks/connectivity/connection-failure/`
- `domains/mongodb/commands/connectivity/check-mongos-connectivity/`
- `domains/mongodb/skills/connectivity/triage-connection-failure/`
