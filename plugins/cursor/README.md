# Cursor Integration

本目录存放 Cursor 项目级集成的源实现。

当前形态：

- 安装时写入目标项目的 `.cursor/mcp.json` 注册本地 MCP server
- 安装时写入目标项目的 `.cursor/commands/*.md` 提供 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate` 命令入口
- 安装时写入目标项目的 `.cursor/rules/midstack-triage.mdc` 引导 Cursor Agent 优先调用 MCP tools
- MCP server 通过 `MIDSTACK_TRIAGE_WORKSPACE` 把相对输出路径解析到目标 Cursor 项目，而不是 midstack 源码仓库

这不是 Cursor marketplace 插件，也不依赖人工在 UI 中逐条执行测试。

## Install

插件源目录包含：

```text
plugins/cursor/mcp-server.py
plugins/cursor/commands/midstack:start.md
plugins/cursor/commands/midstack:analyse.md
plugins/cursor/commands/midstack:review.md
plugins/cursor/commands/midstack:validate.md
plugins/cursor/rules/midstack-triage.mdc
```

安装到目标 Cursor 项目：

```bash
python3 plugins/cursor/install.py --target-dir /home/stephen/AI/<target-project>
```

安装后目标项目会包含：

```text
<target-project>/.cursor/mcp.json
<target-project>/.cursor/commands/midstack:start.md
<target-project>/.cursor/commands/midstack:analyse.md
<target-project>/.cursor/commands/midstack:review.md
<target-project>/.cursor/commands/midstack:validate.md
<target-project>/.cursor/rules/midstack-triage.mdc
```

检查目标项目安装状态：

```bash
python3 plugins/cursor/install.py --target-dir /home/stephen/AI/<target-project> --check
```

固定 sandbox 项目可用于贴近真实 Cursor 项目安装形态的测试：

```bash
python3 plugins/cursor/test-sandbox.py
```

默认 sandbox 路径：

```text
/home/stephen/AI/midstack-cursor-sandbox
```

## Tools

MCP server 暴露以下 tools：

- `midstack_validate`
- `midstack_start`
- `midstack_analyse_fixture`
- `midstack_analyse_remote_run`
- `midstack_analyse_remote_config`
- `midstack_review`

## Automated Test

运行 Cursor MCP smoke test：

```bash
python3 plugins/cursor/test-mcp-server.py
```

该测试会在 `/home/stephen/AI/` 下创建临时项目，安装 `.cursor/` 投影，调用 MCP analyse/review，并验证输出写入临时项目的 `.local/`。

运行固定 sandbox smoke test：

```bash
python3 plugins/cursor/test-sandbox.py
```

该测试会保留 `/home/stephen/AI/midstack-cursor-sandbox`，便于后续直接用 Cursor 打开该项目做真实交互验证。

运行完整仓库验证，包括 Cursor MCP smoke：

```bash
python3 tools/validators/validate-repo.py
```

如需跳过 Cursor MCP smoke：

```bash
python3 tools/validators/validate-repo.py --skip-cursor
```
