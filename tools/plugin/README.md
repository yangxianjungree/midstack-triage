# Local Plugin Prototype

本目录存放本地插件命令原型。

目标：

- 验证 `/start`、`/analyse`、`/review` 三个命令的文件流转
- 不绑定 Claude Code、Codex 或 Cursor
- 默认写入 `.local/`，避免生成运行时 incident 到仓库正文

## Usage

创建本地 incident：

```bash
python3 tools/plugin/midstack-local.py start \
  --middleware mongodb \
  --customer-clue "MongoDB connection timeout" \
  --namespace psmdb-test
```

基于 fixture 或 incident 执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --input-dir tests/fixtures/mongodb/connection-failure-sample \
  --output-dir .local/incidents/connection-failure-sample
```

基于真实远程 smoke 结果执行 analyse：

```bash
python3 tools/plugin/midstack-local.py analyse \
  --remote-run-dir .local/remote-runs/mongodb-remote-smoke-20260607-182217 \
  --output-dir .local/incidents/from-remote-smoke \
  --scenario baseline
```

调度真实远程 smoke 后直接执行 analyse：

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

当前限制：

- 不实现正式 remote executor，只在本地原型中复用 remote smoke 工具
- 可消费已完成的 remote smoke 结果目录
- 可通过本地 remote smoke 工具调度真实只读采集
- 不实现 vendor 插件协议
- analyse 当前调用本地 MongoDB analyse runner
- review 当前基于 `analysis.yaml` 做本地五维评分，不等同于正式人工反馈系统
