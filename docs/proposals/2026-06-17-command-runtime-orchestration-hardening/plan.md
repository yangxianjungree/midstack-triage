---
status: draft
last_updated: 2026-06-17
supersedes: none
superseded_by: none
related:
  - ../2026-06-17-module-refactor-roadmap/spec.md
  - ../2026-06-17-slash-command-surface-hardening/plan.md
  - ../../project/testing-and-install-gates.md
  - ../../specs/plugin-runtime.spec.md
---

# Plan: 控制面编排模块整改

## Objective

梳理 Midstack 的控制面编排边界，让 Phase 1 到 Phase 5 的控制面职责、输入输出和命令层边界更清楚。

本阶段不改 slash command 面，不改插件安装流程，不改远程 transport 实现，也不直接优化 analyse 的根因判断质量。目标是先把命令层、编排层和推理层拆清楚。

## Decisions

已确认：

- `Proposed Slices` 以 `Phase 1` 到 `Phase 5` 组织，供评审使用。
- `Phase 1` 和 `Phase 2` 先做边界评审，不优先进入实现。
- 实现顺序采用 `Phase 3 -> Phase 4 -> analyse 命令层减薄 -> Phase 3-5 回归门禁`。
- `Phase 5` 暂不单独拆更细 proposal，先保留在这份 plan 里。

## Success Criteria

1. Phase 1 到 Phase 5 都能说清控制面职责，不让命令层、phase 层和执行层继续混边界。
2. `src/commands/analyse.py` 只负责命令级编排和结果收口，不再承担过多分支、格式化和重复的状态推进逻辑。
3. Phase 3 采集治理能清晰区分 remote-run 载入、incident 重建、directed recollection、collection report 归一化。
4. Phase 4 推理入口能清晰区分 L1 映射、multitrack orchestration、analysis.yaml 输出格式化。
5. 控制面命令的最小测试集能覆盖 ready / blocked 路径、current incident 行为和输出文件落盘。
6. `/midstack:analyse`、`/midstack:review`、`/midstack:finalize-analysis` 的用户可见语义不回退。
7. 现有 slash 命令面和安装态门禁继续通过。

## Scope

包含：

- `src/commands/analyse.py`
- `src/commands/review.py`
- `src/commands/finalize.py`
- `src/phases/phase3/collection.py`
- `src/phases/phase4/reasoning.py`
- `src/phases/phase4/multitrack/*`
- `tests/tools/plugin/test_midstack_analyse.py`
- `tests/phases/phase3/test_collection.py`
- `tests/phases/phase4/multitrack/*`

不包含：

- slash command markdown 和 Cursor rules
- plugin installer / workspace state / sandbox 投影
- `src/execution/remote/*` 的 transport 重构
- Phase 4 推理质量调优或新模型接入
- 新 agent 适配器

## Current Observations

`src/commands/analyse.py` 当前同时处理：

- incident mode bootstrap
- remote collection 和 remote run replay
- scenario routing 和 directed recollection
- Phase 4 reasoning 调度
- analysis.yaml / report.md / agent-reasoning-task.md 收口

`src/phases/phase3/collection.py` 当前同时处理：

- remote run 载入
- incident 重建
- skill runtime context enrich
- directed recollection
- remote executor next action / user action 归一化

`src/phases/phase4/reasoning.py` 当前是 Phase 4 的入口 facade，但还承担 `analysis.yaml` 输出格式化。

`src/commands/review.py` 和 `src/commands/finalize.py` 目前比较薄，不是首要拆分对象。

当前风险：

- `analyse` 命令层会继续长胖，后续很难判断哪些是编排，哪些是业务逻辑。
- Phase 3 和 Phase 4 的边界如果不先切开，测试会继续把不同层的问题混在一起。
- `analysis.yaml` 输出格式和 reasoning 过程耦合太紧，后续改报告时容易误伤推理主路径。

## Proposed Slices

当前先处于“待评审”状态。以下切片按 5 个 phase 组织，目的是先让你评审控制面边界，而不是直接进入实现。

### Slice 1. Phase 1 启动边界

目标：

- 复核 Phase 1 在控制面中的职责是否只包括 incident 启动、最小输入校验、remote validation 入口。
- 确认 Phase 1 不吞并 Phase 2 之后的编排逻辑。

当前重点文件：

- `src/commands/start.py`
- `src/phases/phase1/`

评审点：

- Phase 1 的输出合同是否已经足够支撑 Phase 2 和 `/midstack:start`。
- 是否需要把更多环境校验从命令层再下沉。

### Slice 2. Phase 2 盘点边界

目标：

- 复核 namespace、对象、拓扑、auth hint 的控制面边界。
- 确认 Phase 2 的盘点结果是否应继续由 start 流程内完成。

当前重点文件：

- `src/phases/phase2/`
- `src/commands/start.py`

评审点：

- Phase 2 的 auto-discovery、ambiguous、not_found 三类结果是否和 start 命令层解耦得足够清楚。

### Slice 3. Phase 3 采集治理边界

目标：

- 将 remote-run 载入、incident 重建、directed recollection、collection report 归一化拆成清晰函数边界。
- 让 Phase 3 继续负责输入治理，但不再吞掉 Phase 4 的职责。

当前重点文件：

- `src/phases/phase3/collection.py`
- `src/commands/analyse.py`

评审点：

- Phase 3 是否应该继续由 `analyse.py` 直接调度，还是抽成更显式的 orchestration helper。
- directed recollection 是否已经侵入了命令层收口逻辑。

### Slice 4. Phase 4 推理边界

目标：

- 将 L1 映射、multitrack orchestration 和 analysis.yaml 格式化拆开。
- 让 `src/phases/phase4/reasoning.py` 只保留稳定入口语义。

当前重点文件：

- `src/phases/phase4/reasoning.py`
- `src/phases/phase4/multitrack/*`
- `src/phases/phase4/rules/*`

评审点：

- rules fallback、multitrack orchestration、analysis renderer 三者是否应该进一步分层。

### Slice 5. Phase 5 收口边界

目标：

- 复核 finalize、review、report、score 的命令层与 phase 层边界。
- 确认 `analyse` 完成后哪些收口动作仍属于控制面，哪些只是后续质量反馈。

当前重点文件：

- `src/commands/finalize.py`
- `src/commands/review.py`
- `src/phases/phase5/*`
- `src/shared/analysis_runtime.py`

评审点：

- `analysis.yaml`、`report.md`、`agent-reasoning-task.md`、review 输出的职责是否过于耦合。

## Implementation Order

评审通过后，再按以下顺序进入实现：

1. 先做 Phase 3，因为 `analyse.py` 当前最大复杂度来自 Phase 3 编排。
2. 再做 Phase 4，收紧 reasoning facade。
3. 然后回头减薄 `src/commands/analyse.py`，让它只保留命令层编排。
4. 最后统一补 Phase 3-5 的控制面回归门禁。

## Boundaries

Always:

- 当前文档先用于评审，不直接触发实现。
- 评审通过后的每个 slice 独立提交。
- 改命令层先补最小测试，再动实现。
- 保持 `analyse`、`review`、`finalize-analysis` 的用户行为不回退。
- 优先抽小 helper，不要先引入过度抽象。

Ask first:

- 新增公开命令或改变命令参数。
- 改动 analysis/review 输出合同。
- 把 Phase 4 推理质量改动和结构拆分混在一个 slice。

Never:

- 把远程 transport 逻辑迁回命令层。
- 把 slash command 面当成控制面实现。
- 让 Phase 3 / Phase 4 的职责边界继续模糊化。

## Open Questions

1. `src/commands/analyse.py` 的 helper 是放在同文件内，还是抽成同级内部模块更清晰？
2. Phase 3 的重构是否需要先提炼“remote-run 重建”单独 helper，再拆 directed recollection？
3. Phase 4 的 `analysis.yaml` 格式化应不应该与 reasoning 输出分离成独立 renderer？
