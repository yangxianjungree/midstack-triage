# Phase 4

`src/phases/phase4/` 放第 4 段“推理与论证”的正式实现。

当前边界：

- `reasoning.py`
  第 4 段门面入口；对上层命令只暴露 `run_phase4_analysis`。
- `multitrack/`
  多轨推理底层实现，包括 reasoning board、track、lead orchestrator、agent 适配层。
- `rule_drafts/`
  middleware 规则保底分析器；生成 `analysis.yaml` 基础草稿，供后续推理和报告链路使用。

规则：

- 第 4 段负责生成和更新推理结论，不承载第 3 段远程采集或第 5 段最终报告落盘。
- 顶层 `phase4/` 只保留清晰门面和阶段级说明；复杂实现继续收在 `multitrack/`。
- 规则 analyse runner 也属于第 4 段正式运行时，统一收在 `rule_drafts/`，不再把主实现留在 `tools/analyse/`。
- 第 4 段代码统一收敛在 `src/phases/phase4/` 下，不再保留平行旧目录。
