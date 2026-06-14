# Phase 4 Tests

`tests/phases/phase4/multitrack/` 只放第 4 段多轨推理模块的验证代码。

目录约束：

- `unit/`
  纯模块级测试，不依赖真实远程环境
- `e2e/`
  使用真实 fixture 或 CLI 入口做端到端验证
- `conftest.py`
  只放共享 fixture / mock helper

不要再在这里放：

- demo 脚本
- 手工执行入口
- 运行产物目录
- 空壳 `integration/` / `fixtures/` 占位目录

真实 incident fixture 继续放在仓库公共位置 `tests/fixtures/`，避免第 4 段测试目录再复制一份样例数据。
