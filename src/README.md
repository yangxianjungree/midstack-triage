# Source Runtime Modules

`src/` 是这个仓库里“可复用、可导入、可随插件一起打包”的正式运行时代码目录。

## 边界

- `src/`
  放稳定的 Python 实现、运行时模型、共享服务层。
- `tools/`
  放薄入口、校验器、回放脚本、一次命令型工具。这里可以调用 `src/`，但不要把核心实现长期堆在入口脚本里。
- `tests/`
  只放验证代码和固定样例；生成产物写到 `.local/`，不要回写仓库 fixture。

## 当前模块方向

- `commands/`
  slash 命令的正式实现入口。
- `phases/`
  按排障 5 段主流程拆分的阶段实现；每个 phase 优先落成独立目录。
- `shared/`
  跨命令、跨 phase 复用的正式运行时能力。
- `phases/phase4/`
  第 4 段推理的正式目录；`multitrack/` 放多轨推理底层实现。
- `midstack_runtime/`
  旧兼容层，只做对 `shared/` 的薄转发，不再承载正式实现。

## 放置规则

- 只要代码需要被多个入口复用，或者需要被 Claude/Cursor/后续其他适配器打包消费，就优先放进 `src/`。
- `tools/` 下的脚本应尽量保持“参数解析 + 调用实现 + 退出码映射”的薄编排职责。
- 设计文档、评审记录、demo 输出不要放进 `src/`。
- 当前已迁入 `src/` 的正式边界包括：
  - `commands/start.py|analyse.py|review.py|finalize.py`
  - `phases/phase1/startup.py`
  - `phases/phase2/inventory.py`
  - `phases/phase3/collection.py`
  - `phases/phase4/reasoning.py`
  - `shared/workspace.py|analysis_runtime.py`
  - `shared/patch_merge.py|scenario_router.py|skill_resolver.py|mongodb_collection_runtime.py`

兼容层仍然保留在：

- `phases/phase1_startup.py`
- `phases/phase2_inventory.py`
- `phases/phase3_collection.py`
- `phases/phase4_reasoning.py`
- `midstack_runtime/`

约束：

- 新的共享运行时代码只写 `src/shared/`
- `src/midstack_runtime/` 只允许 shim，不再新增真实逻辑
