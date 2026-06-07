# 基准文档发现规则

检视前按变更范围加载基准，类似 code-review skill 按 PR 路径加载 `AGENTS.md`。

## 始终加载

| 文件 | 用途 |
|------|------|
| [README.md](../../../README.md) | 项目目标、MongoDB 首个样例 |
| [docs/architecture.md](../../../docs/architecture.md) | 三层结构、职责边界 |

## 按检视范围追加

| 变更涉及 | 追加加载 |
|----------|----------|
| `scenarios/` | `scenarios/*/scenario.yaml`，对照 `scenarios/replica-inconsistency/` |
| `domains/<mw>/` | 该 domain 的 `metadata.yaml`，对照 `domains/mongodb/` |
| runbook | [docs/runbook-spec.md](../../../docs/runbook-spec.md) + MongoDB 样例 runbook |
| skill | [docs/skill-spec.md](../../../docs/skill-spec.md) + MongoDB 样例 skill |
| command | [docs/command-spec.md](../../../docs/command-spec.md) + MongoDB 样例 command |
| `core/shared/` | [docs/architecture.md](../../../docs/architecture.md) 中 shared 准入条件 |
| `interfaces/` | `interfaces/` 下 README 与 plugin 约定 |
| PR / diff | 仅检视 diff 触及路径及其关联 metadata 引用链 |

## 样例链路（结构合规对照）

```text
scenarios/replica-inconsistency/scenario.yaml
domains/mongodb/runbooks/replica-set/replica-member-not-healthy/
domains/mongodb/skills/replica-set/triage-replica-member-not-healthy/
domains/mongodb/commands/replica-set/check-rs-status/
```

新 domain/scenario 检视时，先列一张「与 MongoDB 样例差异表」，再判断差异是否合理。
