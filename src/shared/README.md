# Shared Runtime Modules

`src/shared/` 放跨 slash 命令、跨 phase 复用的正式运行时实现。

当前边界：

- `workspace.py`
  工作区路径、incident marker、adapter-output、文件 I/O 合同。
- `analysis_runtime.py`
  分析结果合同、报告生成、结论 guardrail。
- `patch_merge.py`
  第 3 段脚本输出合并规则。
- `scenario_router.py`
  signal bundle 到 scenario 的路由推断。
- `skill_resolver.py`
  scenario 到 skill / asset 的解析。
- `mongodb_collection_runtime.py`
  指向 `src/execution/remote/mongodb_collection_runtime.py` 的兼容导出层；不要在这里继续演进实现。

规则：

- 只要某段实现会被多个命令或多个 phase 复用，就不要继续留在 `tools/`。
- `shared/` 不承载某个单独 phase 的主流程编排；主流程编排放回 `commands/` 或 `phases/`。
- execution plane 专属实现优先归属 `src/execution/`；只有跨平面复用时才进入 `shared/`。

约束：

- 共享运行时代码统一收敛在 `src/shared/`
- 不再保留单独的 `src/midstack_runtime/` 兼容目录
