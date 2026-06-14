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
- `analyse/`
  MongoDB / Pulsar 规则 analyse runner 的兼容 CLI 壳；正式实现已迁入 `src/phases/phase4/rules/`。
- `remote-executor/`
  真实远程采集执行器的兼容 CLI 壳；正式实现已迁入 `src/execution/remote/executor.py`。
- `remote-smoke/`
  兼容保留的 smoke CLI 包装层；实际执行本体仍走 `src/execution/remote/`。
- `lib/`
  历史兼容导入层，只转发到 `src/shared/*` 或 `src/execution/*`，不再新增正式实现。
- `validators/`
  仓库结构、资产合同和工程回归校验器。
- `replay/`
  fixture 冻结、回放和评分工具。
- `generators/`
  runbook / command / skill 骨架生成器。
- `importers/`
  外部 Markdown 资产导入器。

## 目录分类

| 子目录 | 类型 | 是否要求薄壳 | 是否应迁入 `src/` |
| --- | --- | --- | --- |
| `plugin/` | runtime 入口适配 | 是 | 已迁，主实现已在 `src/commands/` |
| `analyse/` | runtime 兼容入口 | 是 | 已迁，主实现已在 `src/phases/phase4/rules/` |
| `remote-executor/` | runtime 兼容入口 | 是 | 已迁，主实现已在 `src/execution/remote/` |
| `remote-smoke/` | smoke 包装入口 | 是 | 不迁；它是工程 smoke 壳，执行本体已在 `src/` |
| `lib/` | 历史兼容导入层 | 是 | 已迁，主实现已在 `src/shared/` / `src/execution/` |
| `validators/` | 工程校验 | 否 | 不迁 |
| `replay/` | 工程回放/评分 | 否 | 不迁 |
| `generators/` | 工程生成器 | 否 | 不迁 |
| `importers/` | 工程导入器 | 否 | 不迁 |

## 放置规则

- 只要代码已经不是“单脚本专用 helper”，就优先迁到 `src/`。
- 如果代码需要进入 Claude/Cursor 等 agent 插件安装后的 runtime，就应该放到 `src/` 对应模块，而不是继续堆在 `tools/`。
- `tools/` 下脚本可以 `import src/*`，但不要反过来让 `src/` 依赖 `tools/`。
- 测试、校验、回放、生成、迁移等工程逻辑继续放在 `tools/` 或 `tests/`，不要因为“顺手复用”把它们塞进 `src/`。
- 生成输出默认写到 `.local/` 或临时目录，不要回写仓库 fixture。
- 新增 `tools/*` 子目录时，应同时补一个 README 说明用途和边界。
- 如果某段代码表达的是 execution plane 能力，优先落在 `src/execution/`，再由 `tools/` 提供 CLI 壳。

自动约束：

- `tools/validators/validate-tool-boundaries.py`
  会校验 `tools/plugin/`、`tools/analyse/`、`tools/remote-executor/`、`tools/remote-smoke/`、`tools/lib/` 中的包装脚本仍保持薄壳，并校验 `src/` 不反向依赖 `tools/`。
