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
- 可从 `/start` 生成的 incident 目录继续执行 `/analyse`
- 不实现 vendor 插件协议
- analyse 当前调用本地 MongoDB analyse runner
- review 当前基于 `analysis.yaml` 做本地五维评分，不等同于正式人工反馈系统
