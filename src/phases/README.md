# Phase Runtime Modules

`src/phases/` 按排障主流程沉淀 control plane 阶段实现，而不是按脚本来源散放。

当前正式边界：

- `phase1/startup.py`
  第 1 段启动门面；实际远端接入能力来自 `src/execution/remote/access.py`。
- `phase2/inventory.py`
  环境对象盘点、拓扑与 namespace 发现。
- `phase3/collection.py`
  远程采集编排、回放输入构建、场景路由、定向补采。
- `phase4/reasoning.py`
  第 4 段推理运行时门面。
- `phase4/multitrack/`
  第 4 段多轨推理底层实现。
- `phase5/finalize.py`
  分析收口、guardrail、最终报告落盘。
- `phase5/review.py`
  分析结果复核、打分、改进建议生成。

规则：

- phase 目录放“阶段实现”，不是 proposal 文档。
- phase 目录表达流程语义，不长期承载 execution plane 的 transport 或执行器主实现。
- 新 phase 默认采用 `phaseN/<topic>.py` 结构，不再新增新的 `phaseN_xxx.py` 扁平文件。
- 旧的 `phaseN_xxx.py` 平行 shim 已移除；新代码和新测试都直接使用正式 phase 目录。
- 每个 phase 目录在复杂度开始上升后，应补 `README.md` 说明职责边界和允许放置的实现类型。
- 某个 phase 只暴露清晰的入口函数，供 `src/commands/` 编排调用。
- phase 之间共享的通用能力沉到 `src/shared/`。
- 远端执行、SSH 接入、脚本投放这类 execution plane 能力沉到 `src/execution/`。
