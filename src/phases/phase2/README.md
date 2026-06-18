# Phase 2

`src/phases/phase2/` 放第 2 段“环境确认与对象盘点”的正式实现。

当前边界：

- `inventory.py`
  MongoDB 对象发现、拓扑判断、namespace 选择、认证 hint 提取。
- `auth.py`
  认证 secret 候选提取、评分、去重和最终 hint 选择。
- `targets.py`
  从盘点对象构建 MongoDB targets，并按选定 namespace 收敛对象范围。
- `topology.py`
  从 MongoDB role 和 deployment architecture hint 生成拓扑候选。
- `events.py`
  判断 Kubernetes Event 是否关联当前盘点对象。
- `objects.py`
  Kubernetes 对象归一化、MongoDB role hint 和 deployment architecture hint 的纯函数。
- `kubectl.py`
  第 2 段盘点需要的远端 `kubectl get ... -o json` 包装，只负责返回结构化 JSON 结果。

规则：

- 第 2 段输出的是盘点视角的结构化事实，不直接做第 3 段采集或第 4 段推理。
- 中间件通用的对象解析能力，应优先抽到 `src/shared/`，不要把共享逻辑堆在盘点脚本里。
- `__init__.py` 只做包级导出，正式实现仍放在 `inventory.py`、`auth.py`、`targets.py`、`topology.py`、`events.py`、`objects.py` 和 `kubectl.py`。
