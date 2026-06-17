# Phase 3

`src/phases/phase3/` 放第 3 段“信号采集与治理”的正式实现。

当前边界：

- `collection.py`
  Phase 3 control-plane 编排入口：导入 remote run、调用场景路由、富化 skill runtime、触发定向补采。
- `remote_run.py`
  remote executor 输出目录契约、脚本输出合并、remote-executor 结果写入采集报告。
- `recollection.py`
  基于已有证据选择定向补采脚本，不负责启动远程执行。
- `report_gaps.py`
  采集报告 evidence gap 的归一化、收口和补采缺口记录。
- `skill_runtime.py`
  根据 middleware/scenario 匹配 skill、检查脚本证据完整性，并写回 runtime 上下文。

规则：

- 第 3 段负责证据构建和治理，不直接给出最终分析结论。
- 远程执行器的正式实现已经下沉到 `src/execution/remote/executor.py`。
- `collection.py` 作为 control plane 编排层调用 execution plane，不重复承载 transport 实现。
- 仓库不再保留 `tools/remote-*` 兼容壳；工程验证和插件 runtime 统一直接调用 `execution.remote.executor`。
