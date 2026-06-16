# Midstack Triage

把中间件生产排障经验，做成 Agent 可安装、可执行、可持续迭代的插件能力。

Midstack 面向 PaaS 中间件生产故障，目标并非构建另一套监控系统，也不会默认代客执行生产变更，而是将“受理客户线索之后，如何确认环境、如何取证、如何推理、如何形成可复核结论”收敛为一套稳定的运行时和知识体系。

## 为什么做这个项目

生产排障的高成本，通常并非源于命令执行能力不足，而是以下问题长期缺乏产品化支撑：

- 客户上报的初始线索往往不完整、口径不一，故障现象、影响对象和影响范围常混在同一描述里
- 取证动作分散在聊天记录、历史脚本、个人经验与现场判断中，缺少统一编排
- 同类问题反复从初始步骤排查，却难以沉淀结构化证据链
- Agent 可生成分析文本，但若缺少可信证据输入，结论往往难以复核、容易失真

Midstack 旨在填补这一空白：从告警触发或故障报告受理，到产出可交接、可复盘、可继续验证的诊断结果。

## 工作原理

Midstack 当前对外保持 3 个主命令：

- `/midstack:start`：受理原始线索，确认环境入口，建立 incident，给出 `ready / blocked`
- `/midstack:analyse`：执行采集、推理、验证，输出分析结果和报告
- `/midstack:review`：收集评分与反馈，用于后续优化

运行时拆成两层：

- **控制面**：编排 5 段排障流程，管理状态，驱动第 4 段推理和第 5 段结论整合
- **执行面**：负责远端接入、只读脚本执行、证据采集、结果回传

![Midstack 架构图](docs/concepts/diagrams/architecture-overview.svg)

知识沉淀通过 `knowledge_candidates` 回灌，后续可以接入规则检索或向量数据库，但这不是第一版的前置依赖。

架构图、第 4 段展开图和图解说明见 [架构概览](docs/concepts/architecture-overview.md)；整体设计见 [架构设计](docs/concepts/architecture.md)。

## 5 段排障流程

| Phase | 名称 | 作用 |
| --- | --- | --- |
| 1 | 受理与启动 | 保存原始线索，创建排障记录 |
| 2 | 环境确认与对象盘点 | 确认目标环境、部署对象和本次排障范围 |
| 3 | 信号采集与治理 | 执行只读采集，做时间对齐、对象关联、降噪和汇总 |
| 4 | 推理诊断与深入验证 | 多假设推理、验证动作生成、结论收敛 |
| 5 | 结论整合与知识沉淀 | 输出报告、建议和知识候选 |

流程解释见 [docs/concepts/triage-workflow.md](docs/concepts/triage-workflow.md)。

## 快速体验

### 安装到 Claude sandbox

```bash
python3 plugins/claude/plugin-install.py install --workspace /path/to/sandbox
python3 plugins/claude/plugin-install.py check --workspace /path/to/sandbox
```

### 安装到 Cursor 工作区

```bash
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /path/to/workspace
python3 plugins/cursor/plugin-install.py --check-workspace /path/to/workspace
```

安装或升级后，**重新加载 Cursor**（Reload Window），否则已打开的工作区可能不会加载新的 slash 命令投影。

### 在已安装的工作区中执行

完成上述安装后，在 **已安装插件的目标工作区** 中打开 Agent 会话（Claude sandbox 或 Cursor 项目），再依次执行：

```text
/midstack:start <环境入口> 环境的 mongo 节点可能有问题，凭据 <user>/<password>，请帮我排查
/midstack:analyse
/midstack:review
```

命令仅在安装投影所在的工作区内可用；若在未安装的工作区中打开 Agent，将无法识别 `/midstack:*` 命令。

将 `<环境入口>`、`<user>`、`<password>` 替换为测试环境值；勿在聊天记录中暴露生产凭据。

如果 `/midstack:start` 返回 `blocked`，先补齐入口、凭据或环境信息，再重新启动。

## 当前落地情况

| 方向 | 状态 | 说明 |
| --- | --- | --- |
| MongoDB | Active MVP | 已打通 `start -> analyse -> review` 主路径；第 3 段只读采集脚本已形成第一批 MVP |
| Claude Code 插件 | 可用 | bundled runtime 打包、安装、自检和 sandbox 测试；不依赖 sandbox 内再 checkout 源仓库 |
| Cursor 适配器 | 可用但未完全独立 | 当前仍通过 workspace `engine_root` 调用源仓库入口 |
| Pulsar | Skeleton | 结构和样例已在，正式分析链路未完成 |

**已验证成果**：

- 第 4 段多轨推理正式实现已收敛到 `src/phases/phase4/multitrack/`
- MongoDB fixture replay 与本地评分链路已打通，用于回归 analyse 效果
- analyse 结果已能输出结构化报告与知识沉淀候选

完整实现清单见 [docs/project/implementation-status.md](docs/project/implementation-status.md)。

## 仓库结构

```text
midstack-triage/
├── docs/                         概念、规范、项目状态与提案
├── src/
│   ├── commands/                 slash 命令与编排入口
│   ├── phases/                   5 段 control plane
│   ├── execution/                execution plane
│   └── shared/                   跨阶段复用能力
├── core/                         模型、模板、taxonomy 与共享诊断能力
├── domains/
│   ├── mongodb/                  MongoDB 专属资产
│   └── pulsar/                   Pulsar 领域样例
├── scenarios/                    跨中间件标准场景定义
├── interfaces/                   跨适配器接口定义与示例合同
├── plugins/
│   ├── claude/                   Claude Code 插件与 bundled runtime
│   └── cursor/                   Cursor 投影适配器
├── tools/                        校验、回放、生成与工程工具
└── tests/                        集成测试、fixture 与 golden path
```

## 文档入口

- [docs/README.md](docs/README.md)：文档地图和权威分层
- [docs/concepts/architecture-overview.md](docs/concepts/architecture-overview.md)：整体架构图和第 4 段展开图
- [docs/concepts/triage-workflow.md](docs/concepts/triage-workflow.md)：5 段流程解释
- [docs/specs/plugin-runtime.spec.md](docs/specs/plugin-runtime.spec.md)：插件运行时合同
- [docs/project/implementation-status.md](docs/project/implementation-status.md)：实现进展

## 设计边界

- 不承担监控告警系统职责
- 不承担中间件控制面职责
- 默认不执行高风险生产变更
- 不将能力绑定于单一 Agent 平台

## 本地校验

```bash
python3 tools/validators/validate-repo.py
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

