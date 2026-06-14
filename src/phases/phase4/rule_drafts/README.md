# Phase 4 Rule Drafts

`src/phases/phase4/rule_drafts/` 放第 4 段规则保底分析器。

当前边界：

- `mongodb.py`
  MongoDB 规则分析器；根据 incident 目录里的输入、信号和采集结果生成基础 `analysis.yaml` 草稿。
- `pulsar.py`
  Pulsar 规则分析器。
- `__init__.py`
  middleware -> analyser 的正式调度入口，供 `src/commands/analyse.py` 直接调用。

规则：

- 这里放的是正式运行时代码，不再把 analyser 主实现留在 `tools/analyse/`。
- `tools/analyse/*.py` 只保留兼容 CLI 壳，方便 replay、校验和人工单跑。
- 多 middleware 共用的逻辑，优先继续下沉到 `src/shared/`，不要在这里复制。
