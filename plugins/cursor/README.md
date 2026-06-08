# Cursor Integration

本目录存放 Cursor 项目级集成的源实现。

当前形态：

- 安装时写入目标项目的 `.cursor/mcp.json` 注册本地 MCP server
- 安装时写入目标项目的 `.cursor/commands/*.md` 提供 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate` 命令入口
- 安装时写入目标项目的 `.cursor/rules/midstack-triage.mdc` 引导 Cursor Agent 优先调用 MCP tools
- MCP server 通过 `MIDSTACK_TRIAGE_WORKSPACE` 把相对输出路径解析到目标 Cursor 项目，而不是 midstack 源码仓库
- MCP server 同时响应 `tools/list`、`resources/list`、`resources/read`、`prompts/list` 和 `ping`，避免 Cursor 查询资源时卡住

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

安装并批准 Cursor CLI MCP server：

```bash
python3 plugins/cursor/install.py --target-dir /home/stephen/AI/<target-project> --approve
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

检查 Cursor CLI 是否真正能加载 tools：

```bash
cd /home/stephen/AI/<target-project>
agent mcp list-tools midstack-triage
```

如果 MCP 配置变更后出现 `has not been approved`，重新执行：

```bash
agent mcp enable midstack-triage
```

headless 交互测试建议显式批准 MCP：

```bash
agent --print --trust --approve-mcps --workspace /home/stephen/AI/<target-project> \
  '/midstack:start 我的192.168.154.251环境的一个mongo节点有问题，账号密码是root/123，你帮我看一下吧'
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
- `midstack_analyse_incident`
- `midstack_analyse_current`
- `midstack_analyse_fixture`
- `midstack_analyse_remote_run`
- `midstack_analyse_remote_config`
- `midstack_review`

`midstack_start` 在用户未提供 namespace 时会做轻量 MongoDB namespace 发现：扫描远端 Kubernetes 的 Pods、StatefulSets、Services；如果只有一个候选 namespace 会自动填充，如果存在多个候选 namespace 会返回 `blocked` 并要求用户明确选择。

MCP server 还暴露以下 resources，供 Cursor 在命令执行前读取简要用法：

- `midstack://commands/start`
- `midstack://commands/analyse`

## Automated Test

运行 Cursor MCP smoke test：

```bash
python3 plugins/cursor/test-mcp-server.py
```

该测试会在当前仓库 `.local/cursor-mcp-tests/` 下创建临时项目，安装 `.cursor/` 投影，验证 `resources/list` 不超时，调用 MCP analyse/review，并验证输出写入临时项目的 `.local/`。

运行固定 sandbox smoke test：

```bash
python3 plugins/cursor/test-sandbox.py
```

该测试会保留 `/home/stephen/AI/midstack-cursor-sandbox`，执行安装、approval、`agent mcp list-tools midstack-triage` 和 MCP smoke，便于后续直接用 Cursor 打开该项目做真实交互验证。

运行完整仓库验证，包括 Cursor MCP smoke：

```bash
python3 tools/validators/validate-repo.py
```

如需跳过 Cursor MCP smoke：

```bash
python3 tools/validators/validate-repo.py --skip-cursor
```
