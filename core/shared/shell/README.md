# shell

这里只放跨中间件可复用的 shell 约定和片段。

允许：

- 通用 shell 规范
- 输出解析约定
- 环境变量约定

不允许：

- `mongosh`
- `redis-cli`
- `kafka-topics.sh`

凡是依赖具体中间件工具的内容，都应放到对应 `domains/<product>/` 下。
