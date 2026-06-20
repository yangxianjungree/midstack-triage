---
status: stable
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Architecture

## 运行时概览

Midstack 通过 3 条 slash 命令串起 5 段排障流程，并把运行时职责拆成控制面、执行面和后续可扩展的经验回灌路径。

详细图示见 [Midstack 架构图](architecture-overview.md)。

### 命令与阶段映射

| 用户命令 | 执行阶段 | 输出 |
|---------|---------|------|
| `/midstack:start` | Phase 1-2 | `ready` 或 `blocked`（含指导） |
| `/midstack:analyse` | Phase 3-5 | 结构化诊断报告 |
| `/midstack:review` | 反馈收集 | 评分与改进建议 |

### 架构要点

**控制面（Control Plane）**：
- 负责：流程编排、状态管理、推理诊断、报告生成、知识沉淀
- Phase 2 决策点：根据环境检查结果判断 `ready` 或 `blocked`
- Phase 3 & 4：按需调度执行面进行证据采集

**执行面（Execution Plane）**：
- 负责：远程环境接入、只读脚本执行、证据采集与回传
- 触发时机：Phase 3（主要采集）、Phase 4（补充验证）
- 执行合同：`context-file` + `output-file` + `artifact-dir`

**未来：检索增强层（规划中）**：
- 向量数据库存储历史事件和领域资产
- Phase 4 推理时检索相似案例作为参考
- Phase 5 和 review 的输出回灌知识库

### Phase 4 推理产物边界

当前 `/midstack:analyse` 的生产 `conclusion_summary` 由 `src/phases/phase4/rules/<middleware>.py` 的 rules fallback analyzer 生成，并经过 guardrails 修正后用于 `report.md`、`review` 和后续 finalize。

`src/phases/phase4/multitrack/` 是第 4 段多轨推理实现。它会写入 `reasoning-board.yaml` 和 `analysis.multitrack.yaml`；analyse 主链路会把其摘要写入 `analysis.yaml.agent_reasoning` 和 append-only `agent_multitrack` segment。生产结论默认由 rules fallback + guardrails 守底；只有通过 `agent_conclusion_gate` 的结构化候选结论才允许覆盖。

`agent-reasoning-task.md` 是人工或 Agent refinement 合同。默认安装命令不在 slash command 层自由改写 `analysis.yaml` / `report.md`；如需人工或 Agent refinement，应作为显式后续动作，并由 `finalize-analysis` 追加 reasoning segment。

Phase 4 的 `analysis.yaml` 顶层契约字段由 `src/phases/phase4/analysis_contract.py` 统一生成，包括 `retrieval_context`、`experience_matches`、`deep_analysis_requests` 和 `source_boundaries`。这些字段用于未来历史经验/向量召回、深入层请求和来源边界治理；历史经验不能直接作为当前故障结论证据。

因此，新中间件如果要进入 `/midstack:analyse` 生产路径，短期需要：

- 在 `domains/<product>/` 补齐领域资产、脚本、runbook、skill、command。
- 在 `src/phases/phase4/rules/<middleware>.py` 补 rules analyzer，或明确该中间件仍是 skeleton / 非生产 analyse 支持状态。
- 保持 `analysis.yaml` schema 与 incident record spec 兼容。

## 目标

本仓库用于沉淀中间件生产排障资产，并将这些资产组织为可被 Agent 和插件消费的标准化知识。

目录设计遵循三个原则：

- 单一事实来源
- 不重复存放
- 不提前抽象

## 相关文档

| 文档 | 内容 |
|---|---|
| [Midstack 架构图](architecture-overview.md) | 排障运行时：slash 命令、控制面 / 执行面、五段流程（概念图） |
| [排障流程概览](triage-workflow.md) | 五段流程文字说明 |
| [双平面运行时决策](../decisions/2026-06-14-dual-plane-runtime-architecture.md) | control plane / execution plane 代码分层 |

## 三层结构

### 1. 共性层

共性层放在 `core/` 和 `docs/`。

- `docs/` 负责规则说明、资产规范、接口约定
- `core/models/` 负责元数据模型
- `core/templates/` 负责模板
- `core/taxonomies/` 负责通用分类和枚举
- `core/shared/` 负责跨中间件复用的基础诊断能力

### 2. 领域层

领域层放在 `domains/`，按具体中间件拆分。

例如：

- `domains/mongodb/`
- `domains/redis/`
- `domains/kafka/`

每个领域目录只放该中间件专属资产，包括：

- `metadata.yaml`
- `commands/`
- `scripts/`
- `skills/`
- `runbooks/`

### 3. 场景层

场景层放在 `scenarios/`，按跨中间件可复用的故障场景拆分。

例如：

- `scenarios/connection-failure/`
- `scenarios/resource-exhaustion/`
- `scenarios/replica-inconsistency/`
- `scenarios/latency-spike/`
- `scenarios/data-hotspot/`
- `scenarios/kubernetes-runtime/`

场景层只定义场景本身，不存具体产品的 runbook、脚本或命令。

## 职责边界

### `scenarios/`

`scenarios/` 负责：

- 场景命名
- 场景定义
- 标签和检索
- 跨中间件路由入口

`scenarios/` 不负责：

- 某个具体中间件的排查步骤
- 产品专属命令
- 产品专属脚本

### `domains/<product>/`

`domains/<product>/` 负责：

- 该产品的组件模型
- 该产品的命令、脚本、技能
- 该产品的 runbook

runbook 只在这里存一份，通过 metadata 关联到 `scenario`。

其中 `scripts/` 当前应理解为：

- 脚本资产源文件目录
- 供维护、评审、复用和打包使用
- 不是插件安装后的直接运行目录
- 当前建议每个中间件在 `scripts/` 下维护一份 `manifest.yaml`，统一登记可打包脚本资产

### `core/shared/`

`core/shared/` 只允许放跨两个以上中间件可以直接复用的能力，不允许出现具体中间件专属知识。

四类目录的边界如下：

- `shell/`：通用 shell 片段、命令拼装约定、输出解析约定
- `kubernetes/`：Pod、Node、Container、PVC、Event 等 K8s 基础诊断能力
- `linux/`：CPU、内存、磁盘、网络、进程、文件句柄、IO 等 OS 层诊断能力
- `observability/`：日志、指标、链路、告警等观测方法和证据链约定

如果某个内容中显式依赖 `redis-cli`、`mongosh`、`kafka-topics.sh` 等产品专属工具，则不应进入 `core/shared/`。

### `interfaces/`

`interfaces/` 只放给外部适配器消费的接口定义；Claude Code、Codex、Cursor 等厂商适配器的源实现放在 `plugins/<agent>/`。

`.cursor/`、`.claude/` 等目录只代表某个目标项目的安装投影，不作为本仓库插件源目录。当前 Cursor 源实现放在 `plugins/cursor/`，测试时安装到 `/home/stephen/AI/` 下的临时项目或固定 sandbox 项目的 `.cursor/`。

这样可以保持：

- 知识层和执行层解耦
- 仓库不绑定单一厂商
- 适配器实现可以独立演进

## Remote Executor

当前建议把远程执行能力明确建模为 `remote executor`。本节只讲设计动机与职责边界；请求/结果模型、错误分类、远程目录等运行时合同以[插件运行时规范](../specs/plugin-runtime.spec.md) §11 为准。

职责边界：

- `remote executor`
  - 接收环境 IP、账号、密码、端口等接入信息
  - 默认使用第一个 IP 作为跳板入口
  - 建立远程连接
  - 验证远程环境中的基础控制工具，例如 `kubectl`
  - 验证基础 Kubernetes 操作能力，例如 `kubectl exec`
  - 将脚本、`context-file`、输出路径和产物目录组织到远程环境
  - 在远程环境执行脚本
  - 将 `output-file` 和 `artifact-dir` 回传给插件运行时
- `script`
  - 只负责采集和治理逻辑
  - 不负责 SSH 登录、跳板机选择或凭据管理

工具位置原则：

- `kubectl` 这类控制工具通常要求远程执行环境可用
- `mongosh`、`redis-cli`、`kafka-topics.sh` 这类中间件工具默认按 Pod 内工具处理
- 中间件命令优先通过 `kubectl exec` 在目标 Pod 内执行，而不是假设 K8s 节点或跳板机本地存在这些工具

设计原则：

- 排障命令可以远程执行，但远程执行逻辑不应散落在各个脚本中
- 脚本层和执行层解耦，才能跨 Claude Code、Codex、Cursor 复用
- 第一版默认第一个 IP 作为跳板入口，其他 IP 作为候选入口
- `remote executor` 应有独立的请求和结果模型，供不同插件适配器复用
- 执行层错误要和脚本采集状态分开表达，避免把 SSH、`kubectl`、脚本合同失败混成同一类问题
- 远程根目录建议使用 `/tmp/<plugin_name>/`
- 脚本应先按运行时相对路径投放到跳板机，再在远程执行目录中运行
- 单次执行目录建议按 `incident_id` 和 `script_id` 隔离，避免多脚本产物互相覆盖

## 脚本资产与插件运行时边界

当前已明确区分两类脚本位置：

1. 主仓库脚本资产
   - 位于 `domains/<product>/scripts/`
   - 作为单一事实来源维护
   - 用于评审、复用、版本管理和插件打包
2. 插件包运行时脚本
   - 位于各厂商插件自己的包内目录
   - 由插件构建或发布流程从主仓库脚本资产复制或打包生成
   - 作为插件安装后的真实执行对象

设计原则：

- 插件安装后不应直接依赖主仓库源码路径
- 插件运行时只访问自己包内的脚本
- 主仓库继续作为脚本资产的单一事实来源
- 各插件按自身标准决定包内落点，但应保持脚本 ID 和能力语义一致

当前不建议第一版采用以下方式：

- 运行时动态查找用户本地主仓库路径
- 要求用户额外配置仓库源码目录
- 插件安装后再临时下载脚本资产

## 脚本资产清单组织

manifest 字段与打包流程的规范定义见[插件运行时规范](../specs/plugin-runtime.spec.md) §9。当前建议采用“单中间件一个 manifest”的方式：

```text
domains/mongodb/scripts/
  manifest.yaml
  collect/
  normalize/
  helpers/
```

设计原则：

- `manifest.yaml` 负责登记该中间件下可被插件打包和调用的脚本入口
- `helpers/` 中的共享脚本默认不进入 `manifest.yaml`，除非它本身也是可直接执行入口
- 第一版不为每个脚本单独维护一份 `metadata.yaml`
- 第一版先保证 manifest 足够支持打包和运行时映射，不提前做重型建模

## runbook 组织规则

runbook 只存一份。

- 物理存储：按组件组织
- 逻辑检索：按场景组织

以 MongoDB 为例：

```text
domains/mongodb/runbooks/
└── replica-set/
    └── replica-member-not-healthy/
        ├── metadata.yaml
        └── runbook.md
```

其中 `metadata.yaml` 需要同时声明：

- `middleware`
- `component`
- `scenario`

这样既能支持按组件浏览，也能支持按场景检索，不需要复制第二份目录。
