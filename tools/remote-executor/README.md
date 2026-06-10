# Remote Executor

本目录存放插件运行时使用的远程执行层实现。

当前：

- `mongodb-executor.py` 是 MongoDB 第一版远程执行入口
- 负责 capability checks、脚本投放、远程运行、结果回收
- 通过 `script-runtime-map` 解析插件运行时脚本路径
- 为每个脚本执行生成 `remote-executor-request.yaml` 和 `remote-executor-result.yaml`
- 为整批 remote run 生成顶层 `remote-executor-run.yaml`
- preflight `blocked` / `failed` 时也会保留本地 run 目录和结构化 batch result，便于 incident 导入与复盘
- 对 `mongos.get_shard_map` 和 `replicaset.rs_status` 额外执行脚本级 preflight：
  - target pod 解析
  - Pod 内 `mongosh` / `mongo` 可用性检查
  - 对应错误分类优先落 `target_pod_not_found` / `pod_tool_missing`
- 当前会消费 `/start` `object-inventory.yaml` 里的 `auth_hints.selected_secret_ref`，把只读 `secret_ref` hint 注入 `mongos_query` / `replicaset_query`

兼容关系：

- `tools/remote-smoke/mongodb-smoke.py` 继续保留为 smoke CLI 包装入口
- 本地插件 analyse 直接调用本目录下的执行器脚本
