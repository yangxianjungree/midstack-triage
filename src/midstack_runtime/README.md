# Midstack Runtime Compatibility Layer

`src/midstack_runtime/` 是历史导入路径保留层。

当前职责只有一件事：

- 把旧的 `midstack_runtime.*` import 转发到 `src/shared/*`

正式实现位置：

- 工作区与文件合同：`src/shared/workspace.py`
- 分析合同与报告收口：`src/shared/analysis_runtime.py`

约束：

- 不要在这里新增真实运行时逻辑
- 不要把新的共享能力继续放回 `midstack_runtime/`
- 新代码直接写到 `src/shared/`
