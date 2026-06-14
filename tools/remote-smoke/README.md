# Remote Smoke Tools

本目录存放用于真实远程环境验证脚本资产的只读 smoke test 工具。

当前 `mongodb-smoke.py` 作为兼容保留的 smoke 入口，实际执行本体位于 `src/execution/remote/executor.py`，`tools/remote-executor/mongodb-executor.py` 只保留薄壳。

## MongoDB

运行 MongoDB MVP 脚本：

```bash
python3 tools/remote-smoke/mongodb-smoke.py --config .local/test-envs/mongodb-k8s.yaml
```

原则：

- `--config` 指向本地忽略文件，不提交账号密码
- 工具通过 SSH 进入跳板机
- 脚本按 `script-runtime-map` 的插件相对路径投放到远端 `assets/scripts/`
- 单次执行目录使用 `/tmp/midstack-triage/runs/<incident_id>/<script_id>/`
- 本地结果回收到 `.local/remote-runs/<incident_id>/`
- 顶层会额外写 `capability-checks.yaml`
- 顶层会额外写 `remote-executor-run.yaml`
- 每个脚本执行会额外落 `remote-executor-request.yaml` 和 `remote-executor-result.yaml`
- 只执行只读采集和 normalize 脚本
- 即使 preflight 被 `blocked` 或 batch `failed`，也应保留本地 run 目录和结构化 batch result

当前 MongoDB smoke 工具会按 manifest MVP 顺序执行 11 个脚本。
