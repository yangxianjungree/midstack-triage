---
status: draft
last_updated: 2026-06-17
supersedes: none
superseded_by: none
---

# 测试与安装门禁

本文档统一说明 Midstack 的工程回归、插件安装检查和 sandbox 实测门禁。目标是避免“仓库测试通过，但 Claude/Cursor 安装态失败”。

## 门禁分层

| 层级 | 目标 | 代表命令 |
| --- | --- | --- |
| 仓库工程门禁 | 校验资产、fixture、replay、score、工具边界 | `python3 tools/validators/validate-repo.py` |
| 适配器单测 | 锁定 Claude/Cursor installer、命令合同和 runtime marker | `python3 -m pytest tests/plugins/claude tests/plugins/cursor -q` |
| 安装态自检 | 在目标 workspace 安装插件并检查 payload 完整性 | `plugin-install.py check` / `--check-workspace` |
| sandbox smoke | 从已安装 workspace 运行真实 slash 命令或等价 CLI | `/midstack:validate`、`/midstack:start`、`/midstack:analyse` |

默认 sandbox 是当前仓库的兄弟目录：

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
```

## 公共安装合同

Claude 和 Cursor 的安装目录不同，但必须满足同一组合同：

- 安装态 runtime 自包含，不依赖源码 checkout、源码 `tools/plugin/midstack-local.py` 或某个开发者机器路径。
- incident 输出只进入目标 workspace 的 `.local/incidents/`。
- workspace state 不允许回退到历史 `engine_root` 字段。
- slash command / rules 只能调用安装态 runtime wrapper，不应引导 Agent 直接跑 `mongosh`、`pip install`、裸 `ssh` 或裸 `kubectl`。
- 新增或修改 agent 适配器时，必须同步 `plugins/README.md`、对应 `plugins/<agent>/README.md` 和本文档门禁。

公共合同测试放在 `tests/plugins/install_contracts.py`。Claude/Cursor 适配器测试应复用这里的 helper，不要各自复制禁止 token、runtime wrapper、首跳工具约束。

本地维护者的安装态回归收口脚本是 `tools/validators/validate-installed-adapters.py`。它只串起现有 installer、check 和 smoke 命令，不是新的 runtime 入口。

slash 命令与 5 阶段对应关系见 [Slash 命令面说明](slash-command-surface.md)。

## 仓库工程门禁

常规提交前至少运行：

```bash
python3 tools/validators/validate-repo.py
git diff --check
```

`validate-repo.py` 当前覆盖：

- MongoDB / Pulsar 资产合同
- golden path
- patch merge
- fixture hygiene
- Kubernetes runtime 分类
- tool boundary
- scenario routing
- remote run contracts
- MongoDB replay
- MongoDB score gate
- Cursor adapter smoke

改动范围较小时，可先运行更小的相关测试；合并或提交前仍建议跑完整门禁。

## Claude 安装门禁

Claude 是 bundled plugin runtime。安装态必须从 `${CLAUDE_PLUGIN_ROOT}/runtime/...` 执行，不依赖 sandbox 内或兄弟目录里的源码 checkout。

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 plugins/claude/plugin-install.py install --workspace "$SANDBOX"
python3 plugins/claude/plugin-install.py check --workspace "$SANDBOX"
cd "$SANDBOX"
claude -p "/midstack:validate" --allowedTools "Bash(python3 *)"
```

Claude installer/check 必须验证：

- Claude 可见 `midstack@midstack-triage-local`
- 旧 `midstack-triage@midstack-triage-local` 不存在
- 命令面为 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate`
- installed plugin payload 包含 `runtime/bin/midstack-local.py`、`runtime/bin/resolve-workspace.py`、`runtime/src/`、`runtime/domains/` 等 marker
- command markdown 使用 `${CLAUDE_PLUGIN_ROOT}`，不读取 `engine_root`
- `resolve-workspace.py` 能把输出目录解析回目标 sandbox
- installed runtime smoke 能写出 blocked/ready adapter output，且无 traceback

Claude slash smoke 建议至少验证：

```bash
claude -p "/midstack:start <host clue with credentials>" --allowedTools "Bash(python3 *)"
claude -p "/midstack:analyse" --allowedTools "Bash(python3 *)"
```

验收重点：

- 不运行 `mongosh`、`pip install`、raw `ssh`、raw `kubectl`
- incident 输出在 sandbox workspace `.local/incidents/`
- 不写入 `.claude/marketplaces/.../runtime/.local/incidents/`
- 用户摘要不回显密码或 token

## Cursor 安装门禁

Cursor 是 workspace-local runtime。安装态必须从目标 workspace 的 `.cursor/midstack-triage-runtime/...` 执行，不依赖源码 checkout。

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init "$SANDBOX"
python3 plugins/cursor/plugin-install.py --check-workspace "$SANDBOX"
python3 plugins/cursor/test-agent-cli.py
python3 plugins/cursor/test-sandbox.py "$SANDBOX"
```

Cursor installer/check 必须验证：

- `.cursor/midstack-triage.workspace.json` 只包含 `runtime_root`，不包含 `engine_root`
- `.cursor/commands/midstack:*.md` 和 `.cursor/rules/midstack-triage.mdc` 是 workspace-local copy
- `.cursor/midstack-triage-runtime/` 包含 `bin/`、`tools/`、`src/`、`domains/`、`scenarios/`、`core/`、`interfaces/`
- 命令和规则不包含源码 checkout 执行模式
- smoke 的 cwd 使用目标 workspace，不借源码仓库 cwd 通过

Cursor slash smoke 建议在 Cursor 里验证：

```text
/midstack:start <host clue with credentials>
/midstack:analyse
```

验收重点：

- Agent 生成的 shell 形态为 `python3 <workspace>/.cursor/midstack-triage-runtime/bin/midstack-local.py ...`
- 不生成 `cd <source-checkout> && python3 tools/plugin/midstack-local.py ...`
- incident 输出在 workspace `.local/incidents/`

## 什么时候跑哪些门禁

| 改动类型 | 必跑 |
| --- | --- |
| 文档小改 | `git diff --check`，必要时搜索旧路径/旧合同 |
| runtime 代码 | `python3 tools/validators/validate-repo.py` |
| Claude command / installer / runtime bundle | Claude 单测 + install/check + `/midstack:validate` |
| Cursor command / installer / runtime bundle | Cursor 单测 + `test-agent-cli.py` + `test-sandbox.py` |
| 安装态回归收口 | `tools/validators/validate-installed-adapters.py` |
| 远程执行或采集脚本 | validator + replay + 真实远程采集回归 |
| 推理、规则、review、报告输出 | replay + score gate + 相关 phase 测试 |

## 常见回归信号

- Claude/Cursor 命令里出现 `engine_root`
- 命令生成 `cd <source-checkout>`
- 命令直接调用源码 `tools/plugin/midstack-local.py`
- Claude incident 写入 `.claude/marketplaces/.../runtime/.local/`
- Cursor smoke 在源码仓库 cwd 下通过，但 sandbox 中失败
- Agent 在 `/midstack:start` 里自行执行 `mongosh`、`pip install`、raw `ssh` 或 raw `kubectl`

出现以上任一情况，应先修安装态合同和门禁，再讨论 analyse 排障效果本身。
