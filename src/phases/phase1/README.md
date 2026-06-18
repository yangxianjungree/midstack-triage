# Phase 1

`src/phases/phase1/` 放第 1 段“受理与启动”的正式实现。

当前边界：

- `intake.py`
  第 1 段输入完整度、环境模式识别和结构化追问合同。
- `startup.py`
  第 1 段启动门面；消费 execution plane 的远端环境校验能力。

规则：

- 第 1 段只负责启动前的输入与环境确认，不承载对象盘点或后续分析编排。
- `remote` 是当前默认主路径；`local` 和 `offline` 先在 intake 中识别和引导，不隐式回退到 SSH。
- 远端 SSH/SSHPass 接入与可达性检查，正式实现放在 `src/execution/remote/access.py`。
- 需要被多个阶段复用的公共能力，应下沉到 `src/shared/` 或 `src/execution/`。
