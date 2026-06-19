# Triage MongoDB Replica Member Not Healthy

## Goal

判断 MongoDB 副本集成员不健康的具体表现，并将问题归类到拓扑、网络、资源或复制积压。

## Workflow

1. 收集 `rs.status()` 输出，确认异常成员和当前角色分布。
2. 参考 `domains/mongodb/components/replica-set/invariants.md`，对比多成员视角下的 PRIMARY、config、members 和 quorum 是否一致。
3. 对比异常成员的 `health`、`stateStr`、`optimeDate`。
4. 如果成员不可达，转入连接或网络方向检查。
5. 如果成员可达但复制落后，优先检查资源和复制积压。
6. 输出简短结论，并链接对应 runbook。

## Stop Conditions

- 已确认异常成员
- 已形成一级原因分类
- 已给出下一步 runbook 路径
