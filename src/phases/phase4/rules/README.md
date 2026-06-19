# Phase 4 Rules

`src/phases/phase4/rules/` 放第 4 段规则保底分析器。

当前边界：

- `mongodb.py`
  MongoDB 规则分析器；根据 incident 目录里的输入、信号和采集结果生成基础 `analysis.yaml` 草稿。
- `pulsar.py`
  Pulsar 规则分析器；当前服务于 Skeleton / contract path，不代表 Pulsar 已达到 MongoDB Active MVP。
- `__init__.py`
  middleware -> analyser 的正式调度入口，供 `src/commands/analyse.py` 直接调用；同时暴露 middleware support state，区分 Active MVP 与 contract path。

规则：

- 这里放的是正式运行时代码；replay、校验和人工单跑直接调用这里的 CLI 入口。
- 多 middleware 共用的逻辑，优先继续下沉到 `src/shared/`，不要在这里复制。
- 所有规则分析器都应输出 `retrieval_context`、`experience_matches` 和 `source_boundaries`；历史经验当前只预留为空匹配列表，未来接入召回后也只能作为假设来源或验证路径来源，不能直接进入当前故障的 `supporting_evidence` 或 `conclusion_summary.evidence`。
