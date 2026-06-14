# Source Runtime Modules

`src/` 是这个仓库里“可复用、可导入、会随 Claude/Cursor 等 agent 插件 runtime 一起打包”的正式运行时代码目录。

## 边界

- `src/`
  只放稳定的 Python 实现、运行时模型、共享服务层。
- `tools/`
  放薄入口、校验器、回放脚本、一次命令型工具。这里可以调用 `src/`，但不要把核心实现长期堆在入口脚本里。
- `tests/`
  只放验证代码和固定样例；生成产物写到 `.local/`，不要回写仓库 fixture。

目标约束：

- 只要代码需要进入插件安装后的 runtime payload，就应该放到 `src/` 对应模块目录。
- 测试代码、校验脚本、回放工具、导入/生成工具、讨论文档都不要放进 `src/`。
- `src/` 中的模块默认要满足“可被插件 bundle 打包消费”，不要夹杂只服务仓库工程治理的一次性内容。

## 运行拓扑

`src/` 同时表达两个维度：

- control plane
  `commands/`、`phases/`、`shared/` 中的排障编排、推理、报告与状态管理。
- execution plane
  `execution/` 中的远端接入、脚本投放、远程执行、结果回收。

phase 目录描述“排障流程”，execution 目录描述“运行拓扑中的远端执行能力”。两者都属于正式 runtime，但不要混放。

## 当前模块方向

- `commands/`
  control plane 的 slash 命令正式入口。
- `phases/`
  control plane 的排障 5 段流程实现；每个 phase 优先落成独立目录。
- `execution/`
  execution plane 的远端接入与执行实现。
- `shared/`
  跨命令、跨 phase 复用的正式运行时能力。
- `phases/phase4/`
  第 4 段推理的正式目录；`multitrack/` 放多轨推理底层实现。
- `execution/remote/`
  控制端连接 jump host / 故障环境的远端执行能力。
- `phases/phase4/rules/`
  第 4 段规则保底分析器正式实现。

## 放置规则

- 只要代码需要被多个入口复用，或者需要被 Claude/Cursor/后续其他适配器打包消费，就优先放进 `src/`。
- `tools/` 下的脚本应尽量保持“参数解析 + 调用实现 + 退出码映射”的薄编排职责。
- 设计文档、评审记录、demo 输出不要放进 `src/`。
- 只服务测试、校验、回放、生成、迁移的工程逻辑，应继续放在 `tests/` 或 `tools/`，不要迁入 `src/`。
- 当前已迁入 `src/` 的正式边界包括：
  - `commands/start.py|analyse.py|review.py|finalize.py`
  - `commands/plugin_cli.py`
  - `phases/phase1/startup.py`
  - `phases/phase2/inventory.py`
  - `phases/phase3/collection.py`
  - `phases/phase4/reasoning.py`
  - `phases/phase4/rules/*.py`
  - `phases/phase5/finalize.py|review.py`
  - `execution/remote/access.py|executor.py|mongodb_collection_runtime.py`
  - `shared/workspace.py|analysis_common.py|analysis_runtime.py`
  - `shared/patch_merge.py|scenario_router.py|skill_resolver.py`

约束：

- 新的共享运行时代码只写 `src/shared/`
- 新的 Phase 4 运行时代码只写 `src/phases/phase4/` 与其子目录，不再保留平行旧目录
- `src/` 下不再保留仅为仓库内部迁移服务的平行 shim 目录或扁平 phase 别名文件
