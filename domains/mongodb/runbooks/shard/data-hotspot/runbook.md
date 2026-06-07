# MongoDB Data Hotspot

## 适用场景

当 MongoDB 只有部分 shard、集合、租户、key range 或节点出现异常负载、延迟或错误时使用本 runbook。

## 目标

- 判断是否存在数据或请求热点
- 定位受影响 shard、成员、集合或 key range
- 区分热点问题和集群整体资源不足

## Step 1: 确认热点是否局部化

检查：

- 是否只有部分业务或集合受影响
- 是否只有某个 shard 相关请求变慢
- 是否只有某些 Pod 或 Node 资源压力明显

## Step 2: 采集 shard map

执行：

```javascript
db.adminCommand({ getShardMap: 1 })
```

检查：

- shard 列表
- shard 到 replica set 的映射
- 受影响业务是否可能集中在某个 shard

## Step 3: 关联副本集和资源状态

执行：

```javascript
rs.status()
```

并结合 Kubernetes Pod / Node 状态检查：

- 某个 shard PRIMARY 是否异常
- 某个 shard 是否复制延迟
- 某个 shard Pod 是否有资源压力
- 是否只有某个 Node 上的 shard 异常

## Step 4: 输出结论

```text
热点对象: <shard/member/collection/key-range>
热点类型: <data-distribution|request-routing|resource|topology|unknown>
关键证据: <evidence>
证据缺口: <missing evidence>
下一步建议: <next action>
```

## 安全说明

本 runbook 只做只读诊断。

不执行：

- moveChunk
- reshardCollection
- 修改 shard key
- 修改 balancer
- 重启 shard 成员
