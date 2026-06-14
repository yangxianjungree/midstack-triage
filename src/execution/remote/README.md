# Remote Execution Plane

`src/execution/remote/` 放控制端连接远端执行面的正式实现。

当前边界：

- `access.py`
  SSH/SSHPass transport、基础环境校验、scp 收发。
- `executor.py`
  MongoDB 远程脚本执行器；负责编排 capability check、脚本投放、远端执行、结果回收。

规则：

- 这里是 execution plane，不是 phase 流程目录。
- `phase1`、`phase2`、`phase3` 可以调用这里，但不要把 transport 逻辑重新散落回 phase 目录。
- `tools/remote-executor/` 和 `tools/remote-smoke/` 只保留 CLI 壳。
