# Tool Lib Compatibility Layer

`tools/lib/` 是历史脚本导入路径的兼容层。

这里当前只保留薄转发模块：

- `mongodb_collection_runtime.py` -> `src/execution/remote/mongodb_collection_runtime.py`
- `patch_merge.py` -> `src/shared/patch_merge.py`
- `scenario_router.py` -> `src/shared/scenario_router.py`
- `skill_resolver.py` -> `src/shared/skill_resolver.py`

约束：

- 不要把新的共享能力继续写回 `tools/lib/`
- 新代码直接导入 `src/shared/*`
- 只有当旧脚本或外部调用方还依赖历史路径时，才在这里保留 shim
