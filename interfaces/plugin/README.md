# Plugin Interfaces

本目录只放给外部适配器消费的接口定义和数据契约。

当前已确定的一类接口包括：

- 脚本运行时映射接口
  - 用于将主仓库脚本资产的 `script_id` 映射到插件包内部的真实脚本路径
  - 相关样例见 [script-runtime-map.example.yaml](script-runtime-map.example.yaml)
  - 轻量模型见 [core/models/script-runtime-map.schema.yaml](../../core/models/script-runtime-map.schema.yaml)
- 远程执行器接口
  - 用于描述插件运行时如何进入用户提供的远程 K8s 环境、执行脚本并回收结果
  - 请求样例见 [remote-executor-request.example.yaml](remote-executor-request.example.yaml)
  - 结果样例见 [remote-executor-result.example.yaml](remote-executor-result.example.yaml)
  - 请求模型见 [core/models/remote-executor-request.schema.yaml](../../core/models/remote-executor-request.schema.yaml)
  - 结果模型见 [core/models/remote-executor-result.schema.yaml](../../core/models/remote-executor-result.schema.yaml)
- 插件命令输出接口
  - 用于描述 `/start`、`/analyse`、`/review` 返回给用户或 Agent 平台的摘要输出
  - 输出样例见 [adapter-output.example.yaml](adapter-output.example.yaml)
  - 输出模型见 [core/models/adapter-output.schema.yaml](../../core/models/adapter-output.schema.yaml)

不在本仓库中实现以下内容：

- Claude Code 插件执行逻辑
- Codex 适配器实现
- Cursor 适配器实现

这些实现应位于独立仓库或独立子项目中。
