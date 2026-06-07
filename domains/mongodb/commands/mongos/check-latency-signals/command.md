# Check MongoDB Latency Signals

## Purpose

快速收集 MongoDB 延迟突增相关的 mongos、shard、Pod 和日志信号。

## Commands

```bash
kubectl get pod -n <namespace> -o wide
kubectl logs -n <namespace> <mongos-pod> --tail=500
kubectl logs -n <namespace> <mongos-pod> --previous --tail=300
```

```javascript
db.adminCommand({ getShardMap: 1 })
rs.status()
```

## What To Look For

- 慢查询、timeout、connection reset、network error 是否增加
- 是否某个 mongos Pod 日志明显异常
- 是否某个 shard 或副本集成员异常
- 是否存在资源压力、重启或 previous 日志异常

## Notes

- 这些命令均为只读检查。
- 如果需要进一步查询 `currentOp` 或 profile，需要单独确认风险和数据量。
