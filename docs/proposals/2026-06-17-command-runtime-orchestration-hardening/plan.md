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

梳理 Midstack 的控制面编排边界，让 `src/commands/analyse.py`、Phase 3 采集治理和 Phase 4 推理结果格式化各自只做一件事。

本阶段不改 slash command 面，不改插件安装流程，不改远程 transport 实现，也不直接优化 analyse 的根因判断质量。目标是先把命令层、编排层和推理层拆清楚。

## Success Criteria

1. `src/commands/analyse.py` 只负责命令级编排和结果收口，不再承担过多分支、格式化和重复的状态推进逻辑。
2. Phase 3 采集治理能清晰区分 remote-run 载入、incident 重建、directed recollection、collection report 归一化。
3. Phase 4 推理入口能清晰区分 L1 映射、multitrack orchestration、analysis.yaml 输出格式化。
4. 控制面命令的最小测试集能覆盖 ready / blocked 路径、current incident 行为和输出文件落盘。
5. `/midstack:analyse`、`/midstack:review`、`/midstack:finalize-analysis` 的用户可见语义不回退。
6. 命令层与 phase 层的职责边界在文档中能被一句话说清。
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

### Slice 1. `analyse` 命令层减薄

目标：

- 把 `src/commands/analyse.py` 中与 incident bootstrap、remote run routing、结果收口相关的共用分支收拢成更小的 helper。
- 保留 `analyse.py` 作为命令入口，但把可重用的 orchestration 逻辑搬到更聚焦的内部模块或同层 helper。

文件：

- `src/commands/analyse.py`
- `tests/tools/plugin/test_midstack_analyse.py`

验收：

```bash
python3 -m pytest tests/tools/plugin/test_midstack_analyse.py -q
git diff --check
```

### Slice 2. Phase 3 采集治理拆分

目标：

- 将 remote-run 载入、incident 重建、directed recollection 和 report 归一化拆成清晰函数边界。
- 让 Phase 3 继续负责输入治理，但不再吞掉 Phase 4 的职责。

文件：

- `src/phases/phase3/collection.py`
- `tests/phases/phase3/test_collection.py`

验收：

```bash
python3 -m pytest tests/phases/phase3/test_collection.py -q
python3 -m pytest tests/tools/plugin/test_midstack_analyse.py -q
git diff --check
```

### Slice 3. Phase 4 reasoning facade 收紧

目标：

- 将 L1 映射、multitrack orchestration 和 analysis.yaml 格式化拆开。
- 让 `src/phases/phase4/reasoning.py` 只保留稳定入口语义。

文件：

- `src/phases/phase4/reasoning.py`
- `src/phases/phase4/multitrack/*`
- `tests/phases/phase4/multitrack/*`

验收：

```bash
python3 -m pytest tests/phases/phase4/multitrack -q
python3 -m pytest tests/tools/plugin/test_midstack_analyse.py -q
git diff --check
```

### Slice 4. 控制面回归门禁

目标：

- 给 analyse / review / finalize 的命令级输出补最小回归证明。
- 确认控制面拆分后，用户看到的文件和状态不回退。

文件：

- `tests/tools/plugin/test_midstack_analyse.py`
- `tests/phases/phase3/test_collection.py`
- `tests/phases/phase4/multitrack/*`

验收：

```bash
python3 -m pytest tests/tools/plugin/test_midstack_analyse.py tests/phases/phase3 tests/phases/phase4/multitrack -q
git diff --check
```

## Implementation Order

1. Slice 1：先减薄 `analyse.py`。
2. Slice 2：拆 Phase 3 采集治理。
3. Slice 3：收紧 Phase 4 reasoning facade。
4. Slice 4：补控制面回归门禁。

## Boundaries

Always:

- 每个 slice 独立提交。
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
