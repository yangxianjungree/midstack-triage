---
status: draft
last_updated: 2026-06-17
supersedes: none
superseded_by: none
---

# Spec: 模块盘点与逐模块整改路线

## Objective

梳理 Midstack 当前模块边界，为后续按模块逐个优化、整改、重构建立共同地图。

本规格不直接要求改代码。成功标准是：

- 能说清每个模块的职责、输入输出、依赖方向和安装态边界。
- 能识别哪些模块适合先治理，哪些模块应等上游边界稳定后再动。
- 后续每个模块整改都能从本文派生独立 proposal / plan / tasks。

## Assumptions

1. “模块”按维护边界和运行时职责划分，不等同于顶层目录。
2. `src/` 是正式 runtime 实现，凡是 Claude/Cursor 安装态需要执行的代码都应在 `src/` 或被明确打包为 runtime payload。
3. `tools/` 是工程侧入口、校验、回放、导入、生成，不作为长期 runtime 主实现。
4. `domains/`、`core/`、`scenarios/`、`interfaces/` 是资产与合同，不应混入适配器私有逻辑。
5. Claude/Cursor 当前都应满足安装态不依赖源码 checkout。

## Commands

模块盘点与后续整改的常用验证入口：

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 tools/validators/validate-repo.py
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 -m pytest tests/execution tests/phases tests/shared tests/tools -q
python3 plugins/claude/plugin-install.py install --workspace "$SANDBOX"
python3 plugins/claude/plugin-install.py check --workspace "$SANDBOX"
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init "$SANDBOX"
python3 plugins/cursor/plugin-install.py --check-workspace "$SANDBOX"
python3 plugins/cursor/test-agent-cli.py
python3 plugins/cursor/test-sandbox.py "$SANDBOX"
git diff --check
```

安装和 sandbox 门禁详见 [测试与安装门禁](../../project/testing-and-install-gates.md)。

## Project Structure

当前仓库可按以下模块族理解：

```text
src/             正式 runtime 实现
core/            模型、模板、taxonomy、共享资产
domains/         中间件领域资产
scenarios/       跨中间件场景定义
interfaces/      外部适配器接口合同
plugins/         Agent 平台适配器
tools/           工程入口、校验、回放、生成、导入
tests/           测试、fixture、golden path、score
docs/            规范、概念、项目状态、决策归档
examples/        示例和演示
.claude/.cursor  本仓库自身 agent 辅助配置，不是 Midstack 插件安装投影
```

## Module Map

本轮模块划分按“工程能力域”组织，而不是按目录机械拆分。每个一级模块对应一类可独立治理的能力；二级模块再映射到当前目录、主要风险和后续整改方向。

### M1. 插件安装部署模块

目标：让 Claude、Cursor 以及后续 agent 宿主都能稳定安装、更新、卸载、验证 Midstack runtime，并保证安装态不依赖源码 checkout。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Claude installer | `plugins/claude/plugin-install.py` | 构建 sandbox-local marketplace、安装/更新/enable 插件、清理旧会话、安装后检查 |
| Claude bundled runtime | `plugins/claude/runtime/` | Claude 安装态 runtime wrapper、自检、workspace resolver |
| Cursor installer | `plugins/cursor/plugin-install.py` | 链接本地插件、投影 commands/rules、复制 workspace-local runtime、检查 workspace |
| Cursor runtime projection | `.cursor/midstack-triage-runtime/`（安装产物） | Cursor 安装态运行时 payload |
| 安装态 workspace state | `.claude/*.json`、`.cursor/*.json`（目标 workspace） | 记录版本、runtime root、marketplace root、输出根 |

当前风险：

- installer 文件较大，安装、打包、校验逻辑混在一起。
- Claude/Cursor 的安装态行为容易被 command markdown 或 workspace cwd 影响。
- 需要持续防止 `engine_root`、源码 checkout、插件 runtime 内 `.local` 输出等回归。

整改方向：

- 将 installer 内的 build / install / check / smoke 分层。
- 保持安装态门禁为最高优先级。
- 提炼跨适配器一致的 runtime marker 和 dependency boundary 检查。

### M2. Slash 命令与 Agent 命令面模块

目标：稳定 `/midstack:start`、`/midstack:analyse`、`/midstack:review`、`/midstack:validate` 的用户入口和 Agent 执行合同。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Claude command markdown | `plugins/claude/commands/*.md` | Claude slash command 行为合同，必须使用 `${CLAUDE_PLUGIN_ROOT}` |
| Cursor command markdown | `plugins/cursor/commands/midstack:*.md` | Cursor slash command 行为合同，必须使用 workspace-local runtime |
| Cursor always-on rule | `plugins/cursor/rules/midstack-triage.mdc` | Cursor Agent 行为约束 |
| 本地 CLI 入口 | `tools/plugin/midstack-local.py` | 维护者本地调试入口，薄壳 |
| runtime CLI dispatcher | `src/commands/plugin_cli.py` | 将子命令路由到 start/analyse/review/finalize |

当前风险：

- command markdown 是“代码化提示”，测试不充分时会导致 Agent 自行跑 `mongosh/pip/ssh`。
- Claude 和 Cursor 的命令写法不同，但对外语义必须一致。
- `validate` 是工程命令，不应混入用户排障主路径。

整改方向：

- 把 slash command contract 作为可测试资产。
- 建立 Claude/Cursor 命令面一致性检查。
- 保持命令面只做入口约束，不承载复杂业务逻辑。

### M3. 控制面编排模块

目标：承载 5 段排障主流程的本地控制逻辑，负责状态推进、阶段调度、推理、报告和知识沉淀，不直接处理远端 transport。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Command orchestration | `src/commands/start.py`、`analyse.py`、`review.py`、`finalize.py` | 命令级编排和 adapter output |
| Phase 1 启动 | `src/phases/phase1/` | 启动门面、基础环境检查入口 |
| Phase 2 盘点 | `src/phases/phase2/` | namespace、对象、拓扑、auth hint |
| Phase 3 采集治理 | `src/phases/phase3/` | remote run / fixture / recollection 输入治理 |
| Phase 4 推理 | `src/phases/phase4/` | rules fallback、多轨推理、reasoning board |
| Phase 5 收口 | `src/phases/phase5/` | finalize、review、report、score |

当前风险：

- `src/commands/analyse.py`、`phase3/collection.py`、`phase4/rules/mongodb.py` 较大。
- 控制面和执行面已经分离，但部分逻辑边界仍可能交叉。
- Phase 4 rules fallback 与 multitrack 的职责关系还需要更清晰。

整改方向：

- 第一批优先梳理 `src/commands/analyse.py`，明确它只做编排。
- 第二批拆 Phase 3 collection 的输入类型和采集结果治理。
- 第三批梳理 Phase 4 rules fallback 与 multitrack 的边界。

### M4. 执行面模块

目标：负责本地控制端到跳板机/故障环境的远程执行，包含接入、能力检查、脚本投放、执行、结果回收和错误归一化。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Remote access | `src/execution/remote/access.py` | SSH/SSHPass、scp、基础连接 |
| Capability detection | `src/execution/remote/capabilities.py` | kubectl、pod exec、目标工具、脚本 target 探测 |
| Context building | `src/execution/remote/context.py` | 构造远端脚本上下文 |
| Executor contracts | `src/execution/remote/contracts.py`、`core/models/remote-executor-*.schema.yaml` | request/result 合同 |
| Executor orchestration | `src/execution/remote/executor.py` | 脚本投放、批量执行、产物回收 |
| Middleware runtime helpers | `src/execution/remote/mongodb_collection_runtime.py` | MongoDB 采集运行辅助 |
| Runtime support | `src/execution/remote/runtime_support.py` | runtime root、配置加载、路径辅助 |

当前风险：

- `capabilities.py` 和 `executor.py` 复杂度较高。
- 执行失败、blocked、script failed、evidence gap 的语义会影响最终分析可信度。
- 真机回归成本高，但不能只靠离线 fixture。

整改方向：

- 抽清 “接入检查 / 目标探测 / 脚本执行 / 结果归一化” 四层。
- 优先加强 remote-executor contract 测试。
- 每次执行面重构必须明确是否需要真实远程回归。

### M5. 模型、合同与 Taxonomy 模块

目标：维护项目的 L1 事实源，避免字段、状态、风险、场景等定义散落在实现和文档中。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Schema models | `core/models/` | adapter-output、script、runbook、skill、remote executor 等 schema |
| Templates | `core/templates/` | analysis、review、runbook、skill 等模板 |
| Taxonomies | `core/taxonomies/` | 状态、风险、能力、场景、候选类型 |
| Routing model | `core/routing/` | signal 到 scenario 的路由基础 |
| Shared diagnostic assets | `core/shared/` | 跨中间件基础诊断资产 |
| Runtime specs | `docs/specs/` | 命令、运行时、incident、asset reference 等规范 |

当前风险：

- 部分 schema 只是 YAML 文件，自动校验强度有限。
- runtime 中仍可能出现平行字段定义。
- 修改字段/状态时容易忘记同步 fixtures 和 validators。

整改方向：

- 先强化高频合同：adapter-output、remote-executor、script manifest、analysis/review。
- 让 validator 直接消费 L1，而不是复制字段清单。
- 字段变更必须先改 core/spec，再改实现。

### M6. 领域资产模块

目标：组织 MongoDB、Pulsar 以及后续中间件的领域知识、脚本、技能、runbook 和示例。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| MongoDB assets | `domains/mongodb/` | 当前 Active MVP 领域资产 |
| Pulsar assets | `domains/pulsar/` | Skeleton 领域资产 |
| Scripts | `domains/*/scripts/` | 第 3 段采集脚本资产源文件和 manifest |
| Skills / runbooks / commands | `domains/*/{skills,runbooks,commands}/` | 领域知识和操作指导 |
| Components / examples | `domains/*/{components,examples}/` | 组件索引和样例 |

当前风险：

- MongoDB 资产增长后可能出现组件组织和场景组织混杂。
- Pulsar Skeleton 需要避免被误认为可用链路。
- scripts manifest 与 runtime map 是安装态关键资产，不能漂移。

整改方向：

- 优先治理 MongoDB 资产导航、manifest、脚本合同。
- 明确 Pulsar 当前状态和门禁。
- 领域资产不得引用具体 agent 适配器路径。

### M7. 场景与知识检索模块

目标：定义跨中间件场景、signal routing、skill/runbook/command 解析，以及未来向量检索或经验库接入点。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Scenario definitions | `scenarios/*/scenario.yaml` | 跨中间件场景定义 |
| Scenario routing | `src/shared/scenario_router.py`、`core/routing/scenario-signal-map.yaml` | signal 到 scenario 的映射 |
| Skill resolver | `src/shared/skill_resolver.py` | scenario 到领域 skill/runbook/command 的解析 |
| Knowledge candidates | `core/templates/knowledge-candidate.template.yaml`、analysis output | Phase 5 知识候选沉淀 |

当前风险：

- 为单个 fixture 点对点加路由会破坏泛化。
- skill/runbook/command 解析和报告输出耦合度需要控制。
- 向量数据库未来接入点尚未形成稳定边界。

整改方向：

- 先稳定 scenario taxonomy 和 signal map。
- 把向量检索视为后续扩展层，不提前侵入主 runtime。
- 以 fixture replay 和 score gate 检查场景路由退化。

### M8. 测试、回放与质量门禁模块

目标：用自动化证据支撑工程重构、安装部署和排障效果，不依赖用户手动试错发现问题。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Unit / integration tests | `tests/` | runtime、phase、plugin、tool 测试 |
| Fixtures | `tests/fixtures/` | 离线 replay 输入 |
| Golden paths | `tests/golden-paths/` | 最小合同样例 |
| Scores | `tests/scores/` | score gate 期望 |
| Replay tools | `tools/replay/` | fixture replay、freeze、score |
| Validators | `tools/validators/` | 仓库结构、资产合同、安装边界校验 |
| Install gates | `docs/project/testing-and-install-gates.md` | 安装态门禁说明 |

当前风险：

- 真实远程采集和 Agent 交互仍有手工环节。
- fixture hygiene 对历史内容和敏感信息仍需持续治理。
- 大 validator 文件后续可继续拆分。

整改方向：

- 每个模块整改前先列最小测试集。
- 增加安装态等价测试，避免源码态通过但 sandbox 失败。
- 分阶段治理 validator 结构，不影响门禁覆盖。

### M9. 工程工具模块

目标：维护仓库侧生成、导入、校验、回放和本地调试能力，支撑资产工程化。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Local plugin CLI | `tools/plugin/` | 本地调试入口薄壳 |
| Validators | `tools/validators/` | 工程门禁 |
| Replay | `tools/replay/` | 回放和评分 |
| Generators | `tools/generators/` | 资产骨架生成 |
| Importers | `tools/importers/` | Markdown 等外部资产导入 |
| Tool support | `tools/support/` | tools 内部辅助函数 |

当前风险：

- 工具层可能再次堆积运行时实现。
- validators 和 replay 有些文件已变大。

整改方向：

- 保持 `tools/` 调 `src/`，禁止 `src/` 依赖 `tools/`。
- 工程逻辑保留在 tools，不因为复用而塞进 runtime。
- 大工具按子领域拆模块。

### M10. 文档与治理模块

目标：保持规格、实现状态、架构说明、提案和历史记录分层清晰，避免文档成为错误实现依据。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| README | `README.md`、`README.zh.md` | 门面和快速入口（英文 / 中文） |
| Concepts | `docs/concepts/` | 架构解释 |
| Specs | `docs/specs/` | L1 事实源 |
| Project docs | `docs/project/` | 当前状态、计划、门禁 |
| Proposals | `docs/proposals/` | 待确认设计和重构方案 |
| Decisions | `docs/decisions/` | 历史归档，不作为当前依据 |

当前风险：

- 实现变更后 README/spec/status 容易不同步。
- 历史归档中旧描述容易被误读为当前事实。

整改方向：

- 每次重构先判断是否影响 L1。
- 提交前搜索旧路径、旧模式、旧状态词。
- 活文档只写当前事实，历史事实放 decisions。

### M11. 示例与开发辅助模块

目标：保留有助于理解和开发的示例与 agent skill，但不让它们混入 runtime 或安装投影。

子模块：

| 子模块 | 当前路径 | 职责 |
| --- | --- | --- |
| Examples | `examples/` | 演示和说明 |
| Claude dev skills | `.claude/skills/` | 本仓库开发辅助 |
| Cursor dev skills/rules | `.cursor/skills/`、`.cursor/rules/` | 本仓库开发辅助 |

当前风险：

- `examples/phase4/` 是否仍有维护价值需要确认。
- `.claude/.cursor` 容易和插件安装投影混淆。

整改方向：

- 明确 examples 的保留标准。
- 开发辅助 skill 不进入 runtime bundle。
- 本仓库 `.claude/.cursor` 不作为 Midstack 插件源目录。

## Suggested Refactor Order

按能力域建议如下：

1. 安装部署与命令面稳定性
   - 因为它直接决定 Claude/Cursor 是否可用。
   - 已经完成一轮治理，但后续改 command/installer 时仍应第一时间跑门禁。

2. Command Runtime
   - 先梳理 `src/commands/analyse.py`。
   - 目标是让命令层只做编排、路径、adapter output 和 phase 调度。

3. 控制面 Phase 3 / Phase 4
   - 拆 `phase3/collection.py` 和 `phase4/rules/mongodb.py`。
   - 这是 analyse 效果和可维护性的核心。

4. 执行面
   - 拆 `capabilities.py`、`executor.py`。
   - 需要更谨慎，因为牵涉真实远程环境和错误分类。

5. 模型合同与领域资产
   - 强化 schema / manifest / runtime map 校验。
   - 治理 MongoDB 资产导航和脚本合同。

6. 测试与门禁
   - 围绕上述模块补最小测试集和安装态等价测试。

7. 工程工具与文档治理
   - 分批整理 validators/replay/generators/importers。
   - 保持 README/spec/status 同步。
## Testing Strategy

每个模块整改前，先定义该模块的最小验证集。

通用基线：

```bash
git diff --check
python3 -m pytest <module-related-tests> -q
```

涉及 runtime 或跨模块行为：

```bash
python3 tools/validators/validate-repo.py
```

涉及 Claude/Cursor 适配器：

```bash
SANDBOX="$(realpath ../midstack-sandbox)"
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 plugins/claude/plugin-install.py install --workspace "$SANDBOX"
python3 plugins/claude/plugin-install.py check --workspace "$SANDBOX"
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init "$SANDBOX"
python3 plugins/cursor/plugin-install.py --check-workspace "$SANDBOX"
```

涉及排障效果：

```bash
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

## Boundaries

Always:

- 先按模块形成 proposal / plan，再做大改。
- 保持 `src/` 为安装态 runtime 实现边界。
- 保持 `tools/` 为工程侧边界。
- 改 adapter 必须跑安装态门禁。
- 改字段/状态/合同必须先更新 L1 事实源。

Ask first:

- 移动公开路径或改变导入路径。
- 改变 incident 文件结构。
- 改变 slash command 行为。
- 删除 examples、fixtures、legacy 文档或历史资产。
- 引入新依赖或外部服务。

Never:

- 让安装态重新依赖源码 checkout。
- 把真实凭据、现场原始敏感材料写入 fixtures。
- 在 phase 目录中堆远程 transport 主实现。
- 在 plugins 目录中堆通用 runtime 实现。
- 用文档替代测试门禁。

## Success Criteria

- 本文能作为后续逐模块整改的模块地图。
- 每个模块都有清晰职责、风险和建议整改方向。
- 用户确认第一批整改模块和优先级后，再进入具体计划和任务拆分。

## Open Questions

1. 第一批整改是否优先选择 `src/commands/analyse.py`，还是先处理 execution plane？
2. MongoDB analyse 效果不稳的问题，是放在 Phase 3/4 重构后处理，还是并行开一个质量专项？
3. Pulsar 当前保持 Skeleton 是否足够，还是要先明确“不可用”标记和门禁？
4. `examples/phase4/` 是否仍作为文档示例保留，还是后续归档到 decisions/examples？
