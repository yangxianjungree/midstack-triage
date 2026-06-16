# Fixtures

本目录存放可离线回放的 incident fixture。

## 目录边界

- `active/<middleware>/`
  默认 replay、score 和 repo validator 会读取的稳定样本。
- `legacy/<middleware>/`
  历史样本归档区。放入前需要说明为什么不再进入默认门禁。
- `raw/`、`private/`、`sensitive/`
  只允许本地临时使用，已被 `.gitignore` 忽略，不得入库。

每个 active fixture 至少包含：

- `input.yaml`
- `structured_record.yaml`
- `signal_bundle.yaml`
- `collection_report.yaml`
- `expected_analysis.yaml`

## 准入规则

- 只保留最小 replay 合同文件，避免把现场大段原始日志塞进仓库。
- `signal_bundle.yaml` 必须包含能支撑 expected conclusion 的最小证据链。
- `expected_analysis.yaml` 必须与当前实际 analyse 输出对齐，不能只靠 customer clue 命中。
- 凭据、客户名、公网 IP、私钥、token 和未脱敏 remote config 不得入库。
- 内网 IP 第一轮作为 warning 处理；新增 fixture 仍应优先使用文档保留地址或明确假值。
- 运行时生成物应写入 `.local/` 或临时目录，不应纳入仓库。

以下文件属于运行时生成物：

- `adapter-output.yaml`
- `meta.yaml`
- `remote-config.yaml`
- `remote-executor-run.yaml`
- `remote-executor.stdout.txt`
- `remote-executor.stderr.txt`

可使用 [tools/replay/mongodb-freeze-fixture.py](../../tools/replay/mongodb-freeze-fixture.py) 将 `.local` 中的 remote run 或 incident 冻结成新的 replay fixture。默认先输出到 `.local/fixtures/`，确认内容通过 hygiene 检查后再移动到 `tests/fixtures/active/<middleware>/`。
