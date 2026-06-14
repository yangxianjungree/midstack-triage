# Local Plugin CLI Adapter

本目录存放本地 CLI 适配层。

目标：

- 验证 `/start`、`/analyse`、`/review` 三个命令的文件流转
- 不绑定 Claude Code、Codex 或 Cursor
- 默认写入 `.local/`，避免生成运行时 incident 到仓库正文
- 保持 `midstack-local.py` 为薄入口，核心实现放到 `src/commands/plugin_cli.py`、`src/phases/` 与 `src/shared/`
- 作为本地 CLI 调试入口，而不是 Claude 插件安装后的实际运行时源码目录

边界：

- `tools/plugin/midstack-local.py`
  只负责启动 `src/commands/plugin_cli.py`、返回退出码。
- Claude 插件安装后的真实运行入口在 `plugins/claude/runtime/bin/`
- Cursor 适配器通过 workspace `engine_root` 调用这个本地入口
- 新的共享逻辑不要继续写回 `tools/plugin/`

## Usage

创建本地 incident：

```bash
python3 tools/plugin/midstack-local.py start \
  --middleware mongodb \
  --customer-clue "运维巡检发现一个 MongoDB 节点异常。" \
  --environment-ip 192.168.154.251 \
  --username root \
  --password '<password>' \
  --port 22 \
  --namespace psmdb-test
```

`start` 会执行最小环境校验：

- SSH `echo ok`
- `kubectl version --client=true`
- `kubectl get nodes`

基于 `start` 生成的 incident 执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --incident-dir .local/incidents/<incident_id>
```

如果刚执行过 ready 的 `start`，也可以直接分析最近 incident：

```bash
python3 tools/plugin/midstack-local.py analyse
```

`analyse` 完成后会生成：

- `analysis.yaml`：结构化分析结果
- `report.md`：面向用户的 Markdown 排障报告
- `adapter-output.yaml`：插件命令摘要输出

基于 fixture 或 incident 执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --input-dir tests/fixtures/mongodb/connection-failure-sample \
  --output-dir .local/incidents/connection-failure-sample
```

基于已完成的远程采集结果执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --remote-run-dir .local/remote-runs/mongodb-remote-run-20260607-182217 \
  --output-dir .local/incidents/from-remote-run \
  --scenario baseline
```

调度真实远程采集后直接执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --remote-config .local/test-envs/mongodb-k8s.yaml \
  --output-dir .local/incidents/from-remote-config \
  --scenario baseline
```

生成 review：

```bash
python3 tools/plugin/midstack-local.py review \
  --incident-dir .local/incidents/connection-failure-sample
```

`review` 会把五维评分写入 `analysis.yaml` 的 `review` block，并生成 `review-adapter-output.yaml` 摘要输出。

当前限制：

- 本地 CLI 适配层当前通过 `src/execution/remote/executor.py` 调度真实只读采集
- 可消费已完成的远程采集结果目录
- 可通过 `--remote-config` 直接调度同一执行器
- 当前 remote executor 已按 `script-runtime-map` 查找脚本，并为每个脚本执行生成 `remote-executor-request.yaml` / `remote-executor-result.yaml`
- 当前 remote executor 也会为整批 remote run 生成 `remote-executor-run.yaml`
- 当前 remote executor 已对 `mongos.get_shard_map` 和 `replicaset.rs_status` 增加脚本级 target / pod tool preflight
- `/start` 当前会从 Pod / StatefulSet 的显式 `secretKeyRef` 中提取 MongoDB 认证 `secret_ref` hint，并传给 analyse context
- 当 remote executor preflight `blocked` 或 batch `failed` 时，`analyse` 会保留 incident 侧 `collection_report.yaml` 和 run-level 证据，并返回对应 `blocked` / `failed` adapter output
- 可从 `/start` 生成的 incident 目录继续执行 `/analyse`
- 不实现 vendor 插件协议
- analyse 当前调用本地 rules runner 生成 `analysis.yaml` 草稿，并结合第 4 段 / 第 5 段运行时继续整理输出
- review 当前基于 `analysis.yaml` 做本地五维评分，不单独生成 `review.yaml`
