# Midstack Triage

面向 PaaS 中间件生产故障的自动排查插件与知识体系。

项目聚焦 MongoDB、Pulsar 等中间件，目标是将生产排障经验标准化、结构化和可执行化，沉淀为可复用的 `runbook`、命令、脚本、技能和 Agent 能力。

实现形式以 **Claude Code 插件官方标准** 为基线，同时兼容 `Cursor`、`Codex` 等其他 Agent 运行环境。

## 核心价值

- 标准化生产排障流程，减少临场排查的随意性
- 复用中间件专家经验，降低重复排障成本
- 结构化沉淀证据、假设、结论和知识资产
- 通过 metadata 模型让 runbook、command、skill 可检索、可校验、可组合
- 通过插件化方式让排障能力可接入、可复用、可持续迭代

## Scope

本项目当前聚焦以下能力范围：

- PaaS 中间件故障的自动化排查与诊断
- 面向生产环境的 `runbook` 编排与沉淀
- 面向中间件场景的命令、脚本、工具、知识和技能封装
- 将排障步骤组织为标准化插件能力，便于不同 Agent 平台复用
- 优先覆盖高频中间件与高频故障场景，逐步扩展支持面

## 非目标

本项目当前不以以下方向为目标：

- 不直接承担中间件托管控制面或资源编排职责
- 不默认执行高风险变更操作，优先提供只读诊断和风险提示
- 不追求一次性覆盖所有中间件或所有故障类型
- 不绑定单一厂商的 Agent 运行时实现，避免将能力写死在某个平台

## 设计理念

- 先诊断，后建议，最后才是处置
- 优先沉淀真实生产排障经验，而不是抽象化的空泛流程
- 所有关键步骤尽量可验证、可审计、可复现
- 保留原始线索，再做富化和推理
- 采用“共性骨架 + 中间件专属扩展”的结构设计
- 高风险操作必须显式确认
- 插件能力设计优先遵循官方标准，同时兼顾跨平台兼容性

## 稳定结论

以下内容属于当前已经收敛的稳定结论，应作为后续设计和实现的约束基线：

- 排障主流程固定为 5 段：
  - `受理与启动`
  - `环境确认与对象盘点`
  - `信号采集与治理`
  - `推理诊断与深入验证`
  - `结论整合与知识沉淀`
- 插件对外固定为 3 个面向用户的主命令（另有 1 个工程自检命令 `/<plugin_name>:validate`，不属于用户排障主路径）：
  - `/<plugin_name>:start`
  - `/<plugin_name>:analyse`
  - `/<plugin_name>:review`
- 仓库按“共性层 + 领域层 + 场景层”组织：
  - `core/` 与 `docs/` 承载共性规范和底座
  - `domains/` 承载具体中间件资产
  - `scenarios/` 承载跨中间件场景定义
- `scenarios/` 只定义场景，不存产品专属 `runbook`、命令或脚本
- `domains/<product>/` 只存具体中间件资产
- `runbook` 只存一份：
  - 物理上按组件组织
  - 逻辑上按场景检索
- 主仓库保留 `interfaces/` 中的跨适配器接口定义，也允许在 `plugins/<agent>/` 下保留厂商适配器源实现
- `.cursor/`、`.claude/` 等目录只视为目标项目的安装投影，不作为本仓库插件源目录
- 主仓库中的脚本属于资产源文件，插件安装后运行的脚本应由适配器明确映射和调用；当前本地 Cursor 集成通过 `plugins/cursor/` 调用主仓库工具链
- 脚本应使用稳定的 `script_id` 标识，当前最小规则为 `<middleware>.<phase>.<target>.<action>`
- 每个中间件的脚本资产应使用单独的 `manifest.yaml` 统一登记，不为每个脚本单独维护一份 metadata
- 脚本 `manifest.yaml` 已有轻量合同模型和最小校验
- 插件运行时应通过独立映射表将 `script_id` 映射到插件包内脚本路径
- 第 3 段脚本统一采用 `context-file + output-file + artifact-dir` 调用合同
- 远程执行属于 `remote executor`；它负责进入目标环境并执行脚本，脚本本身不内置 SSH 逻辑
- 中间件工具默认按 Pod 内工具处理，例如通过 `kubectl exec` 在目标 Pod 内执行 `mongosh`
- `remote executor` 需要使用独立请求/结果模型，区分执行层状态和脚本采集状态
- 远程执行器错误至少应区分 SSH、认证、`kubectl`、`kubectl exec`、目标 Pod、Pod 内工具、脚本合同和结果回收问题
- 远程执行器应将插件包内脚本投放到跳板机 `/tmp/<plugin_name>/` 下，再按 `incident_id/script_id` 创建单次执行目录
- 第 3 段脚本应优先使用 Python 标准库，兼容 Python 3.6，不默认依赖跳板机预装 `PyYAML`
- MongoDB MVP 第一批 11 个第 3 段脚本已完成合同级实现，并已通过真实 K8s 环境 smoke test
- 本地插件原型已能消费 fixture、incident 或已完成的 remote smoke 结果目录来验证 analyse/review 文件流转
- 本地插件原型已能通过 `.local` remote config 调度真实 MongoDB 只读采集并继续生成分析结果
- 本地插件 `review` 已能基于 `analysis.yaml` 生成五维评分和改进建议
- Cursor 集成源实现已收敛到 `plugins/cursor/`，可安装到临时 Cursor 项目并自动化 smoke test
- Cursor 集成测试以 `/home/stephen/AI/` 下的临时项目或固定 sandbox 项目为目标，不把 midstack 源码仓库自己的 `.cursor/` 当作安装结果
- 第 3 段 `context-file` / `output-file` 已有轻量合同模型和最小示例校验
- `script-runtime-map` 和 `remote executor` 请求/结果已有轻量合同模型和最小示例校验
- `runbook`、`command`、`skill` metadata 已有轻量合同模型和 MongoDB 样例校验
- `runbook`、`command`、`skill`、诊断检查单和事件总结已有核心模板
- 插件命令 `adapter output` 已有轻量合同模型和示例校验
- 风险等级、状态、场景类型、能力类型和标签规范已有共性枚举
- Kubernetes runtime 异常信号已有通用 taxonomy 和 validator，避免把故障分类做成单个案例的点对点规则
- 进入“稳定结论”的内容，必须同步更新 `README` 和对应 spec，不能只留在讨论文档中

## 总体架构

项目围绕 5 段排障主流程组织：

1. `受理与启动`
2. `环境确认与对象盘点`
3. `信号采集与治理`
4. `推理诊断与深入验证`
5. `结论整合与知识沉淀`

在执行方式上：

- 第 3 段以脚本为主，负责采集、整理、时间对齐、初步降噪和结构化输出
- 第 4 段以 Agent 为主，负责多假设推理、验证动作生成和阶段性结论整理
- 排障结果以结构化记录方式沉淀，便于后续继续分析和知识回灌

## 仓库结构

当前仓库按“共性层 + 领域层 + 场景层”组织：

- `docs/`：架构原则、资产规范、接口约定
- `core/`：模板、通用分类、共享诊断能力
- `scenarios/`：跨中间件的标准场景定义
- `domains/`：按具体中间件划分的专属资产
- `interfaces/`：给 Claude Code、Codex、Cursor 等适配器消费的接口定义
- `plugins/`：厂商适配器源实现，例如 `plugins/cursor/`
- `tools/`：校验、生成、导入工具

结构原则如下：

- `scenarios/` 只定义场景，不存产品专属 runbook
- `domains/<product>/` 只存具体中间件资产
- runbook 只存一份，物理上按组件组织，逻辑上按场景检索
- `interfaces/` 放跨适配器接口定义，`plugins/<agent>/` 放对应适配器源实现
- 源码仓库自己的 `.cursor/` 不承载 Midstack 插件安装投影；安装投影应写入目标 Cursor 项目的 `.cursor/`
- 主仓库中的脚本是资产源文件，适配器需要通过明确的映射和执行合同调用

## 插件使用方式

当前插件对外保持 3 个面向用户的主入口（另有工程自检命令 `/<plugin_name>:validate`）：

- `/<plugin_name>:start`
  启动一轮排障，完成输入收集、环境确认和 `ready / blocked` 判断
- `/<plugin_name>:analyse`
  跑完正式分析主路径，执行信号治理、推理验证，并直接产出结论和报告
- `/<plugin_name>:review`
  对插件排障效果做评价、打分和反馈，服务于后续优化

## 当前支持范围

- 第一版正式支持 `MongoDB`
- 当前 MongoDB 领域样例覆盖：
  - `replica-inconsistency`
  - `connection-failure`
  - `resource-exhaustion`
  - `latency-spike`
  - `data-hotspot`
  - `kubernetes-runtime`（运行时异常）
- MongoDB 第 3 段 MVP 脚本已覆盖：
  - Pod、StatefulSet、Service、Node 采集
  - Kubernetes Events 采集
  - mongos shard map 采集
  - replica set `rs.status()` 采集
  - 当前日志和 previous 日志采集
  - 日志 highlights
  - signal bundle 汇总
- `Pulsar` 当前只作为领域样例和结构验证样例
- 已形成排障主流程、插件使用方式和结构化记录的规范基线
- 已形成 MongoDB fixture replay 与本地评分闭环，用于减少只依赖人工反馈的优化滞后
- 已形成 MongoDB Kubernetes runtime 故障 fixtures，可在未知场景线索下回归验证通用 K8s runtime 分类能力
- MongoDB analyse runner 已能基于场景匹配已有 runbook、command、skill 作为知识沉淀候选
- 更多中间件、脚本能力和知识资产将持续补充

## 本地校验

校验 MongoDB 脚本资产、插件接口示例和知识资产 metadata：

```bash
python3 tools/validators/validate-repo.py
```

只校验 MongoDB 资产合同：

```bash
python3 tools/validators/validate-mongodb-scripts.py
```

使用真实 K8s 环境做 MongoDB 远程 smoke test 时，配置文件应放在 `.local/` 下，避免敏感信息进入仓库：

```bash
python3 tools/remote-smoke/mongodb-smoke.py --config .local/test-envs/mongodb-k8s.yaml
```

运行 MongoDB fixture replay 和本地评分：

```bash
python3 tools/replay/mongodb-freeze-fixture.py --remote-run-dir .local/remote-runs/<incident_id> --fixture-dir .local/fixtures/mongodb/<case_id> --case-id <case_id> --scenario baseline
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
python3 tools/replay/mongodb-score-summary.py --score-root .local/scores/mongodb
```

验证 Cursor MCP 集成：

```bash
python3 plugins/cursor/test-mcp-server.py
python3 plugins/cursor/test-sandbox.py
python3 tools/validators/validate-repo.py
```

安装到一个目标 Cursor 项目：

```bash
python3 plugins/cursor/install.py --target-dir /home/stephen/AI/<target-project>
python3 plugins/cursor/install.py --target-dir /home/stephen/AI/<target-project> --check
```

## 文档导航

完整文档地图与权威分层规则见 [docs/README.md](docs/README.md)。常用入口：

- 概念与架构：
  - [架构设计](docs/concepts/architecture.md)
  - [排障流程概览](docs/concepts/triage-workflow.md)
  - [信号治理模式](docs/concepts/signal-governance.md)
- 规范（唯一事实源）：
  - [排障流程规范](docs/specs/triage-workflow.spec.md)
  - [插件使用规范](docs/specs/plugin-usage.spec.md)
  - [插件运行时规范](docs/specs/plugin-runtime.spec.md)
  - [Analyse MVP 规范](docs/specs/analyse-mvp.spec.md)
  - [单次排障记录规范](docs/specs/incident-record.spec.md)
  - [增量合并规范](docs/specs/incident-patch-merge.spec.md)
  - [跨资产引用规范](docs/specs/asset-reference.spec.md)
  - [Runbook 规范](docs/specs/runbook.spec.md)
  - [Command 规范](docs/specs/command.spec.md)
  - [Skill 规范](docs/specs/skill.spec.md)
- 项目管理：
  - [实施计划](docs/project/implementation-plan.md)
  - [TODO](docs/project/todo.md)
- 分析与参考：
  - [领域记录对照](docs/analysis/domain-record-comparison.md)
  - [外部参考资料](docs/references.md)
  - [汇报材料](docs/presentation.md)
- 历史决策（已归档，非权威）：
  - [排障流程讨论](docs/decisions/triage-workflow-discussion.md)
  - [讨论归档](docs/decisions/discussions-archive.md)
- 共性底座：
  - [模型目录](core/models/README.md)
  - [模板目录](core/templates/README.md)
  - [分类目录](core/taxonomies/README.md)
- 工具与测试：
  - [Cursor 集成](plugins/cursor/README.md)
  - [资产校验工具](tools/validators/README.md)
  - [远程 smoke 工具](tools/remote-smoke/README.md)
  - [Replay 工具](tools/replay/README.md)
  - [Analyse 工具](tools/analyse/README.md)
  - [Golden path 测试](tests/golden-paths/README.md)
  - [测试闭环目录](tests/README.md)
