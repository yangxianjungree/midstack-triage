# Remote Execution Plane

`src/execution/remote/` 放控制端连接远端执行面的正式实现。

当前边界：

- `access.py`
  SSH/SSHPass transport、基础环境校验、scp 收发。
- `capabilities.py`
  远端 capability check、错误分类、Pod 目标解析与 pod 内工具探测。
- `mongodb_collection_runtime.py`
  MongoDB Pod/容器目标解析、mongo shell 选择、pod 内执行目标摘要。
- `runtime_support.py`
  远端执行 runtime 的时间戳、YAML/JSON IO、runtime-map 解析等底层支持。
- `context.py`
  context profile、目标集、namespace 选择、inventory 采集与执行上下文构建。
- `contracts.py`
  remote workspace、request/result、run summary 等合同对象构建。
- `executor.py`
  MongoDB 远程脚本执行器门面；负责编排脚本投放、远端执行、结果回收，并兼容旧的导入面。

规则：

- 这里是 execution plane，不是 phase 流程目录。
- `phase1`、`phase2`、`phase3` 可以调用这里，但不要把 transport 逻辑重新散落回 phase 目录。
- 仓库不再保留 `tools/remote-executor/` 和 `tools/remote-smoke/` 兼容壳；正式入口统一是 `src/execution/remote/executor.py`。
- `executor.py` 可以作为兼容门面对外暴露符号，但新实现优先写入对应子模块。
- 需要 monkeypatch transport 的验证器，继续从 `executor.py` 打补丁；门面负责把当前模块的 `run_ssh`/`scp_*` 注入到底层实现。
