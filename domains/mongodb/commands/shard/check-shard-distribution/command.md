# Check MongoDB Shard Distribution

## Purpose

快速判断 MongoDB 异常是否集中在某个 shard、成员、集合或资源位置。

## Commands

```javascript
db.adminCommand({ getShardMap: 1 })
rs.status()
```

```bash
kubectl get pod -n <namespace> -o wide
kubectl logs -n <namespace> <shard-pod> --tail=300
```

## What To Look For

- 是否某个 shard 相关 Pod 资源异常
- 是否某个 shard 副本集成员状态异常
- 是否某个 shard 日志中错误明显更多
- 是否只有部分集合或业务受影响

## Notes

- 这些命令均为只读检查。
- chunk 分布、balancer 和 shard key 分析可能需要后续单独扩展。
