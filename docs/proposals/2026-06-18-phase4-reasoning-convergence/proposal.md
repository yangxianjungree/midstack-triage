---
status: draft
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-17-module-refactor-roadmap/spec.md
  - ../2026-06-17-command-runtime-orchestration-hardening/plan.md
  - ../../concepts/architecture.md
  - ../../project/implementation-status.md
  - ../../project/phase4-multitrack-integration.md
---

# Proposal: Phase 4 推理核收敛与治理资产对齐

## 背景

Midstack 当前已经形成清晰的双平面运行时：

- control plane：`src/commands/`、`src/phases/`、`src/shared/`
- execution plane：`src/execution/`
- asset plane：`domains/`、`scenarios/`、`core/`、`interfaces/`
- adapter plane：`plugins/claude/`、`plugins/cursor/`

这条主架构方向成立，MongoDB MVP 也已经通过 fixture replay、score gate、插件安装态检查等门禁支撑。

当前主要架构债集中在 Phase 4 推理核和治理资产对齐：

1. `analysis.yaml` 有两个生产者路径。
   `src/phases/phase4/reasoning.py` 会通过 multitrack renderer 写入 `analysis.yaml`，随后 `src/commands/analyse.py` 又调用 `generate_rule_analysis()` 用 rules fallback 覆盖同一文件。
2. 三套推理机制并存但职责不够清楚。
   当前同时存在 multitrack reasoning、rules fallback、`agent-reasoning-task.md`，但生产输出实际主要来自 rules fallback。
3. 领域推理知识的落点没有被文档承认。
   MongoDB/Pulsar 规则位于 `src/phases/phase4/rules/<middleware>.py`，而文档对新中间件落点主要描述 `domains/<product>/` 和必要 `core/` 扩展。
4. L1 specs 中存在领域实现稿。
   `docs/specs/rs-status-collection-gap.spec.md` 包含 incident 引用、实现状态、测试策略和 MongoDB 专属实现细节，不适合作为 L1 稳定规范。
5. 架构检视 skill 已落后于现行 runtime。
   `.cursor/skills/midstack-architecture-review/` 仍以较早目录结构为评审基准，缺少 `src/` 双平面、插件 runtime 和当前治理门禁认知。
6. `component` 字段语义分叉。
   `domains/mongodb/metadata.yaml` 的 `components` 表达 MongoDB 逻辑组件；runbook/skill/command metadata 的 `component` 表达排查面或资产分区，例如 `connectivity`、`storage`、`kubernetes-runtime`。两者虽然已有注释区分，但字段名和 taxonomy 仍不足以长期防漂移。

## 目标

本提案目标是收敛 Phase 4 推理核的事实源和产物边界，并让文档、治理资产、taxonomy 与当前实现现实一致。

成功标准：

- `analysis.yaml` 只有一个明确生产者。
- rules fallback、multitrack、agent reasoning task 三者职责边界可被一句话说明。
- README、architecture、implementation status 不再暗示默认真实 Agent 多轨推理已经作为生产输出生效。
- `docs/specs/` 只保留稳定 L1 规范，领域实现稿迁出。
- 架构检视 skill 能按当前 `src/` 双平面和安装态 runtime 正确评审。
- MongoDB 资产中的逻辑组件与排查面命名有明确 taxonomy 或字段边界。

## 非目标

本提案不直接要求：

- 接入真实 Claude/Anthropic 推理作为默认生产路径。
- 重写 MongoDB rules engine。
- 将 `src/phases/phase4/rules/mongodb.py` 全量数据驱动下沉到 `domains/`。
- 改变 `/midstack:start`、`/midstack:analyse`、`/midstack:review` 的用户命令面。
- 重构 execution plane 的 SSH、kubectl、script runtime。
- 调整 MongoDB 诊断质量或新增场景规则。
- 处理 Pulsar MVP 支持状态、Python 版本兼容、全仓 metadata version/status 推广等横向治理问题。

## 变更类型

本提案涉及：

- 命令运行时产物职责：`analysis.yaml` 唯一生产者。
- 文档权威分层：迁移不适合 L1 的领域实现稿。
- 架构文档对齐：更新 README、architecture、implementation status。
- 治理资产更新：更新 `.cursor/skills/midstack-architecture-review/`。
- taxonomy / metadata 纪律：明确逻辑组件与排查面的字段或枚举边界。

## 当前状态

### Phase 4 三机制

| 机制 | 当前位置 | 当前状态 | 问题 |
| --- | --- | --- | --- |
| rules fallback | `src/phases/phase4/rules/` | 实际生产 `analysis.yaml` 的主要来源 | 领域规则硬编码在 `src/`，文档未充分承认 |
| multitrack | `src/phases/phase4/multitrack/` | 框架和测试存在，默认 mock | 会先写 `analysis.yaml`，随后被 rules 覆盖 |
| agent task | `agent-reasoning-task.md` | 给 Agent/人工 refinement 的任务合同 | 当前不是自动生产最终 `analysis.yaml` 的闭环 |

### 当前输出事实

`/midstack:analyse` 当前完成后：

- `analysis.yaml` 来自 rules fallback 和 guardrails。
- `analysis.rules-fallback.yaml` 保存 rules fallback 副本。
- `agent-reasoning-task.md` 指导后续 Agent refinement。
- `report.md` 由当前 `analysis.yaml` 渲染。
- multitrack 会生成 reasoning board，但其渲染到 `analysis.yaml` 的结果不保留为生产输出。

## 决策建议

### D1. 短期将 rules fallback 定义为 `analysis.yaml` 唯一生产者

短期采用最小风险方案：

- `analysis.yaml` 的生产者是 rules fallback + guardrails。
- multitrack 不再写 `analysis.yaml`。
- multitrack 输出保留为独立诊断辅助产物，例如：
  - `reasoning-board.yaml`
  - `analysis.multitrack.yaml`
  - 或 `phase4-multitrack-result.yaml`
- `agent-reasoning-task.md` 继续作为人工/Agent refinement 合同，不宣称自动闭环。

这保持当前真实能力不后退，同时消除双写和死路径。

### D2. 中期保留 multitrack 升级为唯一生产者的可能性

中期可以另开 proposal 评估：

- multitrack 是否接入真实 Agent。
- validation executor 如何接入只读补采或 evidence checker。
- rules fallback 是否变为 seed、baseline 或 fallback branch。
- review/score gate 如何评价 multitrack 产物。

在这之前，不把 multitrack 描述为默认生产推理核。

### D3. 承认 `src/phases/phase4/rules/<middleware>.py` 是当前 rules engine 落点

文档应明确：

- `domains/<product>/` 存资产、脚本、runbook、skill、command。
- `src/phases/phase4/rules/<middleware>.py` 存当前运行时规则分析器。
- 新中间件如要进入 `/midstack:analyse` 生产路径，短期需要补 rules analyser 或明确不支持分析。

后续是否把规则数据驱动下沉到 `domains/`，单独决策。

### D4. `rs-status-collection-gap.spec.md` 迁出 L1 specs

建议迁移到：

- `docs/proposals/2026-06-12-phase4-reasoning-model/`，如果视为历史实现计划；
- 或 `docs/analysis/`，如果视为一次 MongoDB sandbox 诊断分析。

迁移后，在 `docs/specs/README` 或 `docs/README.md` 保持 L1 列表不包含该文件。

### D5. 更新架构检视 skill

`.cursor/skills/midstack-architecture-review/` 应更新为当前架构：

- 识别 `src/commands`、`src/phases`、`src/execution`、`src/shared`。
- 识别 Claude bundled runtime 与 Cursor workspace-local runtime。
- 识别 `tools/` 只做工程入口、校验、回放、生成、导入。
- 将 `domains/*/components`、`tools/generators`、`tools/importers` 标为现行有效路径，而非旧式待砍/延后路径。
- 增加 Phase 4 三机制边界检查项。

### D6. 明确 component 字段语义

两种可选方案：

| 方案 | 内容 | 优点 | 成本 |
| --- | --- | --- | --- |
| A. 新增 taxonomy | 增加 `core/taxonomies/component-types.yaml` 或 `asset-surface-types.yaml` | 保留现有字段，先建立校验事实源 | 中低 |
| B. 字段改名 | 将资产 metadata 的 `component` 改为 `surface` / `triage_surface` | 语义最清楚 | 需要迁移资产和 validator |

建议先采用方案 A，避免一次性改动大量领域资产。

## 影响范围

### 运行时代码

可能涉及：

- `src/phases/phase4/reasoning.py`
- `src/phases/phase4/renderer.py`
- `src/commands/analyse.py`
- `tests/phases/phase4/test_renderer.py`
- `tests/tools/plugin/test_midstack_analyse.py`

短期改动应保持 `/midstack:analyse` 用户可见输出不退化。

### 文档

需要更新：

- `README.md`
- `docs/concepts/architecture.md`
- `docs/project/implementation-status.md`
- `docs/project/phase4-multitrack-integration.md`
- `docs/README.md`
- `docs/specs/rs-status-collection-gap.spec.md` 的迁移位置或引用

### 治理资产

需要更新：

- `.cursor/skills/midstack-architecture-review/SKILL.md`
- `.cursor/skills/midstack-architecture-review/checklist.md`
- `.cursor/skills/midstack-architecture-review/report-template.md`（如引用旧结构）

### Taxonomy / Validator

可能涉及：

- `core/taxonomies/component-types.yaml` 或新的排查面 taxonomy。
- MongoDB asset validator。
- tool boundary / runtime classification validator，视实际文档更新范围决定。

## 兼容性

短期方案应兼容现有 incident 和 fixture：

- `analysis.yaml` 继续存在。
- `analysis.rules-fallback.yaml` 继续存在。
- `agent-reasoning-task.md` 继续存在。
- `report.md` 继续由 `analysis.yaml` 渲染。

如果新增 multitrack 独立产物：

- 该产物是增量文件，不破坏旧消费者。
- adapter output 可选择性加入 record ref，但不应替代 `analysis` record ref。

如果新增 component taxonomy：

- 先只增加 validator warning 或文档引用。
- 字段改名必须另开迁移任务，不能在本提案中隐式完成。

## 落地切片

### Slice 1. 消除 `analysis.yaml` 双写

目标：

- `src/phases/phase4/reasoning.py` 不再写生产 `analysis.yaml`。
- multitrack 输出写入独立文件或只写 reasoning board。
- `src/commands/analyse.py` 仍由 rules fallback 写入 `analysis.yaml`。

验收：

- `tests/phases/phase4/*` 更新为检查独立 multitrack 产物。
- `tests/tools/plugin/test_midstack_analyse.py` 继续通过。
- replay/score gate 不退化。

### Slice 2. 文档现实对齐

目标：

- README 和 implementation status 明确当前默认推理路径。
- architecture 补充 Phase 4 rules engine 的短期落点。
- phase4 multitrack 文档标注默认 mock 和非生产 `analysis.yaml` 生产者状态。

验收：

- 文档不再出现“默认真实 Claude API 推理编排已生效”的歧义表述。
- 新中间件落地说明包含 rules analyser 或明确 skeleton 状态。

### Slice 3. 迁移 rs-status 实现稿

目标：

- 将 `docs/specs/rs-status-collection-gap.spec.md` 移到 proposals 或 analysis。
- 保留必要引用，避免断链。
- `docs/README.md` 的 specs 列表只包含稳定 L1 规范。

验收：

- `docs/specs/` 不再包含 incident-specific implementation note。
- 迁移文件 front matter 标为 `draft` 或 `archived`，不作为 L1 裁决依据。

### Slice 4. 更新架构检视 skill

目标：

- `.cursor/skills/midstack-architecture-review/` 对齐当前目录与双平面 runtime。
- checklist 增加 Phase 4 三机制、安装态 runtime、L1/L3 文档分层检查。

验收：

- skill 不再建议删除现行有效目录。
- skill 能识别 `src/execution` 与 `plugins/*/runtime` 的职责。

### Slice 5. Component taxonomy

目标：

- 增加或明确一个 taxonomy，区分 MongoDB 逻辑组件与排查面。
- 更新 MongoDB metadata 注释或 validator 规则。

验收：

- `domains/mongodb/metadata.yaml` 的 `components` 与资产 metadata 的 `component` 不再被视为同一枚举。
- validator 至少能发现未知排查面字段值。

## 测试与门禁

最小验证：

```bash
python3 -m py_compile $(find src -type f -name '*.py')
python3 -m pytest tests/phases/phase4 tests/tools/plugin/test_midstack_analyse.py -q
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
git diff --check
```

完整门禁：

```bash
python3 tools/validators/validate-repo.py
python3 -m pytest tests/execution tests/phases tests/shared tests/tools -q
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
```

若改动插件命令或安装态 runtime，再运行：

```bash
python3 plugins/claude/plugin-install.py check --workspace "$SANDBOX"
python3 plugins/cursor/plugin-install.py --check-workspace "$SANDBOX"
python3 plugins/cursor/test-agent-cli.py
```

## 风险与回滚

风险：

- 改 Phase 4 输出路径时，fixture replay 或 score gate 可能依赖当前 `analysis.yaml` 写入时机。
- 文档过度承认 `src/phases/phase4/rules/<mw>.py` 后，可能固化硬编码规则落点。
- component taxonomy 如果命名不准，会增加一次后续迁移。

回滚方式：

- Slice 1 保持 `analysis.yaml` schema 和内容不变，只改变 multitrack 产物位置；如失败可恢复旧写入路径。
- 文档更新可独立回滚，不影响 runtime。
- taxonomy 先以新增和 warning 形式落地，不直接重命名字段。

## Open Questions

1. multitrack 独立产物的标准文件名选哪个？
   建议：`analysis.multitrack.yaml`，因为它与 `analysis.rules-fallback.yaml` 对称。
2. `rs-status-collection-gap.spec.md` 更适合迁到 `docs/proposals/` 还是 `docs/analysis/`？
   建议：如果保留为历史整改计划，迁到 proposals；如果保留为事件分析快照，迁到 analysis。
3. Phase 4 rules engine 中期是否要从 Python 硬编码迁为 domain asset？
   建议：暂不在本提案决策，只记录为后续 proposal。
4. component taxonomy 应命名为 `component-types` 还是 `triage-surface-types`？
   建议：如果保留现有字段名，先用 `component-types`；如果准备改字段，优先 `triage-surface-types`。

## 相邻问题

以下问题来自同轮架构检视，但不建议并入本提案主线；它们应另开小提案或直接作为工程修复处理。

### A1. Python 3.8 运行兼容

当前仓库运行环境仍可能是 Python 3.8。`Path | None`、`str | None`、`List[str] | None` 等 PEP 604 写法在未启用 `from __future__ import annotations` 的模块中会导致 import-time failure。

已知影响面包括：

- `tools/support/common.py`
- `src/commands/analyse.py`
- `src/execution/remote/runtime_support.py`
- `src/execution/remote/executor.py`
- `src/execution/remote/context.py`
- `src/execution/remote/capabilities.py`
- `plugins/claude/runtime/bin/resolve-workspace.py`

建议二选一：

- 明确项目最低 Python 版本为 3.10+，并在 README、testing gates、plugin runtime 文档中声明；
- 或将 runtime / validator 路径恢复到 Python 3.8 兼容写法，例如 `Optional[Path]`。

该问题会直接影响 `python3 tools/validators/validate-repo.py`，优先级应高于大规模重构。

### A2. Pulsar 支持状态名实对齐

Pulsar 当前有 skeleton 资产、golden path、两个 MVP 脚本和 rules analyser，但 README 已标为 Skeleton，尚未达到 MongoDB Active MVP 完整度。

需要另行决策：

- 保留 Pulsar rules analyser 和 golden path，但文档继续明确为 Skeleton；
- 或补齐 Pulsar 到 MongoDB 同等 analyse 主链路；
- 或从生产 `/midstack:analyse` supported middleware 中移除 Pulsar，避免误认为已完整支持。

短期建议保持 README 的 Skeleton 定位，并在 analyse unsupported/supported 文案中区分 "rules analyser exists" 与 "Active MVP supported"。

### A3. `queue-backlog` applicable middleware

`scenarios/queue-backlog/scenario.yaml` 当前包含：

- `pulsar`
- `mongodb`

但当前 MongoDB 资产中没有对应 queue-backlog runbook/skill/command 链路。需要二选一：

- 从 `queue-backlog` 的 `applicable_middleware` 移除 `mongodb`；
- 或补齐 MongoDB backlog/data queue 语义下的对应资产，并明确与 `data-hotspot`、`latency-spike` 的边界。

### A4. 领域资产 metadata version/status

部分 core templates 已包含 `status`，但 runbook/skill/command metadata 并未全仓统一 `version` / `status` 字段。该问题属于 metadata governance，不应在 Phase 4 推理核收敛中顺手改。

建议先选一个资产族试点：

- `domains/mongodb/skills/**/metadata.yaml`
- 或 `domains/mongodb/runbooks/**/metadata.yaml`

试点稳定后再推广到 schema、validator 和模板。

## 落地清单

- [ ] 决策 `analysis.yaml` 唯一生产者。
- [ ] 调整 Phase 4 multitrack 输出，不再覆盖生产 `analysis.yaml`。
- [ ] 更新 README、architecture、implementation status 和 phase4 集成文档。
- [ ] 迁移 `rs-status-collection-gap.spec.md`。
- [ ] 更新 `.cursor/skills/midstack-architecture-review/`。
- [ ] 新增或明确 component / triage surface taxonomy。
- [ ] 补充对应测试或 validator。
- [ ] 运行最小门禁和必要 replay/score gate。
