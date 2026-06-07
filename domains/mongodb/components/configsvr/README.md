# MongoDB configsvr

关注 MongoDB 分片集群中的 config server 副本集。

典型对象：

- configsvr StatefulSet
- configsvr Pod
- configsvr Service
- config server replica set members

优先关注：

- configsvr 副本集成员状态
- PRIMARY 是否存在
- configsvr 成员复制延迟
- mongos 到 configsvr 的连接状态
