# Phase 2

`src/phases/phase2/` 放第 2 段“环境确认与对象盘点”的正式实现。

当前边界：

- `inventory.py`
  MongoDB 对象发现、拓扑判断、namespace 选择、认证 hint 提取。

规则：

- 第 2 段输出的是盘点视角的结构化事实，不直接做第 3 段采集或第 4 段推理。
- 中间件通用的对象解析能力，应优先抽到 `src/shared/`，不要把共享逻辑堆在盘点脚本里。
