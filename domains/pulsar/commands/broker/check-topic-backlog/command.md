# Check Pulsar Topic Backlog

## Purpose

快速确认 topic backlog、subscription lag 和 broker 侧吞吐信号。

## Command

```bash
pulsar-admin topics stats persistent://<tenant>/<namespace>/<topic>
```

## What To Look For

- `backlog` 是否持续增长
- `subscriptions` 中 lag 是否集中在单个 consumer
- `publishRate` / `msgRateIn` 与 `msgRateOut` 是否失衡

## Notes

只读检查，适合 backlog 类问题的第一步。
