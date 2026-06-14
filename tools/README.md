# Tools

`tools/` 放仓库级脚本入口和工程辅助工具，不放长期演进的正式运行时实现。

## 边界

- `tools/`
  适合放 CLI 入口、校验器、回放器、导入/生成脚本、一次性工程工具。
- `src/`
  适合放会被多个入口复用、会被插件 bundle 打包、或者需要长期维护的正式实现。
- `plugins/`
  适合放 Agent 平台适配器源码，不放仓库通用工具逻辑。

## 当前子目录职责

- `plugin/`
  本地 CLI 适配层；`midstack-local.py` 是薄启动壳，正式调度在 `src/commands/plugin_cli.py`。
- `remote-executor/`
  真实远程采集执行器的兼容 CLI 壳；正式实现已迁入 `src/phases/phase3/remote_executor.py`。
- `remote-smoke/`
  兼容保留的 smoke CLI 包装层。
- `analyse/`
  MongoDB / Pulsar 规则 analyse runner 的兼容 CLI 壳；正式实现已迁入 `src/phases/phase4/rule_drafts/`。
- `validators/`
  仓库结构、资产合同和工程回归校验器。
- `replay/`
  fixture 冻结、回放和评分工具。
- `generators/`
  runbook / command / skill 骨架生成器。
- `importers/`
  外部 Markdown 资产导入器。
- `lib/`
  历史兼容导入层，只转发到 `src/shared/*`，不再新增正式实现。

## 放置规则

- 只要代码已经不是“单脚本专用 helper”，就优先迁到 `src/`。
- 如果代码需要进入 Claude/Cursor 等 agent 插件安装后的 runtime，就应该放到 `src/` 对应模块，而不是继续堆在 `tools/`。
- `tools/` 下脚本可以 `import src/*`，但不要反过来让 `src/` 依赖 `tools/`。
- 测试、校验、回放、生成、迁移等工程逻辑继续放在 `tools/` 或 `tests/`，不要因为“顺手复用”把它们塞进 `src/`。
- 生成输出默认写到 `.local/` 或临时目录，不要回写仓库 fixture。
- 新增 `tools/*` 子目录时，应同时补一个 README 说明用途和边界。
