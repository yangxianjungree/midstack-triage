# Remote Execution Plane

`src/execution/remote/` 放控制端连接远端执行面的正式实现。

当前边界：

- `access.py`
  SSH/SSHPass transport、基础环境校验、scp 收发。
- `transport.py`
  执行编排使用的 transport 接口；默认 remote transport 委托 `access.py` 的
  SSH/scp 函数，local transport 在本机通过 subprocess/文件复制执行同一套编排。
- `error_contract.py`
  remote executor 的错误码、状态映射、capability check 条目和通用错误分类。
- `capabilities.py`
  兼容导出旧 capability 符号；新实现优先落到对应子模块。
- `executor_preflight.py`
  executor 批量运行前的基础 preflight：remote 检查本地 `sshpass`、SSH、远端
  `kubectl`、集群上下文和 `kubectl exec` 权限；local 检查本机 shell、
  `kubectl`、集群上下文和 `kubectl exec` 权限。
- `mongodb_collection_runtime.py`
  MongoDB Pod/容器目标解析、mongo shell 选择、pod 内执行目标摘要。
- `script_capabilities.py`
  单脚本执行前的目标 Pod 解析、pod 内工具探测和脚本级 capability check。
- `runtime_support.py`
  远端执行 runtime 的时间戳、YAML/JSON IO、runtime-map 解析等底层支持。
- `script_output_contract.py`
  远程脚本 `output.yaml` 的字段合同和校验。
- `context.py`
  context profile、目标集、namespace 选择、inventory 采集与执行上下文构建。
- `kubectl.py`
  远端 `kubectl get ... -o json` 的执行面 helper；Phase2 只保留兼容转发。
- `contracts.py`
  remote workspace、request/result、run summary 等合同对象构建。
- `script_runner.py`
  单个远程脚本的上下文生成、执行、输出校验和产物回收。
- `executor.py`
  MongoDB 远程脚本执行器兼容门面；保留旧导入面和 `python -m execution.remote.executor`。
- `cli.py`
  执行器 CLI 参数解析和批量编排；`python -m execution.remote.executor` 仍通过
  兼容入口转发到这里，`--transport local` 显式选择本地执行。

规则：

- 这里是 execution plane，不是 phase 流程目录。
- `phase1`、`phase2`、`phase3` 可以调用这里，但不要把 transport 逻辑重新散落回 phase 目录。
- 仓库不再保留 `tools/remote-executor/` 和 `tools/remote-smoke/` 兼容壳；正式入口统一是 `src/execution/remote/executor.py`。
- `executor.py` 可以作为兼容门面对外暴露符号，但新实现优先写入对应子模块；单脚本执行放在 `script_runner.py`，CLI 编排放在 `cli.py`。
- 需要 monkeypatch transport 的验证器，继续从 `executor.py` 打补丁；门面负责把当前模块的 `run_ssh`/`scp_*` 注入到底层实现。
