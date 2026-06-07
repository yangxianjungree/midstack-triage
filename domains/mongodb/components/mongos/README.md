# MongoDB mongos

关注 MongoDB 分片集群中的路由层。

典型对象：

- mongos StatefulSet
- mongos Pod
- mongos Service / NodePort
- shard map
- 客户端连接入口

优先关注：

- mongos 是否 Ready
- mongos 是否能连接 config server
- mongos `getShardMap` 是否能返回 shard 映射
- 业务连接是否打到正确 mongos 入口
