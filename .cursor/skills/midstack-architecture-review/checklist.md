# Architecture Review Checklist

逐项检查，标记 `✅ 通过` / `⚠️ 风险` / `❌ 缺失`。细则冲突时以 [README.md](../../../README.md) 与 [docs/architecture.md](../../../docs/concepts/architecture.md) 为准。

**首个落地样例**：`domains/mongodb/` + `scenarios/replica-inconsistency/`。检视新 domain/scenario 时，先与这两条链路对齐，再评估是否可扩展。

---

## 1. 值班视角（On-call）

| 检查项 | 说明 |
|--------|------|
| 快速排除 | 是否有 5 分钟内可完成的 `fast_exclude` 或等价前置检查？ |
| 时间预算 | runbook/skill 是否标注 `phase`（triage/confirm/mitigate/recover）和预估时长？ |
| 风险可读 | 值班员能否一眼区分只读 vs 变更？`risk_level` 或 `mutation_risk` 是否明确？ |
| 交接产物 | 是否有 incident summary / evidence bundle 模板？ |
| 止血路径 | triage 与 mitigation 是否分离，避免一上来跑完整 40 步？ |

---

## 2. Agent 运行时视角

| 检查项 | 说明 |
|--------|------|
| 六步闭环 | 症状输入 → 场景匹配 → 中间件路由 → 只读检查 → 证据汇总 → 结论输出 是否可追溯？ |
| 路由入口 | `scenarios/` 或 catalog 是否提供 `symptoms`、`route_hints`、`applicable_middleware`？ |
| 编排非复制 | skill 是否通过 `required_assets` 引用 runbook/command，而非粘贴全文？ |
| 停止条件 | skill 是否定义输入、输出、停止/升级条件？ |
| 结论结构 | 是否有 finding / evidence 模型或等价字段（severity、confidence、implies、excludes）？ |
| 执行策略 | 是否有统一的只读/审批策略（`safety_constraints`、`core/policies/` 或 spec 约定）？ |
| Phase 4 产物合同 | `analysis.yaml`、`analysis.rules-fallback.yaml`、`analysis.multitrack.yaml`、`reasoning-board.yaml` 的生产者是否清楚？ |
| 安装态 runtime | Claude bundled runtime 与 Cursor workspace-local runtime 是否都能找到所需 `src/`、`domains/`、`core/`、`interfaces/` 资产？ |

---

## 3. 图谱模型视角

| 检查项 | 说明 |
|--------|------|
| 稳定 ID | 每个资产是否有全局唯一 `id`，且不随目录移动而变？ |
| 跨引用 | scenario、runbook、skill、command 是否通过 ID 互引，而非仅靠路径猜测？ |
| 目录是视图 | 多对多关系（一现象多中间件、一 runbook 多 command）是否用 metadata 表达？ |
| 索引层 | 是否存在 `core/catalog/` 或等效路由索引？若无，是否说明检索方案？ |
| 版本 | schema 与资产是否有 `version` / `status`（draft/reviewed/deprecated）？ |

---

## 4. 重复风险视角

| 检查项 | 说明 |
|--------|------|
| scenarios 厚度 | 顶层 scenario 是否只有定义+路由，无产品命令/脚本？ |
| runbook 唯一 | 同一排查流程是否只存一份 runbook？ |
| 双入口 | 按组件/按场景是否通过 metadata（`component` + `scenario`）实现，而非物理双目录？ |
| command vs script | 单条命令在 `commands/`，有控制流在 `scripts/`，边界是否清晰？ |
| 标签 vs 主场景 | 多相关症状用 tags，不复制第二份 runbook？ |

---

## 5. PaaS 约束视角

| 检查项 | 说明 |
|--------|------|
| 部署模式 | 是否区分 managed / self-hosted / operator？ |
| 权限 | 是否声明 `permissions_required` 或 `audience`（tenant / platform-sre）？ |
| 观测抽象 | 检查项是否表达「意图」（如 lag trend），而非绑定单一 PromQL？ |
| 环境适用 | `applicable_env` 是否覆盖目标 PaaS 环境？ |
| 默认只读 | Agent 默认是否只能执行 read-only 资产？ |

---

## 6. 命名纪律视角

| 检查项 | 说明 |
|--------|------|
| slug 风格 | 目录、ID、taxonomy 是否统一 kebab-case？ |
| 枚举一致 | `scenario` 字段、`scenarios/` 目录名、`core/taxonomies/` 是否同一词表？ |
| ID 规范 | 是否遵循 `<domain>.<type>.<name>` 或项目约定？ |
| 排查面命名 | runbook/skill/command metadata 的 `component` 是否与 `core/taxonomies/triage-surface-types.yaml` 对齐？ |
| 逻辑组件边界 | `domains/<mw>/metadata.yaml` 中的 `components` 是否只表达产品逻辑组件，不与资产排查面混用？ |
| 文档分层 | incident-specific 实现诊断是否放在 `docs/analysis/` 或 proposals，而不是 L1 `docs/specs/`？ |

---

## 7. 反模式扫描

对检视对象逐条核对 [SKILL.md](SKILL.md) 中的七条反模式。

---

## 8. MVP 范围视角

| 检查项 | 说明 |
|--------|------|
| 单链路 | 是否能裁剪到 1 个 scenario + 1 个 domain + 1 条 golden path？（参照 MongoDB `replica-inconsistency` 链路） |
| MongoDB 对齐 | 新 domain 的结构与 `domains/mongodb/` 是否一致，而非另起一套？ |
| 目录克制 | 是否延后未落地的 categories / 多插件物理目录，并避免把 `tools/generators`、`tools/importers` 误判为 runtime？ |
| shared 准入 | `core/shared/` 新内容是否满足：2+ domain 复用、无产品语义、无专属工具？ |
| 验证器 | `tools/validators/` 或 CI 是否计划校验 schema 与目录？ |
| 接口解耦 | 知识是否在 `domains/`，`interfaces/` 仅放适配协议？ |

---

## 保留 / 延后 / 砍掉 参考表

检视目录或概念时，可参考：

| 概念 | 默认判断 |
|------|----------|
| `core/models/`, `core/taxonomies/`, `core/templates/` | 保留 |
| `core/catalog/` | 保留（路由索引） |
| `core/shared/` | 保留但严控 |
| `domains/` | 保留 |
| `domains/*/components/` | 保留（当前作为资产排查面索引；不要与 `domains/<mw>/metadata.yaml.components` 逻辑组件混用） |
| `scenarios/` 顶层 | 保留但做薄 |
| `interfaces/` | 保留 |
| `tools/validators/` | 保留 |
| `tests/golden-paths/` | 保留 |
| `tools/generators/`, `tools/importers/` | 保留（现行工程辅助路径；评审是否越界进入 runtime） |
| `categories/` 物理目录 | 延后（第二个同类产品再建） |
| 插件内第二份 runbook/skill | 砍掉 |
