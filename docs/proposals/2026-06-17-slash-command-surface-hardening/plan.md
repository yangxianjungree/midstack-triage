---
status: draft
last_updated: 2026-06-17
supersedes: none
superseded_by: none
related:
  - ../2026-06-17-module-refactor-roadmap/spec.md
  - ../2026-06-17-plugin-install-deploy-hardening/plan.md
  - ../../specs/plugin-runtime.spec.md
  - ../../project/testing-and-install-gates.md
---

# Plan: Slash 命令与 Agent 命令面整改

## Objective

治理 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate` 的命令入口和 Agent 执行合同。

本阶段不优化 analyse 排障效果，不拆控制面 phase 实现；只处理命令 markdown、Cursor always-on rule、runtime CLI dispatcher 参数合同、命令面测试和文档规范。

## Success Criteria

1. Claude/Cursor 对外命令语义一致：主路径是 `start -> analyse`，`review` 是质量反馈，`validate` 是维护者检查。
2. `start` 命令只创建或恢复 incident，不提前分析、不自行跑裸远程/数据库/安装命令。
3. `analyse` 命令只通过安装态 runtime 进入控制面，不让 Agent 在 runtime 前自行采集或安装依赖。
4. `review` 和 `validate` 不被误写成用户排障主路径。
5. Claude/Cursor 命令面的公共合同由测试 helper 覆盖，适配器差异只保留在适配器专属测试中。
6. `src/commands/plugin_cli.py` 的子命令、参数和 slash command 文档保持一致。
7. 独立 slash 命令文档能解释 `/midstack:*` 与 5 阶段流程的对应关系。
8. 命令面文档和测试门禁能解释哪些命令在源码仓库运行，哪些命令在安装态 workspace 运行。

## Scope

包含：

- `plugins/claude/commands/*.md`
- `plugins/cursor/commands/midstack:*.md`
- `plugins/cursor/rules/midstack-triage.mdc`
- `src/commands/plugin_cli.py`
- `tools/plugin/midstack-local.py`
- `tests/plugins/install_contracts.py`
- `tests/plugins/claude/test_claude_plugin_install.py`
- `tests/plugins/cursor/test_cursor_plugin_install.py`
- `plugins/cursor/cli_smoke.py`
- `docs/project/slash-command-surface.md`
- `docs/specs/plugin-runtime.spec.md`
- `docs/project/testing-and-install-gates.md`

不包含：

- `src/commands/start.py` / `analyse.py` / `review.py` 的业务行为重构
- Phase 3 采集、Phase 4 推理、Phase 5 报告质量优化
- Claude/Cursor installer 打包流程重构
- 新 agent 适配器
- CI 接入

## Current Observations

Claude 当前状态：

- 命令名已经稳定为 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate`。
- command markdown 使用 `${CLAUDE_PLUGIN_ROOT}` 和 `resolve-workspace.py` 定位安装态 runtime。
- `start` 的硬边界较完整，已限制裸远程、数据库客户端、安装命令和提前 analyse。
- `review` 和 `validate` 文档较短，但与主路径关系还可以更明确。

Cursor 当前状态：

- 命令文件投影为 `.cursor/commands/midstack:*.md`。
- command markdown 使用 workspace state 的 `runtime_root`。
- always-on rule 会影响非 slash 的自然语言请求，需要和 command markdown 保持同一套边界。
- `analyse` 文档承担了部分 Agent 推理/报告指导，后续要防止继续膨胀成控制面实现说明。
- Cursor `analyse` 文档中的 Agent-led 报告指导是技术债，现阶段保留以维持现有实测效果，后续应迁移到控制面编排模块。

共同风险：

- command markdown 是代码化提示，容易因为文案修改导致 Agent 跑错命令。
- Claude/Cursor 对同一命令的措辞不一致时，用户实际体验会漂移。
- CLI dispatcher 参数新增后，slash command 文档和测试可能没有同步。
- `validate` 是维护者命令，容易被误当成用户排障步骤。

## Command Contract

公共命令语义：

| 命令 | 用户语义 | Agent 首个动作 | 输出/下一步 |
| --- | --- | --- | --- |
| `/midstack:start` | 从自然语言线索创建或恢复 incident | 调安装态 `midstack-local.py start` | ready 时提示 `next run /midstack:analyse`；blocked 时只汇报阻断项 |
| `/midstack:analyse` | 分析当前或指定 incident | 调安装态 `midstack-local.py analyse` | 成功后总结 `analysis.yaml` / `report.md`；blocked 时停止 |
| `/midstack:review` | 对已有分析做质量评分 | 调安装态 `midstack-local.py review` | 输出五维评分，不作为主路径必跑步骤 |
| `/midstack:validate` | 维护者检查安装态 runtime | 调安装态自检或 repo validator | 输出 pass/fail 和可行动失败项 |

Slash 命令与 5 阶段流程对应关系：

| 5 阶段 | 阶段职责 | Slash 入口 | 说明 |
| --- | --- | --- | --- |
| Phase 1 启动 | 建立 incident、解析线索、远端接入校验 | `/midstack:start` | Agent 只抽取参数并调用 runtime；不自行排障 |
| Phase 2 盘点 | namespace、对象、拓扑、auth hint | `/midstack:start` | 由 start runtime 内部完成，ready 后提示 analyse |
| Phase 3 采集治理 | remote run、fixture、recollection 输入治理 | `/midstack:analyse` | analyse 进入控制面后触发采集或读取已有 remote run |
| Phase 4 推理 | rules fallback、多轨推理、reasoning board | `/midstack:analyse` | analyse 内部阶段，不应由 slash command 直接实现 |
| Phase 5 收口 | finalize、review、report、score | `/midstack:analyse`、`/midstack:review` | analyse 产出结论和报告；review 只做质量反馈 |
| 维护者检查 | 安装态 runtime 与资产自检 | `/midstack:validate` | 不属于用户排障 5 阶段主路径 |

公共禁止项：

- 命令面不得引用源码 checkout、个人绝对路径或历史 `engine_root`。
- `start` 之前不得让 Agent 读取插件源码、扫描 incident、跑数据库客户端、安装依赖、裸 SSH 或裸 kubectl。
- `analyse` 之前不得让 Agent 自行连接 MongoDB、安装依赖或绕开 runtime 采集。
- 用户可见输出不得回显密码、token 或完整凭据。
- `review` 不得被描述为 `start -> analyse` 主路径的一环。

适配器差异：

- Claude 使用 `${CLAUDE_PLUGIN_ROOT}/runtime/bin/...` 和 `resolve-workspace.py`。
- Cursor 使用 `.cursor/midstack-triage.workspace.json` 的 `runtime_root` 和 workspace-local runtime。
- Cursor always-on rule 是常驻行为约束，必须比单个 command markdown 更保守。

## Proposed Slices

### Slice 1. 命令合同文档固化

目标：

- 将本计划中的公共命令语义同步到 `docs/specs/plugin-runtime.spec.md` 和测试门禁文档。
- 明确 `review` / `validate` 不是用户排障主路径。
- 新增独立 slash 命令文档，阐明 slash 与 5 阶段流程的对应关系。
- 记录 Cursor `analyse` Agent-led 报告指导的技术债，不在 M2 中迁移。

文件：

- `docs/project/slash-command-surface.md`
- `docs/specs/plugin-runtime.spec.md`
- `docs/project/testing-and-install-gates.md`

验收：

```bash
git diff --check
rg -n 'start -> analyse -> review|start.*analyse.*review|engine_root|/home/stephen/AI' docs/specs docs/project -S
```

### Slice 2. 公共命令合同测试增强

目标：

- 把 start/analyse/review/validate 的公共语义加入 `tests/plugins/install_contracts.py`。
- Claude/Cursor 测试复用同一套公共断言，只保留适配器专属差异。

文件：

- `tests/plugins/install_contracts.py`
- `tests/plugins/claude/test_claude_plugin_install.py`
- `tests/plugins/cursor/test_cursor_plugin_install.py`
- `plugins/cursor/cli_smoke.py`

验收：

```bash
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
git diff --check
```

### Slice 3. Claude/Cursor 命令文案对齐

目标：

- 对齐四个命令的用户语义、blocked 处理、凭据脱敏和下一步提示。
- 保留适配器路径差异，不追求逐字一致。

文件：

- `plugins/claude/commands/*.md`
- `plugins/cursor/commands/midstack:*.md`
- `plugins/cursor/rules/midstack-triage.mdc`

验收：

```bash
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 plugins/cursor/test-agent-cli.py
python3 tools/validators/validate-installed-adapters.py
git diff --check
```

### Slice 4. CLI dispatcher 参数合同校验

目标：

- 建立 slash command 文档与 `src/commands/plugin_cli.py` 子命令/关键参数的一致性测试。
- 防止 CLI 新增参数后 command markdown 漏同步。

文件：

- `src/commands/plugin_cli.py`
- `tests/plugins/install_contracts.py`
- `tests/plugins/claude/test_claude_plugin_install.py`
- `tests/plugins/cursor/test_cursor_plugin_install.py`

验收：

```bash
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 -m pytest tests/tools tests/shared tests/phases -q
git diff --check
```

### Slice 5. 安装态命令回归收口

目标：

- 使用 `tools/validators/validate-installed-adapters.py` 覆盖命令文案变化后的 Claude/Cursor 安装态行为。
- 必要时补最小命令 smoke，不做真实故障效果调优。

文件：

- `tools/validators/validate-installed-adapters.py`
- `docs/project/testing-and-install-gates.md`

验收：

```bash
python3 tools/validators/validate-installed-adapters.py
git diff --check
```

## Implementation Order

1. Slice 1：先把命令语义写进事实源和门禁文档。
2. Slice 2：先增强测试，再允许改命令文案。
3. Slice 3：对齐 Claude/Cursor command markdown 和 Cursor rule。
4. Slice 4：补 CLI dispatcher 参数合同测试。
5. Slice 5：安装态回归收口。

## Boundaries

Always:

- 每个 slice 独立提交。
- 改 command markdown 必须跑插件测试。
- 改命令文案后必须跑对应安装态 smoke。
- 保持 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate` 名称稳定。

Ask first:

- 新增、删除或重命名 slash command。
- 修改 `plugin_cli.py` 的公开参数语义。
- 把 Agent 推理/报告指导从 command markdown 移到 runtime 实现。
- 引入新的命令模板生成器。

Never:

- 让命令面依赖源码 checkout。
- 在命令面内实现业务推理或远程执行逻辑。
- 把 `review` 写成主路径必跑步骤。
- 在用户可见响应中输出明文密码或 token。

## Open Questions

1. 是否需要把 Claude/Cursor command markdown 进一步模板化，还是继续保持两套手写文档加公共测试？
2. Cursor `analyse` 文档中的 Agent-led 报告指导是否应该保留在命令面，还是后续迁入控制面编排模块的任务说明文件？
3. `/midstack:validate` 是否继续暴露给普通用户，还是在文档上明确标为维护者命令但保留入口？
