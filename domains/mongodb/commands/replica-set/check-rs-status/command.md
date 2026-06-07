# Check MongoDB Replica Set Status

## Purpose

快速确认副本集当前角色分布、成员健康状态和复制进度。

## Command

```javascript
rs.status()
```

## What To Look For

- `members[].stateStr` 是否为预期角色
- `members[].health` 是否为 `1`
- `members[].optimeDate` 是否明显落后
- 是否存在 `RECOVERING`、`STARTUP2`、`UNKNOWN` 等异常状态

## Notes

这是只读检查命令，适合作为副本集类问题的第一步。
