---
status: draft
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# 2026-06-16 质量债治理实施计划

## 目标

按 [spec.md](spec.md) 的边界完成第一轮质量债治理：默认 validator 修绿，fixture 生命周期分层落地，公开 fixture 敏感信息扫描增强，并保留 README/license 既有通过状态。

## 实施顺序

### 1. Fixture 路径分层

目标：

- 建立 `tests/fixtures/active/` 和 `tests/fixtures/legacy/`。
- 将当前默认回放样本迁入 active。
- 工具默认只扫描 active fixture。

主要改动：

- 移动当前 `tests/fixtures/mongodb/*` 到 `tests/fixtures/active/mongodb/*`。
- 移动当前 `tests/fixtures/pulsar/*` 到 `tests/fixtures/active/pulsar/*`。
- 更新 `tools/replay/mongodb/replay.py` 默认 `--fixture-root`。
- 更新 `tools/replay/mongodb/score.py` 默认 `--fixture-root`。
- 更新 Pulsar replay 默认路径。
- 更新引用 fixture 路径的测试。

验证：

```bash
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

风险：

- 直接移动路径会影响测试引用。用 `rg "tests/fixtures"` 做完整引用检查。

### 2. 修复 readiness active fixture

目标：

- `kubernetes-readiness-failure-sample` 继续作为 active fixture。
- fixture 的结构化证据和 expected analysis 一致。

主要改动：

- 在 `signal_bundle.yaml` 增加最小 `pod-not-ready` abnormal signal。
- 如需要，在 `structured_record.yaml` 增加合成 Kubernetes `Unhealthy` event。
- 避免只凭 `customer_clue` 提高置信度。
- 将 `collection_report.yaml` 从只有 remote executor failed 的历史状态修正为适合 active replay 的最小成功/expected gap 状态，或保留 critical gap 但相应降低 expected confidence。

验证：

```bash
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

风险：

- 过度补 fixture 会制造不真实证据。只补能支撑 `pod-not-ready` 的最小信号。

### 3. Raw/private/sensitive ignore 规则

目标：

- 未脱敏现场样本和本地冻结候选默认不进入 git。

主要改动：

- 更新 `.gitignore`：
  - `.local/fixtures/`
  - `tests/fixtures/**/raw/`
  - `tests/fixtures/**/private/`
  - `tests/fixtures/**/sensitive/`
  - `tests/golden-paths/fixtures/**/raw/`
  - `tests/golden-paths/fixtures/**/private/`
  - `tests/golden-paths/fixtures/**/sensitive/`

验证：

```bash
git check-ignore -v tests/fixtures/active/mongodb/example/raw/file.yaml
git check-ignore -v tests/golden-paths/fixtures/private/file.yaml
```

风险：

- 不要 ignore `tests/fixtures/active/**` 本身，否则公开 fixture 无法入库。

### 4. Fixture hygiene 增强

目标：

- 明确阻断真实敏感信息。
- 将 `tests/golden-paths/fixtures/` 纳入扫描。
- 对公网 IP、内网 IP 做分级处理。

主要改动：

- 更新现有 fixture hygiene validator。
- 扫描范围包括：
  - `tests/fixtures/active/`
  - `tests/fixtures/legacy/`
  - `tests/golden-paths/fixtures/`
- 规则：
  - 私钥、token、明显真实密码：error
  - remote-config、adapter-output、remote executor 生成物出现在可入库 fixture：error
  - 公网 IP：error，文档保留地址除外
  - 内网 IP：warning 或需要 allowlist/reason；第一轮可先输出 warning，不阻断
  - `test-user`、`example-password`、`10.0.0.1` 等测试假值允许

验证：

```bash
python3 tools/validators/validate-repo.py
python3 -m pytest tests/tools/validators -q
```

风险：

- 一次性将内网 IP 设为 error 可能误伤 Kubernetes 合成证据。第一轮先 warning，后续再收紧。

### 5. 文档与状态同步

目标：

- 让文档反映新 fixture 生命周期。
- 把完成项从 TODO 迁移或标记到实现状态。

主要改动：

- 更新 `tests/fixtures/README.md`。
- 更新 `tests/golden-paths/README.md` 中的敏感信息边界。
- 更新 `docs/project/todo.md`：保留未完成项，标记本轮已处理内容。
- 更新 `docs/project/implementation-status.md`：记录 fixture 分层和 hygiene gate 已落地。

验证：

```bash
git diff --check
```

## 依赖关系

1. 先做路径分层，再改 replay/score 默认路径。
2. 修复 readiness fixture 后，才能要求 MongoDB replay/score 默认通过。
3. ignore 规则可独立完成。
4. hygiene 增强依赖最终目录结构，否则扫描路径会反复调整。
5. 文档和状态同步最后做，避免描述中途状态。

## 验收命令

最终验收：

```bash
python3 tools/validators/validate-repo.py
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
python3 -m pytest tests/plugins/claude/test_claude_plugin_install.py tests/plugins/cursor/test_cursor_plugin_install.py -q
git diff --check
```

## 不在本轮处理

- analyse 根因判断质量优化。
- 接入真实 Claude API 推理编排。
- Pulsar/Redis/Elasticsearch/Kafka 正式支持。
- Cursor bundled runtime 独立分发。
- 严格 schema 全面替换轻量合同模型。
