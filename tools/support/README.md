# Tool Support Modules

`tools/support/` 放 `tools/` 内部复用的工程辅助模块。

边界：

- 这里只放工程脚本公共 helper，例如 repo 根路径解析、YAML 读写、子进程调用封装。
- 不放插件 runtime 正式实现；需要进入 Claude/Cursor runtime payload 的代码仍然归 `src/`。
- 不放历史兼容导出；兼容导出仍放 `tools/lib/`。

当前用途：

- `common.py`
  提供 `ROOT`、`now_iso()`、`resolve_repo_path()`、`load_yaml()`、`write_yaml()`、`run_command()`、`write_text_files()`。

规则：

- 如果 helper 只服务某个 `tools/<domain>/` 子目录，优先先放在该目录内。
- 只有当 helper 被多个工程子目录复用，并且明确不属于 runtime，才提升到这里。
- `src/` 不应依赖 `tools/support/`。
