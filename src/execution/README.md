# Execution Runtime Modules

`src/execution/` 放执行面运行时能力。

这里的代码不负责排障流程编排，而负责真正的远端接入、脚本投放、命令执行、结果回收等执行能力。控制面由 `src/commands/` 和 `src/phases/` 编排调用这些模块。

当前边界：

- `remote/`
  SSH/SSHPass 远端接入、capability check、上下文构建、脚本投放与回收。
  其中 `transport.py` 定义执行编排使用的 transport 接口，`access.py` 提供当前 SSH/scp 实现，`script_output_contract.py` 管脚本输出合同，`capabilities.py` 管远端能力与目标探测，`script_runner.py` 管单脚本执行编排，`executor.py` 管兼容门面，`cli.py` 管远程执行器 CLI。
- `modes.py`
  执行方式合同。当前默认是 `remote`，后续 `local` 和 `offline` 必须通过这里表达能力差异，再接入 phase 编排。

## 执行方式

- `remote`
  当前默认路径。control plane 通过 SSH/SSHPass 进入 jump host 或故障环境，投放脚本并回收证据。
- `local`
  预留路径。control plane 在本机执行采集，不经过 SSH transport。当前还没有正式 executor。
- `offline`
  预留路径。不执行采集命令，只分析已有 incident、fixture 或 remote-run 产物。当前还没有正式 executor。

规则：

- 执行面模块要显式表达“本地控制端 -> 远端执行端”的边界。
- 新执行方式先扩展 `modes.py` 合同，再接入具体 executor。
- 接入 `local` 或 `offline` 时，先补测试证明 mode 不回落到 SSH/SSHPass，再接入 `src/commands/` 或 `src/phases/`。
- phase 目录只负责流程语义，不长期承载远端 transport 或执行器主实现。
- 新的执行通道先实现 execution transport/executor，再由 `modes.py` 和命令入口选择；不要让 slash 命令、phase 或 agent 文档直接编排 SSH/scp。
- 需要被多个 phase 或多个 agent 适配器复用的远端执行能力，应优先沉到这里。
