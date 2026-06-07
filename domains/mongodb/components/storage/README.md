# MongoDB Storage

关注 MongoDB 存储层和磁盘相关问题。

典型对象：

- PVC / PV
- data directory
- WiredTiger
- disk usage
- disk IO
- filesystem errors

优先关注：

- 磁盘空间是否不足
- IO 是否饱和
- 是否存在存储层错误日志
- 是否影响复制或进程启动
