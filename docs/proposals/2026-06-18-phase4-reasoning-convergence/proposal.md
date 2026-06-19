---
status: completed
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

整改前主要架构债集中在 Phase 4 推理核和治理资产对齐：

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
- 统一 runtime root / workspace root 解析合同。
- 处理 scenario、routing、domain assets 三方一致性治理。
- 处理 Pulsar MVP 支持状态、Python 版本兼容、全仓 metadata version/status 推广等横向治理问题。

## 变更类型

本提案涉及：

- 命令运行时产物职责：`analysis.yaml` 唯一生产者。
- 文档权威分层：迁移不适合 L1 的领域实现稿。
- 架构文档对齐：更新 README、architecture、implementation status。
- 治理资产更新：更新 `.cursor/skills/midstack-architecture-review/`。
- taxonomy / metadata 纪律：明确逻辑组件与排查面的字段或枚举边界。

## Spec-driven 需求梳理

### 假设

1. 本轮整改目标是兑现本提案内的 Phase 4 收敛和治理资产对齐，不处理相邻 P1/P2 架构债。
2. `/midstack:analyse` 用户命令面保持兼容；已有消费者继续读取 `analysis.yaml`、`report.md` 和 `adapter-output.yaml`。
3. 短期生产分析能力以 rules fallback + guardrails 为事实源；multitrack 保留为过程推理与诊断辅助，不宣称真实 Agent 生产闭环。
4. taxonomy 先新增事实源并接入 validator，不在本轮批量重命名资产 metadata 字段。

### Objective

本轮交付的是一次架构合同收敛：

- 对使用者：`/midstack:analyse` 的主输出仍稳定可用，且不会再出现 Phase 4 多轨草稿和 rules fallback 同写 `analysis.yaml` 的歧义。
- 对维护者：README、architecture、implementation status、Phase 4 集成说明和架构检视 skill 能反映当前真实 runtime。
- 对贡献者：领域资产中 MongoDB 逻辑组件和排查面 taxonomy 有可校验边界。

### Tech Stack

- Python runtime：`src/commands/`、`src/phases/`、`src/shared/`
- YAML artifacts：incident 目录下的 `analysis.yaml`、`analysis.rules-fallback.yaml`、`analysis.multitrack.yaml`、`reasoning-board.yaml`
- Docs：Markdown + YAML front matter
- Validators/tests：`pytest`、`tools/validators/*`、`tools/replay/*`

### Commands

本轮最小门禁：

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

### Project Structure

```text
src/commands/analyse.py                 → analyse 编排，生产 analysis.yaml / report.md
src/phases/phase4/reasoning.py          → Phase 4 multitrack facade，只写 multitrack 辅助产物
src/phases/phase4/rules/                → 当前生产 analysis.yaml 的 rules fallback analyzer
docs/concepts/architecture.md           → 架构事实源说明
docs/project/implementation-status.md   → L3 实现进展
docs/project/phase4-multitrack-integration.md → Phase 4 当前集成说明
docs/analysis/                          → incident-specific 或实现诊断类分析记录
.cursor/skills/midstack-architecture-review/  → 架构检视治理资产
core/taxonomies/                        → 共用 taxonomy 事实源
tools/validators/                       → repo / asset / taxonomy 校验入口
```

### Code Style

新增运行时合同应保持显式文件名常量和薄函数封装，避免把产物名散落在多个调用点：

```python
MULTITRACK_ANALYSIS_FILENAME = "analysis.multitrack.yaml"


def write_multitrack_analysis(incident_dir: Path, analysis: Dict[str, Any]) -> None:
    analysis_path = incident_dir / MULTITRACK_ANALYSIS_FILENAME
    write_yaml_object(analysis_path, analysis, allow_unicode=True)
```

文档更新只描述当前事实和决策，不把未来能力写成已实现状态。

### Testing Strategy

| 层级 | 验证内容 | 入口 |
| --- | --- | --- |
| Unit / facade | Phase 4 不写生产 `analysis.yaml`，Unicode YAML 正常保留 | `tests/phases/phase4/test_reasoning_io.py` |
| CLI integration | `/midstack:analyse` 同时保留生产分析和 multitrack 辅助产物 | `tests/phases/phase4/multitrack/e2e/test_cli_integration.py`、`tests/tools/plugin/test_midstack_analyse.py` |
| Validator | docs/taxonomy/asset 合同不漂移 | `python3 tools/validators/validate-repo.py` |
| Replay / score | MongoDB MVP 诊断质量不退化 | `tools/replay/mongodb-replay.py`、`tools/replay/mongodb-score.py` |

### Boundaries

- Always：保持 `analysis.yaml` schema 和生产路径兼容；新增产物只能作为辅助引用；更新测试覆盖任何运行时合同变化。
- Ask first：真实 Agent 生产闭环、rules engine 下沉到 domains、字段批量改名、插件命令面变化。
- Never：把 multitrack mock 输出宣称为生产结论；删除 rules fallback；把 incident-specific 实现稿留在 L1 specs；隐式改变现有 adapter output 主 record ref。

## 状态记录

### 整改前 Phase 4 三机制

| 机制 | 当前位置 | 当前状态 | 问题 |
| --- | --- | --- | --- |
| rules fallback | `src/phases/phase4/rules/` | 实际生产 `analysis.yaml` 的主要来源 | 领域规则硬编码在 `src/`，文档未充分承认 |
| multitrack | `src/phases/phase4/multitrack/` | 框架和测试存在，默认 mock | 会先写 `analysis.yaml`，随后被 rules 覆盖 |
| agent task | `agent-reasoning-task.md` | 给 Agent/人工 refinement 的任务合同 | 当前不是自动生产最终 `analysis.yaml` 的闭环 |

### 整改后输出事实

`/midstack:analyse` 完成后：

- `analysis.yaml` 来自 rules fallback 和 guardrails。
- `analysis.rules-fallback.yaml` 保存 rules fallback 副本。
- `analysis.multitrack.yaml` 保存 multitrack renderer 产出的辅助诊断草稿。
- `reasoning-board.yaml` 保存 multitrack reasoning board。
- `agent-reasoning-task.md` 指导后续 Agent refinement。
- `report.md` 由当前 `analysis.yaml` 渲染。
- multitrack 不写生产 `analysis.yaml`。

## 决策建议

### D1. 短期将 rules fallback 定义为 `analysis.yaml` 唯一生产者

短期采用最小风险方案：

- `analysis.yaml` 的生产者是 rules fallback + guardrails。
- multitrack 不再写 `analysis.yaml`。
- multitrack 输出保留为独立诊断辅助产物：
  - `reasoning-board.yaml`
  - `analysis.multitrack.yaml`
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

迁移到 `docs/analysis/rs-status-collection-gap.md`。该文件更像一次 MongoDB sandbox incident 的实现诊断记录，而不是稳定 L1 规范或仍待评审的 proposal。

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

采用方案 A，但 taxonomy 命名为 `triage-surface-types.yaml`。原因是资产 metadata 当前字段仍叫 `component`，但语义实际上是排查面；taxonomy 名称必须先把概念说清楚，避免继续与 `domains/mongodb/metadata.yaml` 的逻辑组件混淆。

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
- `docs/analysis/rs-status-collection-gap.md` 的迁移位置或引用

### 治理资产

需要更新：

- `.cursor/skills/midstack-architecture-review/SKILL.md`
- `.cursor/skills/midstack-architecture-review/checklist.md`
- `.cursor/skills/midstack-architecture-review/report-template.md`（如引用旧结构）

### Taxonomy / Validator

可能涉及：

- `core/taxonomies/triage-surface-types.yaml`。
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

如果新增 triage surface taxonomy：

- 本轮接入 validator 校验现有资产 metadata 的 `component` 字段。
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

任务：

- [x] Task: Phase 4 multitrack 改写 `analysis.multitrack.yaml`
  - Acceptance: 直接调用 Phase 4 facade 不创建生产 `analysis.yaml`；`/midstack:analyse` 仍创建生产 `analysis.yaml`。
  - Verify: `python3 -m pytest tests/phases/phase4/test_reasoning_io.py tests/phases/phase4/multitrack/e2e/test_cli_integration.py -q`
  - Files: `src/phases/phase4/reasoning.py`、`tests/phases/phase4/test_reasoning_io.py`、`tests/phases/phase4/multitrack/e2e/test_cli_integration.py`
- [x] Task: adapter output 暴露 multitrack 辅助产物
  - Acceptance: `adapter-output.yaml.record_refs` 保留 `analysis`，并新增 `analysis_multitrack`。
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_analyse.py -q`
  - Files: `src/commands/analyse.py`、`tests/tools/plugin/test_midstack_analyse.py`

### Slice 2. 文档现实对齐

目标：

- README 和 implementation status 明确当前默认推理路径。
- architecture 补充 Phase 4 rules engine 的短期落点。
- phase4 multitrack 文档标注默认 mock 和非生产 `analysis.yaml` 生产者状态。

验收：

- 文档不再出现“默认真实 Claude API 推理编排已生效”的歧义表述。
- 新中间件落地说明包含 rules analyser 或明确 skeleton 状态。

任务：

- [x] Task: README / implementation status 写清当前默认推理路径
  - Acceptance: 文档明确 `analysis.yaml` 当前来自 rules fallback + guardrails，multitrack 是过程辅助产物。
  - Verify: `rg -n "rules fallback|analysis.multitrack|真实 Claude|默认" README.md docs/project/implementation-status.md`
  - Files: `README.md`、`docs/project/implementation-status.md`
- [x] Task: architecture / Phase 4 integration 写清 rules engine 落点
  - Acceptance: 新中间件接入说明不会只指向 `domains/`，而会说明生产 analyse 还需要 rules analyzer 或明确 skeleton。
  - Verify: `rg -n "src/phases/phase4/rules|analysis.multitrack|reasoning-board" docs/concepts/architecture.md docs/project/phase4-multitrack-integration.md`
  - Files: `docs/concepts/architecture.md`、`docs/project/phase4-multitrack-integration.md`

### Slice 3. 迁移 rs-status 实现稿

目标：

- 将 `docs/specs/rs-status-collection-gap.spec.md` 移到 `docs/analysis/rs-status-collection-gap.md`。
- 保留必要引用，避免断链。
- `docs/README.md` 的 specs 列表只包含稳定 L1 规范。

验收：

- `docs/specs/` 不再包含 incident-specific implementation note。
- 迁移文件 front matter 标为 `draft` 或 `archived`，不作为 L1 裁决依据。

任务：

- [x] Task: 将 rs-status 实现诊断迁到 `docs/analysis/`
  - Acceptance: `docs/specs/rs-status-collection-gap.spec.md` 删除，迁移文件有 front matter 且 status 不是 authoritative。
  - Verify: `rg -n "rs-status-collection-gap|rs.status Collection" docs`
  - Files: `docs/specs/rs-status-collection-gap.spec.md`、`docs/analysis/rs-status-collection-gap.md`、`docs/README.md`

### Slice 4. 更新架构检视 skill

目标：

- `.cursor/skills/midstack-architecture-review/` 对齐当前目录与双平面 runtime。
- checklist 增加 Phase 4 三机制、安装态 runtime、L1/L3 文档分层检查。

验收：

- skill 不再建议删除现行有效目录。
- skill 能识别 `src/execution` 与 `plugins/*/runtime` 的职责。

任务：

- [x] Task: 更新 architecture review skill 基准和 checklist
  - Acceptance: skill 将 `src/` 双平面、`plugins/*/runtime`、`tools/generators`、`tools/importers`、`domains/*/components` 标为现行有效路径。
  - Verify: `rg -n "src/execution|bundled runtime|workspace-local runtime|tools/generators|Phase 4" .cursor/skills/midstack-architecture-review`
  - Files: `.cursor/skills/midstack-architecture-review/SKILL.md`、`.cursor/skills/midstack-architecture-review/checklist.md`

### Slice 5. Component taxonomy

目标：

- 增加或明确一个 taxonomy，区分 MongoDB 逻辑组件与排查面。
- 更新 MongoDB metadata 注释或 validator 规则。

验收：

- `domains/mongodb/metadata.yaml` 的 `components` 与资产 metadata 的 `component` 不再被视为同一枚举。
- validator 至少能发现未知排查面字段值。

任务：

- [x] Task: 新增 triage surface taxonomy 并接入 MongoDB asset validator
  - Acceptance: runbook/command/skill metadata 的 `component` 通过 `core/taxonomies/triage-surface-types.yaml` 校验；MongoDB 逻辑组件仍留在 `domains/mongodb/metadata.yaml`。
  - Verify: `python3 -m pytest tests/tools -q` 或 `python3 tools/validators/validate-repo.py`
  - Files: `core/taxonomies/triage-surface-types.yaml`、`core/taxonomies/README.md`、`tools/validators/mongodb_assets/contracts.py`、`tools/validators/mongodb_assets/domain_assets.py`

### Slice 6. 历史经验召回字段预留

目标：

- 在 `analysis.yaml` 顶层预留未来历史经验/向量库召回字段。
- 当前不接入 embedding、向量库或真实召回服务。
- 明确历史经验只能作为假设来源或验证路径来源，不能作为当前故障结论的直接证据。

验收：

- MongoDB/Pulsar rules fallback 都输出 `retrieval_context`、`experience_matches` 和 `source_boundaries`。
- `analysis.multitrack.yaml` 辅助草稿也输出同一组顶层契约字段，但不替代生产 `analysis.yaml`。
- `agent-reasoning-task.md` 明确要求人工/Agent refinement 保留这些字段。
- `experience_matches` 当前保持空列表。
- 模板和 incident spec 明确 `source_boundaries` 的证据边界。

任务：

- [x] Task: rules fallback 输出经验召回预留契约
  - Acceptance: rules fallback 生成的 `analysis.yaml` 顶层包含召回上下文、空经验匹配和证据来源边界。
  - Verify: `python3 -m pytest tests/phases/phase4/rules -q`
  - Files: `src/phases/phase4/analysis_contract.py`、`src/phases/phase4/rules/mongodb.py`、`src/phases/phase4/rules/pulsar.py`、`tests/phases/phase4/rules/`
- [x] Task: multitrack 和 Agent task 对齐经验召回契约
  - Acceptance: `analysis.multitrack.yaml` 携带同一组顶层契约字段；`agent-reasoning-task.md` 要求 refinement 保留这些字段。
  - Verify: `python3 -m pytest tests/shared/test_agent_reasoning_task.py tests/phases/phase4/test_renderer.py -q`
  - Files: `src/phases/phase4/analysis_contract.py`、`src/phases/phase4/renderer.py`、`src/shared/analysis_runtime.py`、`tests/shared/test_agent_reasoning_task.py`、`tests/phases/phase4/test_renderer.py`
- [x] Task: 模板和规范记录历史经验边界
  - Acceptance: `analysis.template.yaml` 和 incident/workflow specs 说明历史经验不能直接进入当前结论证据。
  - Verify: `rg -n "retrieval_context|experience_matches|source_boundaries|历史经验" core/templates/analysis.template.yaml docs/specs`
  - Files: `core/templates/analysis.template.yaml`、`docs/specs/incident-record.spec.md`、`docs/specs/triage-workflow.spec.md`

### Slice 7. 受控验证请求契约

目标：

- Phase 4 可以在推理后提出需要补采或验证的证据请求。
- 当前只生成 `verification_requests`，不执行动态脚本或命令。
- 为后续动态验证预留一等资产、二等只读命令和禁止动作的治理边界。

验收：

- MongoDB/Pulsar rules fallback 输出顶层 `verification_requests`。
- MongoDB 在缺失 rs.status 或关键 previous logs 时请求仓库内只读脚本。
- Pulsar queue backlog 在缺失 broker topic stats 时请求仓库内只读脚本。
- 一等只读资产标记为 `asset_tier: first_class`、`risk_level: read-only`、`execution_policy: auto_allowed`、`status: planned`。
- 文档明确 `verification_requests` 是计划，不代表已经执行；临时只读命令需 guardrail，破坏性动作 blocked。

任务：

- [x] Task: rules fallback 生成验证请求
  - Acceptance: Phase 4 rules 根据明确证据缺口输出只读一等资产验证请求，但不执行请求。
  - Verify: `python3 -m pytest tests/phases/phase4/rules -q`
  - Files: `src/phases/phase4/verification_requests.py`、`src/phases/phase4/rules/mongodb.py`、`src/phases/phase4/rules/pulsar.py`、`tests/phases/phase4/rules/`
- [x] Task: 模板和规范记录验证请求边界
  - Acceptance: `analysis.template.yaml` 和 incident/workflow specs 说明一等资产、二等只读命令与 blocked 动作边界。
  - Verify: `rg -n "verification_requests|auto_allowed|ad_hoc_readonly|blocked" core/templates/analysis.template.yaml docs/specs`
  - Files: `core/templates/analysis.template.yaml`、`docs/specs/incident-record.spec.md`、`docs/specs/triage-workflow.spec.md`

### Slice 8. 推理时间线与报告可信度

目标：

- Phase 4 生成结构化 `reasoning_timeline`，把关键事件顺序带入 `analysis.yaml`。
- `report.md` 展示关键时间线，让读者能看到“什么时间发生了什么关键事项”。
- 时间线用于关联症状、采集动作和假设，但不单独证明因果。

验收：

- MongoDB/Pulsar rules fallback 和 multitrack draft 都输出顶层 `reasoning_timeline`。
- `reasoning_timeline.events` 从 `signal_bundle.timeline_summary`、异常信号、Kubernetes events 和采集动作聚合。
- `report.md` 包含 `## Timeline`，并限制展示条数避免报告被噪音撑爆。
- Agent task 和 specs 明确 refinement 必须保留时间线，未知时间不得伪造。

任务：

- [x] Task: rules fallback 输出结构化推理时间线
  - Acceptance: Phase 4 rules 输出 `reasoning_timeline.events` 和 `reasoning_timeline.findings`。
  - Verify: `python3 -m pytest tests/phases/phase4/rules/test_mongodb_rules.py tests/phases/phase4/rules/test_pulsar_rules.py -q`
  - Files: `src/phases/phase4/reasoning_timeline.py`、`src/phases/phase4/rules/mongodb.py`、`src/phases/phase4/rules/pulsar.py`
- [x] Task: report 和 Agent task 使用时间线
  - Acceptance: `report.md` 渲染关键时间线；Agent task 要求保留 `reasoning_timeline`。
  - Verify: `python3 -m pytest tests/shared/test_analysis_report.py tests/shared/test_agent_reasoning_task.py -q`
  - Files: `src/shared/analysis_runtime.py`、`tests/shared/`
- [x] Task: 模板和规范记录时间线边界
  - Acceptance: 模板和 specs 说明时间线字段、来源、报告用途和因果边界。
  - Verify: `rg -n "reasoning_timeline|Timeline|时间线" core/templates/analysis.template.yaml docs/specs`
  - Files: `core/templates/analysis.template.yaml`、`docs/specs/incident-record.spec.md`、`docs/specs/triage-workflow.spec.md`

### Slice 9. 机制深化与领域不变量检查

目标：

- Phase 4 不只停在现象或机制识别，还能从当前证据中提取“为什么能发生”的深化线索。
- 初始实现不硬编码单个故障案例，而是增加 MongoDB replica set 多视角不变量检查。
- 已采反证要进入结构化 finding，避免 Agent 重复建议已经被部分验证或反驳的路径。

验收：

- `analysis.yaml` 输出顶层 `deepening_findings`。
- MongoDB replica set 多视角 `config_version/config_term`、members 列表和 voting quorum 不一致会产生 high severity finding。
- 当前 MongoDB TCP/27017 probe 成功会反驳 `sustained_network_partition`，不再被隐藏在原始采集产物里。
- Agent task 和 specs 要求 refinement 使用 `deepening_findings` 推进 enabling/root cause。

任务：

- [x] Task: MongoDB replica set 不变量 deepening
  - Acceptance: Phase 4 rules 从 `structured_record.details.replica_members` 和 `network_overlay.pod_connectivity_checks` 输出机制深化 finding。
  - Verify: `python3 -m pytest tests/phases/phase4/rules/test_mongodb_rules.py -q`
  - Files: `src/phases/phase4/rules/mongodb_deepening.py`、`src/phases/phase4/rules/mongodb.py`、`tests/phases/phase4/rules/test_mongodb_rules.py`
- [x] Task: 模板和合同记录 deepening 字段
  - Acceptance: 模板、specs 和 Agent task 明确 deepening finding 的证据边界和用途。
  - Verify: `rg -n "deepening_findings|enabling/root cause|不变量" core/templates/analysis.template.yaml docs/specs src/shared/analysis_runtime.py`
  - Files: `core/templates/analysis.template.yaml`、`docs/specs/incident-record.spec.md`、`docs/specs/triage-workflow.spec.md`、`src/shared/analysis_runtime.py`

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

## 已决策事项

1. multitrack 独立产物标准文件名为 `analysis.multitrack.yaml`。
   原因：它与 `analysis.rules-fallback.yaml` 对称，且不会改变既有 `analysis.yaml` 消费者。
2. `rs-status-collection-gap.spec.md` 迁到 `docs/analysis/rs-status-collection-gap.md`。
   原因：内容是 MongoDB sandbox incident 的实现诊断记录，不是 L1 稳定规范。
3. 排查面 taxonomy 命名为 `triage-surface-types.yaml`。
   原因：现有资产字段名仍叫 `component`，但实际语义是排查面；taxonomy 名称先纠正概念边界。

## 后续问题

Phase 4 rules engine 中期是否要从 Python 硬编码迁为 domain asset，本提案不决策。建议另开 proposal 讨论 rules data model、domain asset schema 和 score gate 评价方式。

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

### A3. runtime root / workspace root 合同分裂

当前安装态 runtime 和工作区产物依赖两类根路径：

- `MIDSTACK_TRIAGE_RUNTIME_ROOT`：由 Claude/Cursor runtime wrapper 设置，用于 packaged runtime 内的 `src/`、`domains/`、`interfaces/`、`core/` 资产解析。
- `MIDSTACK_TRIAGE_WORKSPACE`：由 slash command 层设置，用于 incident 输出、`.local/incidents` 和当前工作区定位。

同时仍有若干模块直接以 `Path(__file__).resolve().parents[...]` 推导仓库或 runtime 根，例如：

- `src/execution/remote/runtime_support.py`
- `src/shared/workspace.py`
- `src/shared/scenario_router.py`
- `src/shared/skill_resolver.py`
- `src/phases/phase4/rules/<middleware>.py`

当前安装态能够工作，主要依赖 runtime bundle 目录结构与源码 checkout 结构一致；但接口上没有一个统一的 root contract。后续如果 runtime payload 继续裁剪、domain asset 索引下沉，或测试需要替换 runtime root，就容易出现 executor、scenario router、skill resolver 指向不同根目录的问题。

建议另开 P1 小提案，定义统一路径接口，例如：

- `runtime_root()`：packaged runtime / source checkout 中资产根。
- `workspace_root()`：用户工作区与 incident 输出根。
- `repo_root()` 或 `source_root()`：仅供仓库工程工具使用，不进入安装态 runtime contract。

落地时应让 `runtime_support`、`scenario_router`、`skill_resolver`、rules common 和插件 wrapper 共用同一套解析规则。

### A4. scenario / routing / domain assets 三方一致性

当前 `tools/validators/validate-scenario-routing.py` 主要运行单元测试，尚未验证以下三方合同：

1. `scenarios/<scenario>/scenario.yaml` 的 `applicable_middleware`。
2. `core/routing/scenario-signal-map.yaml` 的 scenario / middleware 路由声明。
3. `domains/<middleware>/` 下 runbook / skill / command / script 等资产是否存在对应 scenario。

`queue-backlog` 是当前可见样例：

`scenarios/queue-backlog/scenario.yaml` 当前包含：

- `pulsar`
- `mongodb`

但 routing map 只对 `pulsar` 声明 `queue-backlog` 路由，且当前 MongoDB 资产中没有对应 queue-backlog runbook/skill/command 链路。

单点修法是二选一：

- 从 `queue-backlog` 的 `applicable_middleware` 移除 `mongodb`；
- 或补齐 MongoDB backlog/data queue 语义下的对应资产，并明确与 `data-hotspot`、`latency-spike` 的边界。

更稳妥的架构修法是新增 validator：

- 每个 `scenario.yaml` 声明的 middleware，要么在 routing map 中有对应路由，要么明确标注为未路由 / skeleton。
- routing map 中出现的 scenario / middleware，必须能在 `scenarios/` 和 `domains/` 中找到对应声明或资产。
- domain asset metadata 中的 `scenario` / `primary_scenario` 不应指向不存在或未声明的 scenario。

该治理不应混入本提案的 Phase 4 输出收敛；建议作为独立治理 slice 或后续 proposal。

### A5. 领域资产 metadata version/status

部分 core templates 已包含 `status`，但 runbook/skill/command metadata 并未全仓统一 `version` / `status` 字段。该问题属于 metadata governance，不应在 Phase 4 推理核收敛中顺手改。

建议先选一个资产族试点：

- `domains/mongodb/skills/**/metadata.yaml`
- 或 `domains/mongodb/runbooks/**/metadata.yaml`

试点稳定后再推广到 schema、validator 和模板。

## 落地清单

- [x] 决策 `analysis.yaml` 唯一生产者。
- [x] 调整 Phase 4 multitrack 输出，不再覆盖生产 `analysis.yaml`。
- [x] 更新 README、architecture、implementation status 和 phase4 集成文档。
- [x] 迁移 `rs-status-collection-gap.spec.md`。
- [x] 更新 `.cursor/skills/midstack-architecture-review/`。
- [x] 新增或明确 component / triage surface taxonomy。
- [x] 预留历史经验召回字段并明确证据边界。
- [x] 补充对应测试或 validator。
- [x] 运行最小门禁和必要 replay/score gate。
