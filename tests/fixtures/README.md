# Fixtures

本目录存放可离线回放的 incident fixture。

每个 fixture 建议包含：

- `input.yaml`
- `structured_record.yaml`
- `signal_bundle.yaml`
- `collection_report.yaml`
- `expected_analysis.yaml`

仓库内 fixture 约束：

- 只保留最小 replay 合同文件
- 不要把运行时生成物回写到 `tests/fixtures/`
- 以下文件属于生成物，应写到 `.local/` 或临时目录，不应纳入仓库：
  - `adapter-output.yaml`
  - `meta.yaml`
  - `remote-config.yaml`
  - `remote-executor-run.yaml`
  - `remote-executor.stdout.txt`
  - `remote-executor.stderr.txt`

第一批 MongoDB fixture：

- `mongodb/baseline-sharded-cluster`
- `mongodb/replica-inconsistency-sample`
- `mongodb/connection-failure-sample`

可使用 [tools/replay/mongodb-freeze-fixture.py](../../tools/replay/mongodb-freeze-fixture.py) 将 `.local` 中的 remote run 或 incident 冻结成新的 replay fixture。默认建议先输出到 `.local/fixtures/`，确认内容不包含敏感信息或大段原始日志后再决定是否纳入仓库。
