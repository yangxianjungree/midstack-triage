# Replay Tools

本目录存放离线 replay 工具。

共享工程 helper 位于 `tools/support/common.py`；这里只保留 replay 领域逻辑，不再在每个脚本里重复 repo 根路径、YAML I/O、子进程调用封装。

## MongoDB Fixture Replay

从已完成的 remote run 冻结 fixture：

```bash
python3 tools/replay/mongodb-freeze-fixture.py \
  --remote-run-dir .local/remote-runs/<incident_id> \
  --fixture-dir .local/fixtures/mongodb/<case_id> \
  --case-id <case_id> \
  --scenario baseline
```

从已完成的 incident 冻结 fixture：

```bash
python3 tools/replay/mongodb-freeze-fixture.py \
  --incident-dir .local/incidents/<incident_id> \
  --fixture-dir .local/fixtures/mongodb/<case_id> \
  --case-id <case_id> \
  --scenario baseline
```

当前第一版支持 fixture 读取、回放摘要，以及调用本地 MongoDB analyse runner 生成分析结果。

```bash
python3 tools/replay/mongodb-replay.py
```

生成每个 fixture 的本地 analyse 输出：

```bash
python3 tools/replay/mongodb-replay.py --run-analyse
```

默认读取：

```text
tests/fixtures/mongodb/*/
```

输出：

- case id
- middleware
- scenario
- customer clue
- expected conclusion
- fixture 文件完整性

## MongoDB Score Summary

生成 replay 评分文件：

```bash
python3 tools/replay/mongodb-score.py --run-analyse
```

要求所有评分维度至少达到 `medium`：

```bash
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

默认写入：

```text
.local/scores/mongodb/*.score.yaml
```

汇总 replay 评分文件：

```bash
python3 tools/replay/mongodb-score-summary.py
```

默认读取：

```text
tests/scores/mongodb/*.score.yaml
```

汇总本地生成评分：

```bash
python3 tools/replay/mongodb-score-summary.py --score-root .local/scores/mongodb
```
