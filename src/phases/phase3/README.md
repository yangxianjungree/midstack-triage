# Phase 3

`src/phases/phase3/` 放第 3 段“信号采集与治理”的正式实现。

当前边界：

- `collection.py`
  remote run 导入、场景路由、skill runtime 富化、定向补采触发、采集报告治理。

规则：

- 第 3 段负责证据构建和治理，不直接给出最终分析结论。
- 远程执行器的正式实现已经下沉到 `src/execution/remote/executor.py`。
- `collection.py` 作为 control plane 编排层调用 execution plane，不重复承载 transport 实现。
- `tools/remote-executor/` 只保留兼容 CLI 壳，供 smoke、回放和人工单跑复用。
