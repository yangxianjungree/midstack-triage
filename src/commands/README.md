# Slash Command Runtime

`src/commands/` 放 Midstack slash 命令对应的正式实现。

目标边界：

- `plugin_cli.py`
  本地 CLI 调度层，负责把 `start/analyse/review/finalize-analysis` 接到阶段实现。
- `start.py`
  第 1/2 段启动编排、incident 初始化。
- `analyse.py`
  第 3/4/5 段主分析入口编排。
  从 started incident 的 `execution_mode` / `environment_mode` 派生执行模式；`offline` 只消费已有产物，`local` 读取 ready incident 的 `local-config.yaml` 并通过本地 transport 执行采集。
- `review.py`
  第 5 段 review 入口壳，转发到 `phases/phase5/review.py`。
- `finalize.py`
  第 5 段 finalize 入口壳，转发到 `phases/phase5/finalize.py`。

当前边界：

- `src/commands/plugin_cli.py`
  持有本地 CLI 的参数解析和命令调度。
- `tools/plugin/midstack-local.py`
  只负责引导 Python 路径并调用 `plugin_cli.main()`。

不再长期承载主逻辑。
