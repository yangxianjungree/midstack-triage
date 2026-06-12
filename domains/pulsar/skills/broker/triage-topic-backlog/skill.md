# Triage Pulsar Topic Backlog

## Goal

判断 Pulsar topic backlog 是消费停滞、broker 压力、bookie 存储还是路由问题，并收敛影响面。

## Workflow

1. 收集 broker topic stats，确认 backlog 是否持续增长。
2. 对比受影响 topic 的 producer / consumer 速率与 subscription lag。
3. 若 broker 正常而 bookie 异常，转入存储链路检查。
4. 输出简短结论，并链接 topic-backlog runbook。

## Stop Conditions

- 已确认受影响 topic 和 subscription
- 已形成一级原因分类
- 已给出下一步 runbook 路径
