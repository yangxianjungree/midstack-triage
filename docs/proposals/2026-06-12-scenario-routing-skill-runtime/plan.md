---
status: draft
last_updated: 2026-06-12
supersedes: none
superseded_by: none
---

# Scenario 路由 + Skill 混合运行时 + Pulsar 样例 — 实施计划

本计划承接架构检视结论与用户确认的三项决策：

1. **Scenario 路由**：从 `signal_bundle` 自动推断（非用户手选为主路径）
2. **Skill 运行时地位**：**选项 C 混合模式** — MVP 全量采集不变；scenario 匹配后由 skill 驱动定向补采白名单与 Agent 任务注入
3. **第二 domain**：Pulsar，先打穿一条 golden path

本文件是过程性执行计划，不替代 L1。字段与流程合同仍以 `docs/specs/`、`core/models/`、`core/templates/`、`core/taxonomies/` 为准。

## 目标与成功标准

### 目标

- 在 Phase 3 结束后、定向补采与 Phase 4 之前，自动推断 `scenario` 及候选列表
- 定向补采白名单从「Python 硬编码」迁移为「skill `required_assets` ∩ manifest 只读 catalog」，保留现有门禁
- `agent-reasoning-task.md` 注入 matched skill/runbook 路径与 stop conditions
- 为 Pulsar 建立与 MongoDB 同等的「一条 golden path」扩展模板

### 成功标准（MongoDB）

- [ ] `tests/fixtures/mongodb/*` 中已覆盖场景，`scenario_inference.confidence` 为 high/medium 的比例 ≥ 90%
- [ ] `unknown` 仅出现在故意模糊的 baseline fixture
- [ ] 推断后 `knowledge_candidates` 非空（当 confidence ≥ medium）
- [ ] directed recollection 所选 script 均来自 matched skill 的 `required_assets`（或文档列明的全局 fallback 表，见下文）
- [ ] `agent-reasoning-task.md` 含 `Matched Assets` 段：skill、runbook、scenario 路径
- [ ] 现有 remote smoke、fixture replay、review smoke 无回归
- [ ] 修复 `mongodb-check-pod-resource-pressure` 的 `scenario` 与 `kubernetes-runtime` skill 不一致问题

### 成功标准（Pulsar）

- [ ] `scenarios/queue-backlog` 的 `applicable_middleware` 含 `pulsar`
- [ ] `domains/pulsar/` 具备 runbook + skill + command + manifest + 至少 2 个 collect 脚本
- [ ] `tests/golden-paths/pulsar-analyse-minimal.yaml` 通过 validator
- [ ] fixture 可离线跑通 analyse 草稿 + review（不要求 remote smoke 第一版即就绪）

## 非目标（本轮不做）

- 用 ML/embedding 做 scenario 分类
- 砍掉 MVP 11 脚本改为 skill 按需全量采集
- 用户侧新增 slash 命令或 analyse 多轮循环
- Pulsar 远程 executor 与真实集群 smoke（可放在 Phase 4 后）
- 将 `deepest_supported_level`、gap 类型立即升级为 L1 taxonomy（仍用 soft field）

## 架构快照

```text
MVP collect (11 scripts, 不变)
    → normalize → signal_bundle.yaml
    → scenario_router.infer(signal_bundle, structured_record, customer_clue, middleware)
    → 写 input.yaml.scenario + scenario_inference
    → resolve_skills(scenario, middleware) → matched skill(s)
    → directed_recollection:
         candidates = skill.required_assets(type=script)
         ∩ manifest.readonly
         ∩ gap_triggers (现有 should_run_* 逻辑)
         cap = 3
    → write_agent_reasoning_task(+ matched assets)
    → analysis.rule-draft.yaml
    → Agent Phase 4/5 + finalize
```

## 组件与依赖

| 组件 | 职责 | 依赖 |
|------|------|------|
| `core/routing/scenario-signal-map.yaml` | 信号 → scenario 规则表 | `scenario-types` taxonomy |
| `tools/lib/scenario_router.py` | 推断引擎 | signal map、signal_bundle schema |
| `tools/lib/skill_resolver.py` | scenario → skill metadata 解析 | domains metadata |
| `tools/lib/directed_recollection.py` | 从 skill 解析补采白名单 | manifest、gap triggers |
| `tools/plugin/midstack-local.py` | 编排调用点 | 上述 lib |
| `docs/specs/scenario-routing.spec.md` | L1 路由合同（实施后升级） | — |
| `docs/specs/skill.spec.md` | 补充运行时消费语义 | — |

## 实施顺序

### Phase A：规范与数据修复（可并行，1 个会话）

**A1. 修 metadata 不一致**

- 文件：`domains/mongodb/commands/kubernetes-runtime/check-pod-resource-pressure/metadata.yaml`
- 改动：`scenario: kubernetes-runtime`（与 skill `primary_scenario` 对齐）
- 验收：`validate-mongodb-scripts.py` 通过；`knowledge_candidates_for_scenario("kubernetes-runtime")` 含该 command

**A2. 起草 `scenario-routing.spec.md`（草案）**

- 定义：`scenario_inference` 字段、confidence 枚举、多候选、`unresolved` 语义
- 定义：`customer_clue` 仅 tie-break，不作证据级路由
- 定义：与 `input.yaml` / `meta.yaml` 的写入位置

**A3. 更新 `skill.spec.md`**

- 明确选项 C：MVP 全量采集不变；`required_assets` 驱动定向补采与证据完备性检查；`skill.md` 供 Agent Phase 4

**A4. 创建 `core/routing/scenario-signal-map.yaml`**

- MongoDB 六场景 + `kubernetes-runtime` 的初始规则
- 引用已有 `signal_id`（`normalize-signals-bundle.py`、`kubernetes-runtime-signal-types.yaml`）
- 为 replica 场景补充 normalize 侧稳定 `signal_id`（若缺失）

### Phase B：Scenario 路由引擎（依赖 A4）

**B1. `tools/lib/scenario_router.py`**

- 输入：`signal_bundle`、`structured_record`（可选）、`customer_clue`（tie-break）、`middleware`
- 输出：`scenario`、`scenario_inference`（candidates、confidence、matched_signals、unresolved）
- 算法：规则表加权评分，top1 为 primary；top2 分差 < 阈值 → `unresolved: true`

**B2. 接入 `midstack-local.py` analyse 路径**

- 调用点：`normalize` 完成之后、`directed_recollection` 之前
- 写回：`input.yaml` 的 `scenario` 与 `scenario_inference`；`meta.yaml` 可选镜像
- 日志：在 `collection_report` 或新块 `routing_report` 记录推断依据（soft field，先不写 L1）

**B3. 单测 + fixture 断言**

- 新文件：`tests/unit/test_scenario_router.py` 或扩展现有 validator
- 覆盖 fixture：
  - `kubernetes-crashloop-sample` → `kubernetes-runtime`
  - `replica-inconsistency-sample` → `replica-inconsistency`
  - `connection-failure-sample` → `connection-failure`
  - `kubernetes-flannel-overlay-partition-root-cause` → `kubernetes-runtime`（高置信）+ 次选若适用

### Phase C：Skill 混合运行时（依赖 B）

**C1. `tools/lib/skill_resolver.py`**

- `resolve_skills(middleware, scenario)` → 按 `primary_scenario` 匹配 skill metadata 列表
- `extract_script_ids(skill_metadata)` → `required_assets` 中 `type: script` 的 id 列表
- `resolve_asset_paths(type, id)` → 仓库内路径（复用 validator 索引逻辑）

**C2. 重构 directed recollection**

- 将 `directed_recollection_script_ids()` 改为：
  1. 取 matched skill(s) 的 script `required_assets`
  2. ∩ `manifest.yaml` 中 `readonly: true`
  3. 再应用现有 `should_run_*` gap 触发器
  4. `DIRECTED_RECOLLECTION_CAP = 3` 不变
- **迁移表**（硬编码 → skill）：

| 现有硬编码 script | 迁入 skill |
|-------------------|------------|
| `mongodb.collect.dns.coredns` | `triage-kubernetes-runtime-failure` |
| `mongodb.collect.network.overlay` | 同上 |
| `mongodb.collect.logs.discover_sink` | `triage-kubernetes-runtime-failure` + `triage-replica-member-not-healthy`（按 scenario 选 skill） |
| `mongodb.collect.logs.file_tail` | 同上 |
| `mongodb.collect.logs.node_file_tail` | 同上 |
| `mongodb.collect.pods.describe` | `triage-kubernetes-runtime-failure` |

- 各 skill `metadata.yaml` 补全缺失的 `required_assets` script 引用
- 保留极薄 fallback：若无 matched skill，回退当前硬编码（仅日志告警，便于发现资产缺口）

**C3. 证据完备性检查（轻量）**

- 在 `agent-reasoning-task` 或 `collection_report` 增加：
  - `skill_required_scripts`: 列表
  - `missing_or_failed`: MVP 或补采后仍失败/未跑的 required script
- 不阻塞 analyse；供 Agent 与 review 引用

**C4. 增强 `write_agent_reasoning_task()`**

- 新增 `## Matched Assets`：
  - scenario id + inference summary
  - skill path + `skill.md` 摘要（inputs/outputs/stop conditions）
  - runbook path（来自 skill `required_assets`）
- 新增 `## Skill Workflow`：摘录 `skill.md` 的 Workflow 节（≤30 行）

### Phase D：验证与 golden path 扩展（依赖 B、C）

**D1. 扩展 golden paths**

- 每个 MongoDB scenario 至少 1 个 fixture 路由断言（可并入 `validate-golden-paths.py` 或新 `validate-scenario-routing.py`）
- 优先：`kubernetes-runtime`、`replica-inconsistency`

**D2. Replay / score 回归**

- `mongodb-replay.py --run-analyse` 全 fixture 通过
- score gate `min-level medium` 不下降

**D3. Cursor MCP smoke**

- 更新 `test-mcp-server.py` / sandbox 若断言 scenario 字段

### Phase E：Pulsar 最小 golden path（可与 B 后期并行）

**E1. 场景层**

- 更新 `scenarios/queue-backlog/scenario.yaml`：`applicable_middleware` 增加 `pulsar`
- 补充 Pulsar 典型 symptoms（backlog、consumer lag、broker unavailable）

**E2. 领域资产（最小集）**

```text
domains/pulsar/
  runbooks/broker/topic-backlog/
  skills/broker/triage-topic-backlog/
  commands/broker/check-topic-backlog/
  scripts/manifest.yaml
  scripts/collect/collect-broker-stats.sh      # 占位/契约级
  scripts/collect/collect-topic-stats.sh
  scripts/normalize/normalize-signals-bundle.py  # 可先薄包装复用模式
```

**E3. 路由规则**

- `core/routing/scenario-signal-map.yaml` 增加 pulsar 段（如 `topic-backlog-high` → `queue-backlog`）
- `tools/lib/scenario_router.py` 支持 `middleware` 过滤规则

**E4. Analyse 骨架**

- `tools/analyse/pulsar-analyse.py`：复用 hypothesis/gap/knowledge_candidates 模式
- `midstack-local.py` / MCP：`middleware=pulsar` 时分派（第一版可仅 fixture 路径）

**E5. 测试**

- `tests/fixtures/pulsar/topic-backlog-sample/`
- `tests/golden-paths/pulsar-analyse-minimal.yaml`

## 任务清单（含验收）

### Phase A

- [ ] **Task A1**：修复 kubernetes-runtime command scenario 字段  
  - 验收：validator 通过；knowledge_candidates 含该 command  
  - 文件：1 个 metadata.yaml

- [ ] **Task A2**：`docs/specs/scenario-routing.spec.md` 草案  
  - 验收：涵盖 inference 字段、confidence、多候选、clue tie-break  
  - 文件：新 spec

- [ ] **Task A3**：更新 `docs/specs/skill.spec.md` 运行时语义  
  - 验收：明确选项 C 三分工（MVP / 补采 / Agent）  
  - 文件：skill.spec.md

- [ ] **Task A4**：`core/routing/scenario-signal-map.yaml`  
  - 验收：覆盖 MongoDB 6 scenario + 文档注释；validator 可加载  
  - 文件：新 routing 配置

### Phase B

- [ ] **Task B1**：实现 `scenario_router.py` + 单测  
  - 验收：上述 fixture 断言全绿  
  - 文件：tools/lib、tests/unit

- [ ] **Task B2**：接入 midstack-local analyse  
  - 验收：analyse fixture 后 `input.yaml` 含 `scenario_inference`  
  - 文件：midstack-local.py

### Phase C

- [ ] **Task C1**：`skill_resolver.py`  
  - 验收：replica-inconsistency → `mongodb-triage-replica-member-not-healthy`  
  - 文件：tools/lib

- [ ] **Task C2**：定向补采改 skill 驱动 + 更新 6 个 skill metadata  
  - 验收：补采 script 均 ∈ skill.required_assets；cap 仍为 3  
  - 文件：midstack-local.py、domains/mongodb/skills/**/metadata.yaml

- [ ] **Task C3**：证据完备性 soft 字段  
  - 验收：collection_report 或 task 中可见 missing required scripts  
  - 文件：midstack-local.py

- [ ] **Task C4**：`agent-reasoning-task.md` 注入 Matched Assets  
  - 验收：生成的 task 含 skill/runbook 路径与 workflow 摘录  
  - 文件：midstack-local.py

### Phase D

- [ ] **Task D1**：路由 golden path / validator  
  - 验收：`validate-repo.py` 含路由检查  
  - 文件：tools/validators、tests/golden-paths

- [ ] **Task D2**：replay + score 回归  
  - 验收：现有 score gate 通过  
  - 命令：`mongodb-replay.py`、`mongodb-score.py`

### Phase E

- [ ] **Task E1–E5**：Pulsar 最小 golden path  
  - 验收：`pulsar-analyse-minimal.yaml` 通过；fixture 可离线 analyse  
  - 文件：domains/pulsar、scenarios、tests

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| normalize 缺少 MongoDB 专属 signal_id，路由不准 | Phase A4 补 signal；优先用已有 K8s taxonomy |
| 多 scenario 同分 | `unresolved` + Agent 多假设；不强行单 scenario |
| skill 未声明补采 script，回归漏采 | fallback 硬编码 + validator 检查「已知 playbook script 必须在某 skill required_assets」 |
| Pulsar 范围膨胀 | 严格限制 E 阶段仅 queue-backlog 一条路径 |
| L1 字段升级滞后 | 先用 soft field；D 阶段后评估升 template/taxonomy |

## 建议实施节奏

```text
Week 1:  Phase A + B（路由可推断、可测试）
Week 2:  Phase C + D（skill 混合运行时、MongoDB 回归）
Week 3:  Phase E（Pulsar 契约级 golden path，executor 可后续）
```

每一 Phase 结束运行：

```bash
python3 tools/validators/validate-repo.py
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
python3 plugins/cursor/test-mcp-server.py
```

## 待人类评审项

- [ ] `scenario_inference` 写入 `input.yaml` 是否可接受（vs 独立 `routing.yaml`）
- [ ] 多 skill 同 scenario 时取全部还是 top1（建议：primary scenario 匹配的全部 readonly skill 合并 script 集）
- [ ] Pulsar 首场景用 `queue-backlog` 还是新建 `broker-unavailable`
- [ ] 硬编码 fallback 保留多久（建议：至 6 个 MongoDB skill 的 required_assets 补全后删除）
