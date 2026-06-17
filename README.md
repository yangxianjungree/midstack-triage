# Midstack Triage

**中文** · [English](README.en.md)

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

- `/midstack:start`：受理原始线索，确认环境 IP 和远端接入信息，建立 incident，给出 `ready / blocked`
- `/midstack:analyse`：执行采集、推理、验证，默认分析当前 incident，输出分析结果和报告
- `/midstack:review`：基于本次分析结果自动生成五维评分、改进建议和风险提示，用于后续优化

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

以下命令默认在 `midstack-triage` 仓库根目录执行。

### 安装到 Claude sandbox

```bash
python3 plugins/claude/plugin-install.py install --workspace /path/to/sandbox
python3 plugins/claude/plugin-install.py check --workspace /path/to/sandbox
```

该命令面向 sandbox；默认会清理目标 workspace 的 Claude 项目历史。需要保留历史时，参考 [plugins/claude/README.md](plugins/claude/README.md) 使用 `--keep-project-state`。

### 安装到 Cursor 工作区

```bash
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /path/to/workspace
python3 plugins/cursor/plugin-install.py --check-workspace /path/to/workspace
```

安装或升级后，**重新加载 Cursor**（Reload Window），否则已打开的工作区可能不会加载新的 slash 命令投影。

Cursor 适配器会把 workspace-local runtime 安装到 `.cursor/midstack-triage-runtime/`，安装态不需要回调本仓库源码 checkout。

### 在已安装的工作区中执行

完成安装后，在 **已安装插件的目标工作区** 里打开 Agent 会话。

用自然语言描述故障即可，环境地址、凭据、客户原话可以写在同一条消息里：

```text
/midstack:start 192.168.1.10 环境的 MongoDB 副本集有节点异常，账号密码 root/example，客户反馈查询超时
/midstack:analyse
```

建议按下面顺序使用：

1. **`/midstack:start`** — 受理线索并确认环境；返回 `ready` 后继续，若提示 `blocked` 则按说明补全后重新执行
2. **`/midstack:analyse`** — 采集证据、完成分析并生成报告
3. **`/midstack:review`**（可选）— 对本次分析做质量评估

以上命令仅在已安装的工作区内可用。示例面向测试环境；`start` 会将凭据写入本地 incident 配置供后续 `analyse` 使用，生产环境建议使用临时凭据或后续 secret 引用机制。

## 当前落地情况

| 方向 | 状态 | 说明 |
| --- | --- | --- |
| MongoDB | Active MVP | 已打通 `start -> analyse` 主路径；`review` 用于质量反馈；第 3 段只读采集脚本已形成第一批 MVP |
| Claude Code 插件 | 可用 | bundled runtime 打包、安装、自检和 sandbox 测试；不依赖 sandbox 内再 checkout 源仓库 |
| Cursor 适配器 | 可用 | workspace-local runtime、命令/rule 投影、sandbox smoke 和安装态依赖检查已打通 |
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
- [docs/project/testing-and-install-gates.md](docs/project/testing-and-install-gates.md)：测试、安装与 sandbox 门禁

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

适配器安装自检与 `/midstack:validate` 见 [plugins/claude/README.md](plugins/claude/README.md)、[plugins/cursor/README.md](plugins/cursor/README.md)。

## 开源协议

本项目使用 [Apache License 2.0](LICENSE) 开源。
项目源头与再分发说明见 [NOTICE](NOTICE)。
