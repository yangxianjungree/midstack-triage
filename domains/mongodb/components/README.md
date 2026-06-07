# MongoDB Components

本目录是 MongoDB 组件入口索引。

原则：

- 这里只描述组件边界和排障关注点
- 不复制 runbook、command、skill 正文
- 具体资产仍存放在 `runbooks/`、`commands/`、`skills/`、`scripts/`
- 一个 runbook 仍只存一份，组件入口只负责导航

当前组件入口：

- `connectivity`
- `mongos`
- `configsvr`
- `shard`
- `replica-set`
- `storage`
- `kubernetes-runtime`
