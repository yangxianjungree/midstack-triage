# Shared Runtime Modules

`src/shared/` 放跨 slash 命令、跨 phase 复用的正式运行时实现。

当前边界：

- `workspace.py`
  工作区路径、incident marker、adapter-output、文件 I/O 合同。
- `analysis_common.py`
  analysis payload 的轻量通用读取辅助，如 `analysis_text()`。
- `analysis_runtime.py`
  分析结果合同、报告生成、结论 guardrail。
- `patch_merge.py`
  第 3 段脚本输出合并规则。
- `scenario_router.py`
  signal bundle 到 scenario 的路由推断。
- `skill_resolver.py`
  scenario 到 skill / asset 的解析。

规则：

- 只要某段实现会被多个命令或多个 phase 复用，就不要继续留在 `tools/`。
- `shared/` 不承载某个单独 phase 的主流程编排；主流程编排放回 `commands/` 或 `phases/`。
- execution plane 专属实现优先归属 `src/execution/`；只有跨平面复用时才进入 `shared/`。
- 共享运行时代码统一收敛在 `src/shared/`
