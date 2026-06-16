---
status: draft
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# 2026-06-16 质量债治理规格

## Assumptions

1. 本轮目标是先让仓库质量门禁、fixture 生命周期和开源前安全边界稳定下来，不直接解决 analyse 排障效果不够稳的问题。
2. `README.md`、`LICENSE`、`NOTICE` 已作为门面与开源协议基线，本轮只在发现事实错误时做小修，不再重写门面内容。
3. `tests/fixtures/` 仍然需要入库，但只保留脱敏、可公开、可回归的 active fixture；未脱敏现场样本不得入库。
4. 默认质量门禁必须可复现、可解释；历史样本可以保留，但不能阻断默认 `validate-repo.py`。
5. 本轮不引入新外部依赖，不改真实远程采集协议，不改变三条用户 slash 命令。

## Objective

将当前已识别的 P0/P1 技术债收敛成一轮可验证的质量治理：

- 修复当前 `validate-repo.py` 失败的 MongoDB replay/score gate。
- 建立 fixture 生命周期分层，避免历史样本、未脱敏样本和 active gate 样本混在一起。
- 强化 fixture hygiene，降低开源仓库泄漏账号、密码、IP、客户命名、原始日志或 token 的风险。
- 把已知中长期技术债保留在项目 TODO/实现状态中，避免第一轮治理范围失控。

成功后，项目应具备一个稳定的开源前质量基线：默认 validator 可绿，公开 fixture 可审计，历史 fixture 不阻断主线。

## Tech Stack

- Python 3 标准库为主，保持现有工具风格。
- YAML 读写沿用现有 `support.common` / 本地 helper。
- 测试继续使用 `pytest`、现有 replay/score 工具和 `tools/validators/validate-repo.py`。
- 不新增运行时依赖，不改变插件打包协议。

## Commands

主要验证命令：

```bash
python3 tools/validators/validate-repo.py
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
python3 -m pytest tests/plugins/claude/test_claude_plugin_install.py tests/plugins/cursor/test_cursor_plugin_install.py -q
git diff --check
```

若拆分 fixture 分层，需要补充或更新对应命令：

```bash
python3 tools/replay/mongodb-replay.py --fixture-root tests/fixtures/active/mongodb --run-analyse
python3 tools/replay/mongodb-score.py --fixture-root tests/fixtures/active/mongodb --run-analyse --min-level medium
```

## Project Structure

目标结构：

```text
tests/fixtures/
├── README.md
├── active/
│   ├── mongodb/
│   └── pulsar/
├── legacy/
│   └── mongodb/
└── .gitkeep 或说明文件
```

目录职责：

- `tests/fixtures/active/`：默认 replay、score、validator 扫描的公开脱敏 fixture。
- `tests/fixtures/legacy/`：历史样本、旧规则样本、暂不符合当前门禁的样本；默认不阻断主线。
- `.local/fixtures/`：本地生成或冻结的候选 fixture，默认 ignore。
- `tests/fixtures/**/raw/`、`private/`、`sensitive/`：未脱敏现场样本目录，必须被 `.gitignore` 屏蔽。

## Code Style

保持现有工具代码风格：小函数、显式错误列表、无重型抽象。

示例：

```python
def fixture_errors(path: Path) -> List[str]:
    errors: List[str] = []
    data = load_yaml(path)
    if data.get("status") not in ("active", "legacy"):
        errors.append("%s status must be active or legacy" % path)
    return errors
```

约定：

- validator 返回错误列表，不直接在深层函数中退出进程。
- 路径参数使用 `Path`。
- 默认行为保守：只扫描 active fixture；legacy 需要显式参数启用。
- fixture 迁移不改业务规则，除非该 fixture 本身必须补证据才能维持期望。

## Testing Strategy

分层验证：

- Unit：fixture 分层发现逻辑、hygiene 规则、fixture metadata 解析。
- Replay：MongoDB active fixtures 必须通过 `mongodb-replay.py --run-analyse`。
- Score gate：active fixtures 必须通过 `mongodb-score.py --run-analyse --min-level medium`。
- Repo validator：`tools/validators/validate-repo.py` 必须默认绿。
- Regression：Claude/Cursor 插件协议和 license 投影测试保持通过。

Fixture 迁移策略：

- `kubernetes-readiness-failure-sample` 若作为 active fixture 保留，必须补足 `pod-not-ready` 信号或结构化 Kubernetes `Unhealthy` event，使 expected 与证据一致。
- 若该样本只用于保存历史期望，则迁移到 `legacy`，默认 replay/score 不扫描。

## Boundaries

Always:

- 保留公开 fixture 的最小可复现证据链。
- 修改 fixture 期望时，同时说明是修正样本还是修正规则。
- 默认 validator 只允许被 active fixture 阻断。
- 所有新增 fixture 必须通过 hygiene 检查。
- 运行 `git diff --check` 和相关 replay/score 命令后再提交。

Ask first:

- 改变 `analysis.yaml` 字段结构或 incident 目录结构。
- 修改 slash 命令行为或 adapter output 状态语义。
- 将 legacy fixture 重新提升为 active。
- 引入新依赖或接入真实 Agent API。
- 把客户现场原始样本纳入仓库。

Never:

- 提交明文密码、token、私钥、客户原始日志或未脱敏远程配置。
- 为了让测试通过直接删除失败 fixture。
- 让历史 fixture 默认阻断主线质量门禁。
- 用 customer clue 替代证据链直接提高根因置信度。
- 在本轮处理 Pulsar/Redis/Kafka 正式支持或深度 analyse 效果优化。

## Success Criteria

1. `python3 tools/validators/validate-repo.py` 默认通过。
2. MongoDB replay 和 score gate 默认只扫描 active fixtures，并全部通过。
3. `kubernetes-readiness-failure-sample` 被修复为 active，或迁移为 legacy 且不再阻断默认门禁。
4. `.gitignore` 明确屏蔽 raw/private/sensitive fixture 目录和本地冻结候选。
5. Fixture README 说明 active/legacy/raw 的职责、准入条件和迁移规则。
6. Fixture hygiene validator 至少覆盖明文凭据、私钥/token、未脱敏远程配置、疑似真实客户名和明显不该入库的生成物。
7. README/license/plugin manifest 相关测试继续通过。
8. `docs/project/todo.md` 与 `docs/project/implementation-status.md` 不再互相冲突；本轮完成项迁移到实现状态，遗留项保留在 TODO。

## Decisions

1. `kubernetes-readiness-failure-sample` 保留为 active fixture，但必须补足结构化证据链。该样本代表常见的 Pod Running 但 NotReady 场景，不应因为当前 fixture 不完整而迁入 legacy。
2. Fixture 目录直接迁移到 `tests/fixtures/active/<middleware>` 和 `tests/fixtures/legacy/<middleware>`。工具可以保留显式 `--fixture-root` 参数，但默认路径只指向 active fixture，不长期维护旧默认路径。
3. IP 脱敏采用分级策略：公网 IP 作为 error；内网 IP 作为 warning 或需要 allowlist/reason。active fixture 中的真实环境内网 IP 应优先替换为文档保留地址，Kubernetes 典型服务地址或合成证据地址可通过 allowlist 说明保留。
4. `tests/golden-paths/fixtures/` 纳入同一套敏感信息扫描。测试假值如 `test-user`、`example-password`、`10.0.0.1` 可允许，但真实凭据、私钥、token、未脱敏远程配置和生成物仍必须阻断。

## Open Questions

None for this implementation slice.
