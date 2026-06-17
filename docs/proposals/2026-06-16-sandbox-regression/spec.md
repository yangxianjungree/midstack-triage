---
status: draft
last_updated: 2026-06-16
supersedes: none
superseded_by: none
---

# 2026-06-16 Sandbox 安装包回归规格

## Objective

统一本地固定 sandbox 工作区名称，并用该目录重新验证 Claude/Cursor 安装包回归。

本轮标准 sandbox 路径定为：

```text
/home/stephen/AI/midstack-sandbox
```

目标：

- 后续文档、脚本默认值和示例不再使用 `midstack-cursor-sandbox` 作为当前标准路径。
- Claude 插件重新安装到 `midstack-sandbox` 后，通过 installer check 和安装后 runtime validate。
- Cursor 插件安装到 `midstack-sandbox` 后，Agent 只能调用 workspace-local bundled runtime，不能再 `cd` 到 `midstack-triage` 源码仓库或调用源码 `tools/plugin/midstack-local.py`。
- 保持旧 `midstack-cursor-sandbox` 作为历史工作区，不主动删除。

## Commands

```bash
python3 plugins/claude/plugin-install.py install --workspace /home/stephen/AI/midstack-sandbox
python3 plugins/claude/plugin-install.py check --workspace /home/stephen/AI/midstack-sandbox
cd /home/stephen/AI/midstack-sandbox && claude -p "/midstack:validate" --allowedTools "Bash(python3 *)"
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /home/stephen/AI/midstack-sandbox
python3 plugins/cursor/plugin-install.py --check-workspace /home/stephen/AI/midstack-sandbox
python3 plugins/cursor/test-sandbox.py /home/stephen/AI/midstack-sandbox
python3 -m pytest tests/execution/remote/test_runtime_support.py tests/plugins/claude/test_claude_plugin_install.py tests/plugins/cursor/test_cursor_plugin_install.py -q
git diff --check
```

## Project Structure

- `plugins/claude/`
  Claude 插件安装器、README 和 runtime bundle。
- `plugins/cursor/`
  Cursor 安装器、workspace-local runtime 投影、命令模板、规则和固定 sandbox 冒烟。
- `docs/specs/`
  sandbox 依赖边界和当前工作区名称。
- `/home/stephen/AI/midstack-sandbox`
  标准兄弟 sandbox 工作区。

## Code Style

- 只改当前示例、默认值和帮助文本。
- 不改历史 incident 引用和历史 proposal 记录。
- 不把 sandbox 目录内容提交到仓库。

## Testing Strategy

- Installer check：验证 Claude 安装可见性、sandbox-local marketplace、bundled runtime 和 selfcheck。
- Installed runtime validate：从 sandbox 内通过 Claude slash 命令或等价安装后 runtime 入口验证。
- Cursor command contract：命令模板和规则必须读取 `runtime_root`，不得出现 `engine_root`、源码仓库 `cd`、源码 `tools/plugin/midstack-local.py` 安装态调用。
- Cursor smoke：确认固定 sandbox 默认路径统一后仍可用，且 CLI cwd 为 sandbox 而不是源码仓库。
- Cursor current-incident smoke：构造 ready incident 与 remote-config，从 workspace-local runtime 运行 `analyse --output-root .local/incidents`，覆盖真实 `/midstack:analyse` 路径。
- Source-checkout root invariant：`src/execution/remote/runtime_support.py` 在无 `MIDSTACK_TRIAGE_RUNTIME_ROOT` 时必须把 repo root 解析为 `midstack-triage`，而不是兄弟目录 `/home/stephen/AI`。
- Unit regression：保留 Claude/Cursor installer 测试。

## Boundaries

Always:

- 使用 `/home/stephen/AI/midstack-sandbox` 作为新的标准固定 sandbox。
- 保持 Claude bundled runtime 不依赖 sandbox 内源码 checkout。
- 保持 Cursor 安装态不依赖源仓库 checkout。

Ask first:

- 删除旧 `midstack-cursor-sandbox`。
- 改变 Claude/Cursor slash command 名称协议。
- 提交 sandbox 工作区内容。

Never:

- 将 `.claude/`、`.cursor/`、`.local/` sandbox 投影提交到本仓库。
- 用旧 `midstack-cursor-sandbox` 继续作为当前默认路径。
- 让 Cursor 安装态命令生成 `cd /home/stephen/AI/midstack-triage && python3 tools/plugin/midstack-local.py ...`。

## Success Criteria

1. 当前代码和文档中的固定默认 sandbox 路径统一为 `/home/stephen/AI/midstack-sandbox`。
2. Claude plugin install/check 在该路径通过。
3. Claude 安装后 runtime validate 通过，且不依赖源仓库 checkout。
4. Cursor workspace state 只包含 `runtime_root`，不包含 `engine_root`。
5. Cursor 命令模板、规则和 sandbox 投影均不包含源码仓库执行模式。
6. Cursor sandbox smoke 可在该路径通过。
7. Cursor current-incident analyse smoke 可在该路径通过，不出现 `FileNotFoundError`、`Traceback`、`/home/stephen/AI/domains/...` 或源码仓库调用。
8. `git diff --check` 和相关 installer 测试通过。

## Open Questions

None.
