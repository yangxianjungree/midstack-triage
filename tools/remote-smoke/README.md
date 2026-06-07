# Remote Smoke Tools

本目录存放用于真实远程环境验证脚本资产的只读 smoke test 工具。

## MongoDB

运行 MongoDB MVP 脚本：

```bash
python3 tools/remote-smoke/mongodb-smoke.py --config .local/test-envs/mongodb-k8s.yaml
```

原则：

- `--config` 指向本地忽略文件，不提交账号密码
- 工具通过 SSH 进入跳板机
- 脚本投放到 `/tmp/midstack-triage/assets/scripts/mongodb/`
- 单次执行目录使用 `/tmp/midstack-triage/runs/<incident_id>/<script_id>/`
- 本地结果回收到 `.local/remote-runs/<incident_id>/`
- 只执行只读采集和 normalize 脚本

当前 MongoDB smoke 工具会按 manifest MVP 顺序执行 10 个脚本。
