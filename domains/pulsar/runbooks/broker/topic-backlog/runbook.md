# Pulsar Topic Backlog

## 适用场景

- topic backlog 持续增长
- consumer lag 无法回落
- broker 日志出现 ledger write timeout 或 backlog 告警

## Step 1: 确认积压范围

检查：

- 受影响 topic / subscription / tenant
- backlog 是否集中在单个 broker 或 bookie
- 是否伴随 broker 或 bookie Pod 异常

## Step 2: 区分消费停滞与写入压力

- 若 consumer 无 ack 进展，优先查 consumer 侧
- 若 broker 写入超时或 bookie 异常，优先查存储链路

## Step 3: 输出阶段性结论

记录受影响对象、最可信原因分类和只读下一步验证动作。
