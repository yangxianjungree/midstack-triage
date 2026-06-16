---
status: draft
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# 2026-06-16 质量债治理任务拆解

## Task 1: 建立 fixture active/legacy 目录

- Acceptance:
  - 当前 MongoDB replay fixture 位于 `tests/fixtures/active/mongodb/`。
  - 当前 Pulsar replay fixture 位于 `tests/fixtures/active/pulsar/`。
  - `tests/fixtures/legacy/` 目录存在，用于后续归档历史样本。
  - 原 `tests/fixtures/mongodb/` 和 `tests/fixtures/pulsar/` 不再作为默认 fixture 根目录。
- Verify:
  - `find tests/fixtures -maxdepth 3 -type d | sort`
  - `rg -n "tests/fixtures/(mongodb|pulsar)" tests tools src docs -g '!docs/proposals/2026-06-16-quality-debt-hardening/*.md'`
- Files:
  - `tests/fixtures/`

## Task 2: 更新 replay/score 默认 fixture root

- Acceptance:
  - MongoDB replay 默认读取 `tests/fixtures/active/mongodb`。
  - MongoDB score 默认读取 `tests/fixtures/active/mongodb`。
  - Pulsar replay 默认读取 `tests/fixtures/active/pulsar`。
  - 显式 `--fixture-root` 仍可覆盖默认路径。
- Verify:
  - `python3 tools/replay/mongodb-replay.py --run-analyse`
  - `python3 tools/replay/mongodb-score.py --run-analyse --min-level medium`
  - `python3 tools/replay/pulsar-replay.py --run-analyse`
- Files:
  - `tools/replay/mongodb/replay.py`
  - `tools/replay/mongodb/score.py`
  - `tools/replay/pulsar/replay.py`
  - wrapper 脚本如存在默认路径说明

## Task 3: 修复 readiness active fixture 证据链

- Acceptance:
  - `kubernetes-readiness-failure-sample` 仍在 active。
  - `signal_bundle.yaml` 包含能触发 `kubernetes-runtime` 的最小 `pod-not-ready` 异常信号。
  - 如补 `structured_record.yaml`，只补合成且脱敏的 `Unhealthy` / readiness probe evidence。
  - `expected_analysis.yaml` 与实际规则输出一致，且不是只依赖 `customer_clue`。
- Verify:
  - `python3 tools/replay/mongodb-replay.py --run-analyse`
  - `python3 tools/replay/mongodb-score.py --run-analyse --min-level medium`
  - `sed -n '1,120p' .local/replay/kubernetes-readiness-failure-sample.analysis.yaml`
- Files:
  - `tests/fixtures/active/mongodb/kubernetes-readiness-failure-sample/signal_bundle.yaml`
  - `tests/fixtures/active/mongodb/kubernetes-readiness-failure-sample/structured_record.yaml`
  - `tests/fixtures/active/mongodb/kubernetes-readiness-failure-sample/collection_report.yaml`
  - `tests/fixtures/active/mongodb/kubernetes-readiness-failure-sample/expected_analysis.yaml`

## Task 4: 补 raw/private/sensitive ignore 规则

- Acceptance:
  - `.local/fixtures/` 被 ignore。
  - `tests/fixtures/**/raw/`、`private/`、`sensitive/` 被 ignore。
  - `tests/golden-paths/fixtures/**/raw/`、`private/`、`sensitive/` 被 ignore。
  - active fixture 正常文件不被 ignore。
- Verify:
  - `git check-ignore -v .local/fixtures/example.yaml`
  - `git check-ignore -v tests/fixtures/active/mongodb/example/raw/file.yaml`
  - `git check-ignore -v tests/golden-paths/fixtures/private/file.yaml`
  - `test -z "$(git check-ignore tests/fixtures/active/mongodb/baseline-sharded-cluster/input.yaml || true)"`
- Files:
  - `.gitignore`

## Task 5: 增强 fixture hygiene validator

- Acceptance:
  - 扫描范围包括 `tests/fixtures/active/`、`tests/fixtures/legacy/`、`tests/golden-paths/fixtures/`。
  - 私钥、token、疑似真实密码、未脱敏 remote config 和生成物作为 error。
  - 公网 IP 作为 error，RFC 文档保留地址除外。
  - 内网 IP 第一轮不阻断，但输出 warning 或结构化说明。
  - `test-user`、`example-password`、`10.0.0.1` 等测试假值允许。
- Verify:
  - `python3 tools/validators/validate-repo.py`
  - `python3 -m pytest tests/tools/validators -q`
- Files:
  - `tools/validators/validate-fixture-hygiene.py` 或现有 fixture hygiene validator
  - `tools/validators/validate-repo.py`
  - `tests/tools/validators/test_validate_fixture_hygiene.py`

## Task 6: 更新 fixture 文档

- Acceptance:
  - `tests/fixtures/README.md` 说明 active、legacy、raw/private/sensitive 的职责。
  - README 说明新 fixture 准入：最小证据链、脱敏、hygiene 通过、expected 与 actual 对齐。
  - `tests/golden-paths/README.md` 说明其 fixtures 也受 hygiene 扫描约束。
- Verify:
  - `git diff --check -- tests/fixtures/README.md tests/golden-paths/README.md`
- Files:
  - `tests/fixtures/README.md`
  - `tests/golden-paths/README.md`

## Task 7: 更新项目状态文档

- Acceptance:
  - `docs/project/implementation-status.md` 记录 fixture 分层与 hygiene gate 已落地。
  - `docs/project/todo.md` 保留未完成的后续增强，不再把本轮已完成项当作未完成。
  - 日期更新到实际变更日。
- Verify:
  - `git diff --check -- docs/project/implementation-status.md docs/project/todo.md`
- Files:
  - `docs/project/implementation-status.md`
  - `docs/project/todo.md`

## Task 8: 最终回归与提交前检查

- Acceptance:
  - 默认质量门禁通过。
  - MongoDB replay/score 默认通过。
  - 插件协议和安装器相关测试保持通过。
  - 工作区只包含本轮质量债治理相关变更。
- Verify:
  - `python3 tools/validators/validate-repo.py`
  - `python3 tools/replay/mongodb-replay.py --run-analyse`
  - `python3 tools/replay/mongodb-score.py --run-analyse --min-level medium`
  - `python3 -m pytest tests/plugins/claude/test_claude_plugin_install.py tests/plugins/cursor/test_cursor_plugin_install.py -q`
  - `git diff --check`
  - `git status -sb`
- Files:
  - no implementation files beyond previous tasks
