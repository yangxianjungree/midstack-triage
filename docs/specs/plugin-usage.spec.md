---
status: authoritative
last_updated: 2026-06-14
supersedes: none
superseded_by: none
---

# Plugin Usage Spec

本文件用于确认插件对外使用方式的当前规范。

## 1. 总体原则

插件对外应保持少量、稳定、易理解的主入口命令。

说明：

- `/<plugin_name>` 表示插件名称前缀占位
- 实际命令形态应为 `/<plugin_name>:start`、`/<plugin_name>:analyse`、`/<plugin_name>:review`
- 当前 Claude 与 Cursor 适配器都使用 `/midstack` 作为命令前缀

当前对外保留 3 个面向用户的主命令：

- `/midstack:start`
- `/midstack:analyse`
- `/midstack:review`

此外保留 1 个工程自检命令 `/midstack:validate`，仅用于资产校验、replay、score gate 和适配器自检，不属于用户排障主路径。

内部仍然映射到项目的 5 段排障主流程，但对用户不暴露过多内部细节。

运行时说明：

- Claude 适配器安装后运行 plugin-local bundled runtime
- Cursor 适配器安装后运行 workspace-local runtime
- 两者对外命令面保持一致，均收敛为 `/midstack:*`

## 2. 插件命令与排障主流程对应表

当前插件命令与 5 段排障主流程的对应关系如下：

| 插件命令 | 对应流程阶段 | 主要职责 | 主要输出 |
|---|---|---|---|
| `/<plugin_name>:start` | 第 1 段 `受理与启动` + 第 2 段 `环境确认与对象盘点` | 收集最小输入、保存原始线索、验证环境可达性、判定 `ready / blocked`、完成基础环境和对象确认 | `ready / blocked` 状态、最小接入信息、前置环境确认结果 |
| `/<plugin_name>:analyse` | 第 3 段 `信号采集与治理` + 第 4 段 `推理诊断与深入验证` + 第 5 段 `结论整合与知识沉淀` | 采集和治理信号、生成并验证多条假设、形成阶段性结论、生成知识沉淀候选 | `structured_record`、`signal_bundle`、`collection_report`、阶段性结论、知识沉淀候选 |
| `/<plugin_name>:review` | 不直接对应用户排障主路径，属于插件反馈闭环 | 对插件当前排障表现做评价、打分、反馈，服务于开发者、DBA 和维护者持续优化插件能力 | 质量评分、评分原因、改进建议 |

### 结论

面向用户的对外命令保持 3 个：

- `/<plugin_name>:start`
- `/<plugin_name>:analyse`
- `/<plugin_name>:review`

其中：

- `start` 负责把排障启动起来，并完成前两段基础工作
- `analyse` 负责跑完正式分析主路径，并直接产出结论
- `review` 不面向最终用户结果输出，而面向插件优化反馈闭环
## 3. `/midstack:start`

### 目标

- 启动一轮新的排障
- 引导用户输入最小必填信息
- 进入第 1 段和第 2 段
- 判断当前状态是 `ready` 还是 `blocked`

### 输入

必填：

- 中间件类型
- 环境 IP
- 账号
- 密码

可选（高价值，建议提供）：

- 客户提供的原始故障线索

可选：

- 端口
- namespace
- cluster_id

> 参数定义与默认值以[插件运行时规范](plugin-runtime.spec.md) §6 为准。

### 行为

- 引导用户补齐最小输入
- 保存原始故障线索
- 尝试验证远程接入和基础 Kubernetes 能力
- 保存 incident 目录和本地忽略的远程配置
- 做环境确认与对象盘点的前置动作

### 输出

- 如果满足启动条件，输出 `ready`
- 如果不满足，输出 `blocked`

### `blocked` 时的行为

- 不结束流程
- 继续引导用户纠正或补充信息
- 明确指出当前阻塞项

### `ready` 时的行为

- 提示用户可执行 `/midstack:analyse`

## 4. `/midstack:analyse`

### 目标

- 进入第 3 段和第 4 段
- 执行信号采集与治理
- 执行多假设推理和验证
- 产出第 5 段的阶段性结论和知识沉淀候选

### 前置条件

- 当前排障记录状态为 `ready`，或为 `analysed`（基于已有记录继续分析）
- 状态校验与提示规则以[插件运行时规范](plugin-runtime.spec.md) §7 为准

### 行为

- 基于前面阶段已确认的信息继续分析
- 如果由 `/midstack:start` 产生 incident，则优先从该 incident 的 `remote-config.yaml` 调度真实只读采集
- 没有显式 `incident_id` 时，默认分析会话级当前目标记录；该记录的唯一定义见[插件运行时规范](plugin-runtime.spec.md) §4
- 前面阶段的基础输入和基础确认内容默认冻结，不再随意修改
- 由脚本负责采集、整理、标准化、结构化输出
- 由 Agent 负责假设生成、验证动作生成和阶段性判断

### 输出

至少包括：

- `structured_record`
- `signal_bundle`
- `collection_report`
- 阶段性分析结果
- 阶段性结论
- 面向用户的 `report.md`
- 知识沉淀候选

### 额外约定

- `/midstack:analyse` 执行完成后，应直接完成第 3、4、5 段
- 用户不需要再执行 `/midstack:review` 才能看到结论和报告

## 5. `/midstack:review`

### 目标

- 对插件当前排障表现做评价和打分
- 为插件开发者、DBA 和维护者提供反馈
- 支撑后续能力优化和迭代

### 行为

- 基于当前已有排障记录和分析结果做评价
- 没有显式 `incident_id` 时，默认 review 会话级当前目标记录（定义见[插件运行时规范](plugin-runtime.spec.md) §4）；可 review 的状态集合以其 §7 为准
- 不负责重新执行完整分析流程
- 不作为面向最终用户的结论输出入口

### 输出

至少包括：

1. 质量评分
2. 评分原因
3. 改进建议

### 评分维度

当前建议评分维度包括：

- `evidence_completeness`
- `hypothesis_coverage`
- `validation_depth`
- `conclusion_confidence`
- `knowledge_reusability`

### 评分方式

当前建议每个维度先采用：

- `high`
- `medium`
- `low`

并附一条简短原因说明。

模板：

- [core/templates/review.template.yaml](../../core/templates/review.template.yaml)

## 6. 命令之间的关系

当前建议的标准使用路径为：

1. 执行 `/midstack:start`
2. 在 `ready` 后执行 `/midstack:analyse`
3. 在需要对插件效果做反馈和评分时执行 `/midstack:review`

## 7. 命令输出合同

插件命令返回给用户或 Agent 平台的内容应是摘要输出，不直接承载完整 incident 记录。

当前建议：

- 详细证据、信号、采集报告和分析结果写入 incident 目录
- 命令输出只包含状态、摘要、用户提示、记录引用、下一步动作、阻塞项和告警
- `/midstack:start` 的输出状态主要是 `ready` 或 `blocked`
- `/midstack:analyse` 的输出状态主要是 `completed`、`blocked` 或 `failed`
- `/midstack:review` 的输出状态主要是 `completed` 或 `failed`

轻量合同模型：

- [core/models/adapter-output.schema.yaml](../../core/models/adapter-output.schema.yaml)

接口样例：

- [interfaces/plugin/adapter-output.example.yaml](../../interfaces/plugin/adapter-output.example.yaml)

## 8. 设计结论

### 为什么不合并 `/midstack:start` 和 `/midstack:analyse`

因为两者职责不同：

- `/midstack:start` 负责启动、建档、判定 `ready / blocked`
- `/midstack:analyse` 负责正式进入分析和验证

强行合并会模糊状态边界，不利于用户理解，也不利于插件内部控制流程。

### 为什么保留 `/midstack:review`

虽然 `/midstack:analyse` 已直接产出结论和报告，但仍建议保留 `/midstack:review`，因为它适合：

- 对插件排障效果做反馈
- 对分析质量做评分
- 收集改进建议
- 为插件开发者和 DBA 提供优化依据
