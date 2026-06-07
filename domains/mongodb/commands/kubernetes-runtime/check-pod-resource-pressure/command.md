# Check MongoDB Pod Resource Pressure

## Purpose

快速确认 MongoDB Pod 是否存在资源压力、重启、OOM、探针失败、Node 压力或调度异常。

## Commands

查看 Pod 状态：

```bash
kubectl get pod -n <namespace> -o wide
```

查看目标 Pod 明细：

```bash
kubectl describe pod -n <namespace> <pod>
kubectl get pod -n <namespace> <pod> -o yaml
```

查看 Node 状态：

```bash
kubectl get node -o wide
kubectl describe node <node>
```

查看当前和 previous 日志：

```bash
kubectl logs -n <namespace> <pod> --tail=300
kubectl logs -n <namespace> <pod> --previous --tail=300
```

## What To Look For

- `restartCount` 是否增加
- `lastState.reason` 是否为 `OOMKilled`
- events 中是否有探针失败或调度失败
- Node 是否存在 MemoryPressure、DiskPressure、PIDPressure
- 日志中是否有 no space、OOM、too many open files 或存储层错误

## Notes

- 这些命令均为只读检查。
- 如果发现资源压力，只输出证据和建议，不直接执行重启、扩容或清理动作。
