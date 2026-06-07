# Replay Tools

本目录存放离线 replay 工具。

## MongoDB Fixture Replay

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
