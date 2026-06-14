# Slash Command Runtime

`src/commands/` 放 Midstack slash 命令对应的正式实现。

目标边界：

- `start.py`
  第 1/2 段启动编排、incident 初始化。
- `analyse.py`
  第 3/4/5 段主分析入口编排。
- `review.py`
  第 5 段 review 入口壳，转发到 `phases/phase5/review.py`。
- `finalize.py`
  第 5 段 finalize 入口壳，转发到 `phases/phase5/finalize.py`。

`tools/plugin/midstack-local.py` 应逐步收敛成：

1. 参数解析
2. 调用 `src/commands/*`
3. 返回退出码

不再长期承载主逻辑。
