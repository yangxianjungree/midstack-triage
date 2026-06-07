# Replay

本目录用于记录 fixture replay 的流程和后续工具入口。

第一版目标：

1. 读取 `tests/fixtures/mongodb/<case_id>/`
2. 将 `input.yaml`、`structured_record.yaml`、`signal_bundle.yaml`、`collection_report.yaml` 作为 analyse 输入
3. 生成实际 `analysis.yaml`
4. 与 `expected_analysis.yaml` 做人工或半自动对比

当前最小 replay 工具：

- [tools/replay/mongodb-replay.py](/home/stephen/AI/midstack-triage/tools/replay/mongodb-replay.py)

第一版 replay 工具只输出 fixture 摘要，不执行完整 analyse 推理引擎。

完整 analyse runner 实现前，fixture 仍可用于人工回放和 prompt / 规则评审。
