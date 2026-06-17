---
status: draft
last_updated: 2026-06-17
supersedes: none
superseded_by: none
related:
  - ../2026-06-17-module-refactor-roadmap/spec.md
  - ../../project/testing-and-install-gates.md
---

# Plan: 插件安装部署模块整改

## Objective

优先治理“插件安装部署模块”，让 Claude/Cursor 安装、更新、部署、验证形成稳定、可重复、可测试的工程能力。

本阶段不优化 analyse 排障效果；只处理安装部署、命令面、runtime payload、workspace state 和 sandbox 门禁。

## Success Criteria

1. Claude/Cursor installer 的职责边界清晰：build / project / install / check / smoke 可被单独理解和测试。
2. 安装态 runtime payload 完整性检查可解释、可扩展。
3. workspace state 合同明确，不再出现历史 `engine_root` 模式回退。
4. command markdown / rules 的行为合同有自动化测试保护。
5. sandbox smoke 能覆盖真实安装态路径，而不是只覆盖源码态。
6. Claude/Cursor 共同安装合同、共同禁止项和共同检查口径有单一说明入口，避免只修一个适配器。
7. README / plugin README / testing gate 文档与实现保持一致。

## Scope

包含：

- `plugins/claude/plugin-install.py`
- `plugins/claude/runtime/bin/*`
- `plugins/claude/commands/*.md`
- `plugins/cursor/plugin-install.py`
- `plugins/cursor/commands/*`
- `plugins/cursor/rules/*`
- `plugins/cursor/cli_smoke.py`
- `plugins/cursor/test-agent-cli.py`
- `plugins/cursor/test-sandbox.py`
- `tests/plugins/claude/`
- `tests/plugins/cursor/`
- `plugins/README.md`
- `plugins/claude/README.md`
- `plugins/cursor/README.md`
- `docs/project/testing-and-install-gates.md`

不包含：

- `src/commands/analyse.py` 行为优化
- Phase 3 / Phase 4 排障效果优化
- MongoDB 领域资产治理
- 新 agent 平台适配
- CI 平台接入

## Current Observations

Claude 当前状态：

- 使用 plugin-local bundled runtime。
- installer 已能 build sandbox-local marketplace、purge project state、安装/enable 插件、运行 selfcheck。
- 近期修复了 command markdown 过软、`pwd` 解析到插件 runtime 目录的问题。
- `plugin-install.py` 文件较大，职责集中。

Cursor 当前状态：

- 使用 workspace-local runtime。
- installer 已能复制 command/rule/runtime payload 到目标 workspace。
- check-workspace 已检查 `runtime_root`、runtime marker、命令/rule projection。
- `cli_smoke.py` 已覆盖临时 workspace 和固定 sandbox，但 installer 同样较大。

共同风险：

- 安装器继续膨胀，新增逻辑难以定位。
- Claude/Cursor 两套 runtime marker 和禁止项检查存在重复但未抽象。
- 命令面属于“代码化提示”，容易被文案改动破坏。
- sandbox smoke 依赖本机环境，缺少更清晰的轻/重门禁分层。

## Shared Contract

Claude 和 Cursor 的安装形态不同，但必须遵守同一组公共合同。公共内容先沉淀为合同、测试 helper 和文档规范；只有当重复实现稳定后，再考虑抽成公共 Python 包。

公共合同：

- 安装态 runtime 必须自包含，不依赖源码 checkout、`tools/plugin/midstack-local.py` 或固定仓库路径。
- 安装态必须能定位用户 workspace，所有 incident 输出必须进入 workspace `.local/incidents/`。
- workspace state 只能记录安装态运行所需字段，不允许回退到历史 `engine_root` 语义。
- slash command / rules 只能调用安装态 runtime wrapper，不允许引导 Agent 自行执行 `mongosh`、`pip install`、裸 `ssh` 等诊断动作。
- 每个适配器必须提供 install / update / check / smoke 的可验证路径。

公共检查项：

- runtime marker 和入口脚本存在。
- command contract 不包含禁止 token。
- workspace state 不包含历史字段。
- smoke 运行路径不在源码 checkout 内。
- sandbox 输出路径不在插件 runtime 内。

公共文档规范：

- `plugins/README.md` 说明跨适配器安装合同和目录边界。
- `plugins/<agent>/README.md` 只说明该 agent 的安装命令、安装态目录、验证命令和已知限制。
- `docs/project/testing-and-install-gates.md` 维护轻/重门禁矩阵，以及哪些命令必须在源码仓库运行、哪些必须在 sandbox workspace 运行。
- 新增 agent 适配器时，必须先补该 agent README、安装态 check、sandbox smoke，再声明可用。

## Proposed Slices

### Slice 1. 安装部署合同文档固化

目标：

- 明确 Claude/Cursor 安装态目录结构、workspace state、runtime marker、禁止回退信号。
- 将“安装部署模块”的事实从 proposal 同步到稳定文档入口。
- 补充跨适配器公共合同和文档规范，作为后续 Claude/Cursor 重构的约束。

文件：

- `docs/project/testing-and-install-gates.md`
- `plugins/README.md`
- `plugins/claude/README.md`
- `plugins/cursor/README.md`

验收：

```bash
git diff --check
rg -n 'engine_root|source-checkout|cd .*/midstack-triage|tools/plugin/midstack-local.py' plugins/claude/commands plugins/cursor/commands plugins/cursor/rules -S
```

### Slice 2. Claude installer 结构整理

目标：

- 在不改变行为的前提下，将 `plugin-install.py` 内部职责拆成清晰函数组。
- 保持命令行接口不变。

建议子边界：

- source validation
- marketplace build
- project cleanup
- plugin install/update/enable
- installed payload check
- installed runtime smoke

文件：

- `plugins/claude/plugin-install.py`
- `tests/plugins/claude/test_claude_plugin_install.py`

验收：

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 -m pytest tests/plugins/claude/test_claude_plugin_install.py -q
python3 plugins/claude/plugin-install.py install --workspace "$SANDBOX"
python3 plugins/claude/plugin-install.py check --workspace "$SANDBOX"
cd "$SANDBOX" && claude -p "/midstack:validate" --allowedTools "Bash(python3 *)"
git diff --check
```

### Slice 3. Cursor installer 结构整理

目标：

- 在不改变行为的前提下，将 `plugin-install.py` 内部职责拆成清晰函数组。
- 保持命令行接口不变。

建议子边界：

- manifest/license validation
- local plugin link
- workspace runtime staging
- command/rule projection
- workspace state write
- workspace check

文件：

- `plugins/cursor/plugin-install.py`
- `plugins/cursor/cli_smoke.py`
- `tests/plugins/cursor/test_cursor_plugin_install.py`

验收：

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 -m pytest tests/plugins/cursor/test_cursor_plugin_install.py -q
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init "$SANDBOX"
python3 plugins/cursor/plugin-install.py --check-workspace "$SANDBOX"
python3 plugins/cursor/test-agent-cli.py
python3 plugins/cursor/test-sandbox.py "$SANDBOX"
git diff --check
```

### Slice 4. 跨适配器安装态门禁对齐

目标：

- 对齐 Claude/Cursor 的共同检查项，减少“一个适配器修了，另一个遗漏”的概率。
- 将重复检查沉淀为测试 helper 或 validator 片段；不急于抽公共安装库。

共同检查项：

- runtime payload marker
- command contract forbidden tokens
- workspace state 禁止历史字段
- output root 不进入插件 runtime 目录
- installed runtime smoke 不依赖源码 checkout

文件：

- `tests/plugins/claude/test_claude_plugin_install.py`
- `tests/plugins/cursor/test_cursor_plugin_install.py`
- `plugins/cursor/cli_smoke.py`
- `docs/project/testing-and-install-gates.md`

验收：

```bash
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 tools/validators/validate-repo.py
git diff --check
```

### Slice 5. Sandbox 回归脚本化收口

目标：

- 将当前人工执行的 Claude/Cursor sandbox 回归步骤收敛为明确命令集合。
- 暂不接入 CI，只让本地维护者能一条清单跑完。
- 如 Slice 4 已形成稳定公共检查，再决定是否抽统一 validator。

候选方案：

- 新增 `tools/validators/validate-installed-adapters.py`
- 或先只增强 `docs/project/testing-and-install-gates.md`，不新增脚本

建议先不新增脚本，等 Slice 2-4 完成后再决定是否有必要。

## Implementation Order

推荐顺序：

1. Slice 1：先固化合同和文档，避免重构时边界漂移。
2. Slice 2：Claude installer 整理。Claude 已是官方插件基线，先稳它。
3. Slice 3：Cursor installer 整理。对齐 Claude 的组织方式，但保留 workspace-local runtime 特性。
4. Slice 4：跨适配器门禁对齐。
5. Slice 5：根据实际重复命令决定是否脚本化 sandbox 回归。

## Boundaries

Always:

- 每个 slice 独立提交。
- 每个 slice 保持现有 CLI 接口兼容。
- 改 installer 必须跑对应安装态 check。
- 改 command markdown 必须跑对应 command contract 测试。
- 新增或修改适配器安装行为时，必须同步公共安装合同文档。

Ask first:

- 拆出新 Python 包或公共安装库。
- 将公共检查从测试 helper 提升为正式 validator 命令。
- 修改 Claude/Cursor 命令名称。
- 修改 workspace state 文件名或字段语义。
- 新增 CI 或外部依赖。

Never:

- 让安装态依赖源码 checkout。
- 把 sandbox `.claude/`、`.cursor/`、`.local/` 投影提交到仓库。
- 用只跑源码态测试替代安装态 smoke。
- 在本阶段修改 analyse 排障策略或结论逻辑。

## Decisions

1. Slice 2/3 第一轮不拆新 Python 包，先在现有 `plugin-install.py` 内按职责分组；如果文件仍然过大，再单独立拆包 proposal。
2. Slice 4 先抽公共测试 helper 或 validator 片段，不直接新增统一命令；等 Claude/Cursor 检查项稳定后再决定是否提供 `tools/validators/validate-installed-adapters.py`。
3. 固定 sandbox 采用当前仓库的兄弟目录 `../midstack-sandbox`；旧 sandbox 不再作为回归目标。
