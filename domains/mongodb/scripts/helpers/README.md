# MongoDB Script Helpers

本目录用于放 MongoDB 脚本共享函数、解析辅助和公共校验。

第一版暂未放入可直接执行脚本。

## 边界

`helpers/` 只放脚本内部复用逻辑，不作为插件运行时的直接入口。

可以放：

- YAML / JSON 读写辅助
- 标准 `output-file` 生成辅助
- 时间戳处理
- Kubernetes 对象解析
- MongoDB `rs.status()` / `getShardMap` 解析
- 日志分类和过滤规则

不放：

- 直接执行入口脚本
- SSH 登录逻辑
- remote executor 逻辑
- 高风险处置动作

如果某个 helper 本身需要成为可执行入口，必须在 `manifest.yaml` 中登记为正式脚本。
