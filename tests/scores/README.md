# Scores

本目录用于保存 replay case 的评分结果。

当前命令入口仍保持：

- [tools/replay/mongodb-score-summary.py](../../tools/replay/mongodb-score-summary.py)

对应实现已经收敛到：

- `tools/replay/mongodb/score_summary.py`

评分维度：

- `evidence_completeness`
- `hypothesis_coverage`
- `validation_depth`
- `conclusion_confidence`
- `knowledge_reusability`

评分等级：

- `high`
- `medium`
- `low`

顶层脚本只保留 CLI 入口，不再承载评分汇总逻辑。
