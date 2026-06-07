# Models

本目录用于存放资产元数据模型。

当前已经开始沉淀第 3 段脚本合同模型：

- `script-manifest.schema.yaml`：领域脚本资产 manifest 合同
- `script-context.schema.yaml`：脚本 `context-file` 最小公共字段和 MongoDB 共享字段
- `script-output.schema.yaml`：脚本 `output-file` 最小公共字段、状态枚举和输出原则
- `script-runtime-map.schema.yaml`：插件运行时 `script_id -> runtime_path` 映射合同
- `remote-executor-request.schema.yaml`：远程执行器请求合同
- `remote-executor-result.schema.yaml`：远程执行器结果合同
- `runbook.schema.yaml`：runbook metadata 合同
- `command.schema.yaml`：command metadata 合同
- `skill.schema.yaml`：skill metadata 合同
- `adapter-output.schema.yaml`：插件命令面向用户或 Agent 平台的输出合同

未来会继续定义：

- 更严格的 JSON Schema 或校验器实现
