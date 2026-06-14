# Phase 5

`src/phases/phase5/` 放第 5 段“结论整合与知识沉淀”的正式实现。

当前边界：

- `finalize.py`
  分析收口、guardrail、最终输出整理。
- `review.py`
  分析复核、五维评分和改进建议。

规则：

- 第 5 段消费前面阶段的结果，不回头承载远程采集或 Phase 4 推理主循环。
- 输出合同类公共逻辑应优先下沉到 `src/shared/analysis_runtime.py`。
