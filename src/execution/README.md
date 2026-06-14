# Execution Runtime Modules

`src/execution/` 放执行面运行时能力。

这里的代码不负责排障流程编排，而负责真正的远端接入、脚本投放、命令执行、结果回收等执行能力。控制面由 `src/commands/` 和 `src/phases/` 编排调用这些模块。

当前边界：

- `remote/`
  SSH/SSHPass 远端接入、capability check、上下文构建、脚本投放与回收。

规则：

- 执行面模块要显式表达“本地控制端 -> 远端执行端”的边界。
- phase 目录只负责流程语义，不长期承载远端 transport 或执行器主实现。
- 需要被多个 phase 或多个 agent 适配器复用的远端执行能力，应优先沉到这里。
