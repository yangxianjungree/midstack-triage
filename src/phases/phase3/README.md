# Phase 3

`src/phases/phase3/` 放第 3 段“信号采集与治理”的正式实现。

当前边界：

- `collection.py`
  remote run 导入、场景路由、skill runtime 富化、定向补采触发、采集报告治理。
- `remote_executor.py`
  MongoDB 远程执行器正式实现；负责 capability check、脚本投放、远程执行和结果回收。

规则：

- 第 3 段负责证据构建和治理，不直接给出最终分析结论。
- 远程执行器正式实现也属于第 3 段运行时，统一放在这里。
- `tools/remote-executor/` 只保留兼容 CLI 壳，供 smoke、回放和人工单跑复用。
