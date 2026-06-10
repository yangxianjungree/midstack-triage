---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Plugin Runtime Spec

本文件用于沉淀插件实现前已经确认的运行时规则，作为编码前的统一基线。

相关文档：

- [docs/PLUGIN_USAGE_SPEC.md](plugin-usage.spec.md)
- [docs/INCIDENT_RECORD_SPEC.md](incident-record.spec.md)
- [docs/TRIAGE_WORKFLOW_SPEC.md](triage-workflow.spec.md)
- [docs/DISCUSSIONS.md](../decisions/discussions-archive.md)

## 1. 命令模型

当前插件对外保留 3 个面向用户的主命令：

- `/<plugin_name>:start`
- `/<plugin_name>:analyse`
- `/<plugin_name>:review`

此外保留 1 个工程自检命令 `/<plugin_name>:validate`，仅用于资产校验、replay、score gate 和 MCP smoke 自检，不属于用户排障主路径。

说明：

- `/<plugin_name>` 仅作为插件名称前缀占位
- 实际命令形态应替换为真实插件名；当前 Cursor 集成使用 `/midstack`

## 2. 命令与流程映射

| 命令 | 对应流程 | 主要职责 |
|---|---|---|
| `/<plugin_name>:start` | 第 1、2 段 | 启动排障、收集最小输入、判断 `ready / blocked`、完成基础环境确认 |
| `/<plugin_name>:analyse` | 第 3、4、5 段 | 执行信号治理、推理验证、输出结论和知识沉淀候选 |
| `/<plugin_name>:review` | 插件反馈闭环 | 对插件当前排障表现做评分、原因说明和改进建议 |

## 3. `incident_id` 规则

当前采用格式：

`<middleware>-<YYYYMMDD>-<HHMMSS>-<rand4>`

示例：

- `mongodb-20260607-213045-a7k2`
- `pulsar-20260607-213112-m4q9`

约束：

- 同时满足唯一性和可读性
- 不将 `cluster_id` 纳入 `incident_id`
- 应在 `/start` 阶段即可生成

## 4. 会话级当前目标记录

当前目标记录按会话级维护。

规则：

- `/plugin:start` 成功创建后，自动将新 `incident_id` 设为当前目标记录
- `/plugin:analyse` 显式传入 `incident_id` 时，切换当前目标记录
- `/plugin:review` 显式传入 `incident_id` 时，切换当前目标记录
- 无显式参数时，优先使用当前会话记忆里最近一次使用的目标记录

第一版约束：

- 不实现复杂的多记录切换命令
- 只保证最近 `start` 创建的记录和最近 `analyse` 完成的记录可被默认命中

## 5. 状态机

当前建议状态如下：

- `created`
- `blocked`
- `ready`
- `analysing`
- `analysed`
- `reviewed`
- `closed`

### 状态含义

- `created`
  - 已创建排障记录，但尚未完成启动校验
- `blocked`
  - 启动受阻，缺少条件或验证失败
- `ready`
  - 已满足启动条件，可进入分析
- `analysing`
  - 正在执行第 3、4、5 段
- `analysed`
  - 已完成一轮分析，已产出结论和报告
- `reviewed`
  - 已完成一次插件效果评价
- `closed`
  - 本次排障记录已结束，不再继续推进

### 主要迁移规则

- `/plugin:start`
  - 创建记录后进入 `created`
  - 校验失败进入 `blocked`
  - 校验成功进入 `ready`
- `/plugin:analyse`
  - 从 `ready` 进入 `analysing`
  - 完成后进入 `analysed`
- `/plugin:review`
  - 从 `analysed` 进入 `reviewed`
  - 不改变分析结论，只补充反馈结果

> 注：incident 记录状态机用 `analysed` 表示一轮分析已完成；而 adapter 输出合同（见 plugin-usage.spec.md §7）用 `completed` 表示 `analyse` 命令本次成功返回。二者是不同字段——前者是 incident 生命周期状态，后者是单次命令输出状态。

## 6. 命令输入方式

### `/plugin:start`

采用“参数可选 + 交互补全”方式。

当前支持参数：

- `middleware`：必填
- `ips`：必填，支持一个或多个值
- `username`：必填
- `password`：必填
- `port`：可选，默认 `22`
- `clue`：可选，支持直接传客户原始故障线索

原则：

- 能直接传就直接传
- 传不全就交互补齐

### `/plugin:analyse`

第一版当前仅保留：

- `incident_id`：可选

规则：

- 无显式 `incident_id` 时，默认分析当前目标记录
- 如存在多个未结束 incident，优先命中当前会话最近目标记录

后续版本预留但暂不实现：

- `scope`
- `force_recollect`

### `/plugin:review`

第一版当前仅保留：

- `incident_id`：可选

规则：

- 无显式 `incident_id` 时，默认 review 当前会话里最近一次已分析的目标记录
- 第一版已实现基于 `analysis.yaml` 的五维评分与改进建议（原型级）

后续版本预留：

- `mode`

## 7. 命令状态校验与提示

### `/plugin:start`

- 不依赖当前目标记录
- 永远允许新建
- 成功创建后覆盖当前目标记录

### `/plugin:analyse`

无当前目标记录时：

- 提示：`当前没有可分析的 incident，请先执行 /plugin:start`

状态不匹配时：

- `blocked`
  - `当前 incident 仍处于 blocked，请先补齐或修正启动信息`
- `created`
  - `当前 incident 尚未完成启动校验，请先完成 start 阶段`
- `analysing`
  - `当前 incident 正在分析中，请等待完成或查看当前进度`
- `analysed`
  - 允许继续 analyse，并提示：
  - `当前 incident 已分析过，将基于已有记录继续分析`
- `closed`
  - `当前 incident 已关闭，请新建或显式指定其他 incident`

### `/plugin:review`

无当前目标记录时：

- 提示：`当前没有可 review 的 incident，请先完成一次 analyse`

状态不匹配时：

- `ready` / `blocked` / `created`
  - `当前 incident 尚未完成 analyse，无法执行 review`
- `analysing`
  - `当前 incident 仍在分析中，请待 analyse 完成后再执行 review`
- `analysed`
  - 允许 review
- `reviewed`
  - 允许再次 review，并提示：
  - `当前 incident 已有 review 记录，将追加或刷新 review 结果`
- `closed`
  - 默认允许 review 已关闭但已有 analyse 结果的历史 incident

## 8. MVP 范围

当前 MVP 范围如下：

- 第一版只正式支持 `MongoDB`
- `/plugin:review` 第一版已实现五维评分与改进建议原型
- `/plugin:analyse` 第一版覆盖：
  - Kubernetes 对象采集
  - 日志采集
  - 基础状态判断
  - 多假设生成
  - 阶段性结论输出

约束：

- 必须显式记录哪些能力尚未实现
- 不允许让用户误以为插件已实现全部已讨论能力

## 9. 脚本运行时来源与标识

当前运行时规则明确如下：

- `domains/<product>/scripts/` 中的脚本属于主仓库脚本资产源文件
- 插件安装后的运行脚本必须位于插件包内部
- 插件运行时不应直接依赖主仓库源码路径

当前建议流程：

1. 主仓库维护脚本资产源文件
2. 插件构建或发布流程选择需要的脚本
3. 将脚本复制或打包到插件包内部目录
4. 插件运行时按 `script_id` 或插件包内相对路径执行

### 最小 `script_id` 规则

当前建议采用：

`<middleware>.<phase>.<target>.<action>`

示例：

- `mongodb.collect.pods.state`
- `mongodb.collect.replicaset.rs_status`
- `mongodb.collect.logs.current`
- `mongodb.normalize.logs.highlights`
- `mongodb.normalize.signals.bundle`

使用原则：

- `script_id` 是稳定标识，不直接等同于源码路径
- 插件运行时应优先按 `script_id` 查找打包后的运行脚本
- 文件名、插件包内路径可以变化，但 `script_id` 应尽量保持稳定

第一版约束：

- 先不定义完整的脚本打包工具链
- 先不定义统一的插件包内目录结构
- 先不定义严格的脚本 manifest schema
- 但必须明确“源码资产路径”和“运行时执行路径”不是同一个概念

### 最小脚本 manifest 方案

当前建议每个中间件在 `domains/<product>/scripts/` 下维护一份 `manifest.yaml`。

示例目录：

```text
domains/mongodb/scripts/
  manifest.yaml
  collect/
  normalize/
  helpers/
```

当前建议 `manifest.yaml` 使用“一个文件登记多个脚本”的方式，不为每个脚本单独建 metadata 文件。

最小字段集：

- `script_id`
- `source`
- `phase`
- `target`
- `action`
- `runtime`
- `readonly`
- `default_packaged`
- `mvp`

字段原则：

- `script_id`
  - 稳定标识
- `source`
  - 只表示主仓库中的脚本资产路径
  - 不表示插件安装后的执行路径
- `phase` / `target` / `action`
  - 表达脚本能力归属
- `runtime`
  - 表达解释器或运行方式，例如 `shell`、`python`
- `readonly`
  - 表达该脚本默认是否只读
- `default_packaged`
  - 表达插件默认是否应打包该脚本
- `mvp`
  - 表达该脚本是否属于第一版正式支持范围

打包时当前建议流程：

1. 读取 `manifest.yaml`
2. 选出 `default_packaged: true` 的脚本
3. 复制到插件包内部目录
4. 生成 `script_id -> plugin_relative_path` 的运行时映射
5. 插件执行时优先按 `script_id` 查找

轻量合同模型：

- [core/models/script-manifest.schema.yaml](../../core/models/script-manifest.schema.yaml)

### 插件侧最小运行时映射文件

当前建议插件包内维护一份独立映射文件，用于把 `script_id` 映射到真实运行路径。

建议文件名：

- `script-runtime-map.yaml`

建议作用：

- 作为插件运行时查找脚本的唯一入口
- 将主仓库中的脚本资产标识与插件包内实际落点解耦
- 避免插件执行逻辑直接依赖主仓库源码路径

当前建议最小字段：

- `plugin`
- `version`
- `generated_at`
- `scripts`

其中 `scripts` 下每条当前建议至少包括：

- `script_id`
- `runtime_path`
- `runtime`
- `readonly`

字段原则：

- `script_id`
  - 对应主仓库 manifest 中的稳定标识
- `runtime_path`
  - 表示插件包内部的相对路径
  - 不允许写主仓库源码路径
- `runtime`
  - 表示运行方式，例如 `shell`、`python`
- `readonly`
  - 表示该脚本在当前插件包中的默认风险属性

当前建议查询规则：

1. 插件收到某个 `script_id`
2. 从 `script-runtime-map.yaml` 中查找对应条目
3. 取出 `runtime_path`
4. 在插件包内部执行该路径对应脚本

轻量合同模型：

- [core/models/script-runtime-map.schema.yaml](../../core/models/script-runtime-map.schema.yaml)

当前不建议第一版：

- 插件直接根据 `script_id` 拼接源码目录路径
- 插件直接扫描包目录推断脚本含义
- 插件运行时再回查主仓库 manifest 作为唯一执行依据

## 10. 第 3 段脚本调用合同

当前建议第 3 段脚本统一采用以下调用方式：

```text
<script> --context-file <path> --output-file <path> --artifact-dir <path>
```

### 最小输入合同

当前建议所有第 3 段脚本都接收：

- `--context-file`
  - 指向插件运行时生成的 YAML 上下文文件
- `--output-file`
  - 指向脚本应写入的 YAML 结果文件
- `--artifact-dir`
  - 指向脚本保存附属产物的目录

### `context-file` 的最小公共字段

当前建议至少包括：

- `incident_id`
- `middleware`
- `script_id`
- `namespace`
- `cluster_id`
- `artifact_root`

说明：

- 以上是最小公共字段
- 不同中间件和不同脚本可以在此基础上增加领域字段
- 第一版不强制把所有领域字段都抽成统一 schema

轻量合同模型：

- [core/models/script-context.schema.yaml](../../core/models/script-context.schema.yaml)

### MongoDB 基础采集脚本的共享 `context-file` 字段

当前建议 MongoDB 第一批基础采集脚本在最小公共字段之外，补充以下共享字段：

- `deployment_architecture`
- `topology_type`
- `access`
- `targets`
- `capabilities`

字段建议：

- `deployment_architecture`
  - 例如 `bitnami`
  - 例如 `operator_crd`
- `topology_type`
  - 第一版 MongoDB 当前主要取值为 `sharded_cluster`
- `access`
  - 建议至少包括：
    - `primary_ip`
    - `candidate_ips`
    - `username`
    - `password`
    - `port`
- `targets`
  - 用于表达当前已知目标对象
  - 建议至少包括：
    - `namespace`
    - `statefulset_refs`
    - `service_refs`
    - `pod_refs`
    - `node_refs`
    - `mongos_pod_ref`
- `capabilities`
  - 用于表达插件运行时已经确认的环境能力
  - 建议至少包括：
    - `kubectl_available`
    - `kubectl_exec_available`
    - `mongosh_in_pod_available`

### MongoDB 5 个基础采集脚本的专属 `context-file` 字段

#### `mongodb.collect.pods.state`

建议额外关注：

- `targets.statefulset_refs`
- `targets.pod_refs`
- `pod_query.mode`

其中 `pod_query.mode` 当前建议取值：

- `by_statefulset`
- `by_pod_refs`
- `by_namespace_scan`

#### `mongodb.collect.statefulsets.yaml`

建议额外关注：

- `targets.statefulset_refs`
- `statefulset_query.include_yaml`

第一版当前建议 `include_yaml: true`。

#### `mongodb.collect.services.yaml`

建议额外关注：

- `targets.service_refs`
- `service_query.include_nodeport`

第一版当前建议 `include_nodeport: true`。

#### `mongodb.collect.nodes.state`

建议额外关注：

- `targets.node_refs`
- `node_query.resolve_from_pods`

第一版当前建议：

- 优先使用 `targets.node_refs`
- 若为空，则允许从当前已识别 Pod 反推节点

#### `mongodb.collect.mongos.get_shard_map`

建议额外关注：

- `targets.mongos_pod_ref`
- `mongos_query.shell`
- `mongos_query.database`
- `mongos_query.command`
- `mongos_query.username`
- `mongos_query.password`
- `mongos_query.password_env`
- `mongos_query.password_file_env`
- `mongos_query.auth_database`
- `mongos_query.secret_ref`

第一版当前建议默认值：

- `mongos_query.shell: mongosh`
- `mongos_query.database: admin`
- `mongos_query.command: getShardMap`
- `mongos_query.auth_database: admin`

MongoDB 认证来源原则：

- MongoDB 运行命令通常需要认证信息，不应默认无认证
- Bitnami 部署优先从 Pod 内环境变量读取，例如 `MONGODB_ROOT_PASSWORD`
- operator+CRD 部署通常需要从 Kubernetes Secret 读取认证信息
- 第一版脚本先支持：
  - 明文 `mongos_query.password`
  - Pod 内环境变量 `mongos_query.password_env`
  - Pod 内密码文件环境变量 `mongos_query.password_file_env`
- `mongos_query.secret_ref` 作为 operator+CRD 方式的接口预留，后续实现
- 脚本输出、artifact 和日志中不应写入 MongoDB 密码

### `output-file` 的最小公共字段

当前建议至少包括：

- `script_id`
- `status`
- `summary`
- `started_at`
- `finished_at`
- `artifacts`
- `structured_record_patch`
- `signal_bundle_patch`
- `collection_report_patch`
- `warnings`
- `evidence_gaps`

字段原则：

- `script_id`
  - 对应本次脚本的稳定标识
- `status`
  - 当前只建议使用：
  - `success`
  - `partial`
  - `blocked`
- `structured_record_patch`
  - 表示脚本对 `structured_record.yaml` 的增量结果
- `signal_bundle_patch`
  - 主要给 `normalize/*` 脚本使用
- `collection_report_patch`
  - 表示本次采集动作、失败项、留白项和证据缺口的增量结果

轻量合同模型：

- [core/models/script-output.schema.yaml](../../core/models/script-output.schema.yaml)

### MongoDB `output-file` 示例约定

当前建议 MongoDB 第 3 段脚本的 `output-file` 采用“结果概览 + patch + 产物引用”的结构。

建议分块：

- `script_id`
- `status`
- `summary`
- `started_at`
- `finished_at`
- `artifacts`
- `structured_record_patch`
- `signal_bundle_patch`
- `collection_report_patch`
- `warnings`
- `evidence_gaps`

字段原则：

- `summary`
  - 一句话概述本次脚本拿到了什么、缺了什么
- `artifacts`
  - 只记录脚本写入 `artifact-dir` 的相对路径和用途
- `structured_record_patch`
  - 只放当前脚本负责的结构化增量
- `signal_bundle_patch`
  - `collect/*` 脚本通常可为空
- `collection_report_patch`
  - 必须明确采集动作、成功项、失败项和证据缺口

### MongoDB `mongos.get_shard_map` 示例结果

对于 `mongodb.collect.mongos.get_shard_map`，当前建议：

- `structured_record_patch`
  - 主要写入 `details.shard_map`
- `signal_bundle_patch`
  - 第一版可为空
- `collection_report_patch`
  - 记录 `mongos` 采集动作和结果

### 状态与退出码原则

当前建议：

- 当脚本按合同完成执行并成功写出 `output-file` 时，进程退出码为 `0`
- `success` / `partial` / `blocked` 通过 `output-file.status` 表达
- 非 `0` 退出码仅用于表示脚本自身执行失败或违反调用合同，例如：
  - 参数缺失
  - 无法写入结果文件
  - 运行时异常退出

这样可以避免将“采集到部分证据”误判成脚本执行失败。

### `stdout` / `stderr` 原则

当前建议：

- 机器可读结果只写 `output-file`
- `stdout` 只用于简短进度信息
- `stderr` 只用于错误提示和调试信息
- 插件运行时不应依赖解析 `stdout` 获取结构化结果

### 脚本运行时依赖原则

真实跳板机环境不应假设具备完整开发机依赖。

第一版建议：

- 第 3 段脚本优先使用 Python 标准库
- Python 脚本语法应兼容 Python 3.6
- 不默认依赖跳板机预装 `PyYAML`
- `context-file` 和 `output-file` 可以采用 JSON-compatible YAML
- 当远端存在 `PyYAML` 时可以读写常规 YAML
- 当远端不存在 `PyYAML` 时，脚本应至少能读写 JSON 格式的机器可读文件

设计原因：

- 生产跳板机通常只保证基础系统工具和 `kubectl`
- 额外 Python 包可能缺失，不能作为脚本运行前置条件
- JSON 是 YAML 的可读子集，适合作为无第三方依赖的降级格式

## 11. Remote Executor

当前建议把远程执行能力明确建模为 `remote executor`。

### 职责

- 接收 `/plugin:start` 收集到的环境信息
- 默认使用第一个 IP 作为跳板入口
- 验证 SSH 连通性
- 验证远程环境中的基础控制工具，例如 `kubectl`
- 验证基础 Kubernetes 操作能力，例如 `kubectl exec`
- 将脚本、`context-file`、`output-file` 路径和 `artifact-dir` 组织到远程环境
- 在远程环境执行脚本
- 拉回 `output-file` 和 `artifact-dir`

### 与脚本的关系

- `remote executor` 负责“怎么到远程环境里执行”
- 第 3 段脚本负责“到了远程环境以后做什么”
- 脚本本身不负责 SSH 登录、跳板机选择或凭据管理

### 工具位置原则

- `kubectl` 这类控制工具通常要求远程执行环境可用
- `mongosh`、`redis-cli`、`kafka-topics.sh` 这类中间件工具默认按 Pod 内工具处理
- 中间件命令优先通过 `kubectl exec` 在目标 Pod 内执行
- 不应假设 K8s 节点、跳板机或远程执行目录本地安装了全部中间件客户端工具

### 与插件命令的关系

- `/plugin:start`
  - 负责收集和验证远程环境信息
- `/plugin:analyse`
  - 通过 `remote executor` 调度第 3 段脚本
- `remote executor`
  - 作为插件运行时的执行层，而不是领域脚本的一部分

### 最小请求模型

`remote executor` 的请求模型用于表达“一次脚本远程执行任务”。

当前建议最小字段：

- `executor_id`
- `incident_id`
- `script_id`
- `middleware`
- `plugin_name`
- `access`
- `script`
- `remote_workspace`
- `required_capabilities`
- `execution`

字段原则：

- `access`
  - 来自 `/plugin:start` 收集到的环境信息
  - `candidate_ips` 支持多个入口 IP
  - `primary_ip` 第一版默认取第一个入口 IP
  - `port` 默认 `22`
- `script`
  - 使用插件包内运行时脚本路径，不使用主仓库源码路径
  - `runtime_path` 来自 `script-runtime-map.yaml`
  - `arguments` 必须能映射到第 3 段脚本合同
- `remote_workspace`
  - 表达远程环境中的临时工作目录和文件落点
  - 建议以 `/tmp/<plugin_name>/` 作为远程根目录
  - 脚本按插件包内相对路径投放到远程 `assets/scripts/` 下
  - 单次脚本执行以 `incident_id` 和 `script_id` 隔离运行目录
- `required_capabilities`
  - 表达执行前必须验证的能力
  - 第一版至少覆盖 `ssh`、`kubectl`、`kubectl_exec`
  - 中间件工具按 Pod 内工具表达，例如 `mongosh` 的 `execution` 为 `pod_internal`
- `execution`
  - 表达超时、是否回收 `output-file`、是否回收 `artifact-dir` 等执行控制项

接口样例：

- [interfaces/plugin/remote-executor-request.example.yaml](../../interfaces/plugin/remote-executor-request.example.yaml)

轻量合同模型：

- [core/models/remote-executor-request.schema.yaml](../../core/models/remote-executor-request.schema.yaml)

### 最小结果模型

`remote executor` 的结果模型用于表达“远程执行层是否成功完成调度、执行和回收”。

当前建议最小字段：

- `executor_id`
- `incident_id`
- `script_id`
- `status`
- `selected_ip`
- `started_at`
- `finished_at`
- `capability_checks`
- `remote_paths`
- `retrieved_files`
- `process`
- `error`
- `warnings`

字段原则：

- `status`
  - `success`：远程执行、脚本调用和结果回收均符合合同
  - `partial`：执行器完成主流程，但存在非阻塞缺口，例如部分 artifact 回收失败
  - `blocked`：执行前置条件不满足，例如 SSH 不通、缺少 `kubectl`、无法执行 `kubectl exec`
  - `failed`：执行器自身异常、脚本合同失败或无法判断结果是否有效
- `selected_ip`
  - 记录本次实际使用的入口 IP
- `capability_checks`
  - 记录每项能力检查的结果
  - 失败项应能映射到明确错误分类
- `retrieved_files`
  - 记录已回收到本地 incident 目录的文件位置
- `process.exit_code`
  - 记录脚本进程退出码
  - 不直接替代脚本 `output-file.status`

接口样例：

- [interfaces/plugin/remote-executor-result.example.yaml](../../interfaces/plugin/remote-executor-result.example.yaml)

轻量合同模型：

- [core/models/remote-executor-result.schema.yaml](../../core/models/remote-executor-result.schema.yaml)

### 状态边界

脚本 `output-file.status` 和 `remote executor.status` 是两个不同层级。

脚本状态：

- `success`
- `partial`
- `blocked`

远程执行器状态：

- `success`
- `partial`
- `blocked`
- `failed`

判断原则：

- 远程执行器只要无法进入环境、无法满足前置能力或无法完成脚本调用，应返回 `blocked` 或 `failed`
- 脚本成功写出有效 `output-file` 后，脚本内部采集状态由 `output-file.status` 表达
- 如果脚本进程退出码非 `0`，且没有有效 `output-file`，远程执行器应返回 `failed`
- 如果脚本进程退出码为 `0`，但 `output-file` 缺失或不符合合同，远程执行器也应返回 `failed`
- 如果脚本进程退出码为 `0`，且 `output-file.status: blocked`，远程执行器可以返回 `success`，因为执行层完成了合同

### 错误分类

第一版建议至少区分以下错误：

| 错误码 | 含义 | 建议状态 |
|---|---|---|
| `ssh_unreachable` | 所有入口 IP 均无法建立 SSH 连接 | `blocked` |
| `ssh_auth_failed` | SSH 认证失败 | `blocked` |
| `missing_sshpass` | 执行器依赖 `sshpass` 但本地缺失 | `blocked` |
| `kubectl_missing` | 远程环境缺少 `kubectl` | `blocked` |
| `k8s_context_unavailable` | 远程环境无法访问 Kubernetes 集群 | `blocked` |
| `kubectl_exec_unavailable` | 无法执行基础 `kubectl exec` | `blocked` |
| `target_pod_not_found` | 目标 Pod 不存在或无法定位 | `blocked` |
| `pod_tool_missing` | Pod 内缺少所需中间件工具，例如 `mongosh` | `blocked` |
| `script_runtime_failed` | 脚本进程非预期异常退出 | `failed` |
| `script_contract_failed` | 脚本未写出有效 `output-file` 或字段不符合合同 | `failed` |
| `output_retrieval_failed` | `output-file` 或产物回收失败 | `partial` 或 `failed` |

### 远程工作目录原则

第一版建议远程执行器先把插件包内脚本投放到跳板机，再在远程运行目录中执行。

远程根目录建议使用：

```text
/tmp/<plugin_name>/
```

脚本投放目录建议保持插件包内相对路径：

```text
/tmp/<plugin_name>/
  assets/
    scripts/
      mongodb/
        collect-pods-state.sh
        collect-statefulsets-yaml.sh
```

单次执行目录建议按 `incident_id` 和 `script_id` 隔离：

```text
/tmp/<plugin_name>/runs/<incident_id>/<script_id>/
  context.yaml
  output.yaml
  artifacts/
```

原则：

- 同一个 incident 下不同脚本互相隔离
- 远程 `script_path` 指向投放后的脚本路径，不指向主仓库源码路径
- `context-file`、`output-file` 和 `artifact-dir` 放在单次执行目录
- `context-file`、`output-file` 和 `artifact-dir` 均使用远程工作目录内路径
- 执行完成后必须回收 `output-file`
- `artifact-dir` 按需回收，回收失败时必须记录在执行器结果中
- 远程临时目录清理策略后续再定，第一版不强制自动删除

### 远程脚本投放流程

当前建议执行顺序：

1. 从 `script-runtime-map.yaml` 根据 `script_id` 找到插件包内 `runtime_path`
2. 在跳板机创建 `/tmp/<plugin_name>/assets/scripts/...`
3. 将脚本和必要 helper 文件投放到对应目录
4. 在跳板机创建 `/tmp/<plugin_name>/runs/<incident_id>/<script_id>/`
5. 写入本次执行的 `context.yaml`
6. 执行远程脚本，并传入远程 `context.yaml`、`output.yaml`、`artifacts/`
7. 回收 `output.yaml` 和 `artifacts/`

这样可以保证：

- 插件运行时不依赖用户本地主仓库路径
- 远程执行现场可定位、可复查
- 多脚本、多 incident 并发时不互相覆盖

## 12. 脚本测试与远程执行原则

当前建议把“脚本逻辑”和“远程执行”分层处理：

- 第 3 段脚本本身不负责 SSH 登录、跳板机选择或凭据管理
- 插件运行时或测试执行器负责进入远程环境
- 脚本只假定自己运行时已经处在远程执行环境中
- 脚本可以直接调用远程环境中的 `kubectl`
- 中间件客户端命令默认通过 `kubectl exec` 在目标 Pod 内调用

这样可以保持：

- 脚本合同稳定
- 脚本逻辑不和远程接入实现耦合
- Claude Code、Codex、Cursor 等不同适配器都可以复用同一套脚本

### 远程测试环境使用原则

当使用真实 K8s 环境做脚本验证时，当前建议：

1. 多个入口 IP 默认以第一个 IP 作为跳板入口
2. 真实账号密码不写入仓库文件
3. 本地测试配置只放在被忽略的本地目录，例如：
   - `.local/test-envs/mongodb-k8s.yaml`
4. 远程测试执行器负责：
   - SSH 连通性验证
   - 基础命令能力验证
   - 将脚本、`context-file`、输出路径和产物目录组织好
   - 在远程环境执行脚本
   - 将 `output-file` 和产物回传本地

### 远程测试最小步骤

当前建议最小步骤如下：

1. 验证 SSH 可达
2. 验证远程环境存在 `kubectl`
3. 验证基础 Kubernetes 操作可执行，例如 `kubectl exec`
4. 生成本次测试用的 `context-file`
5. 在远程环境执行目标脚本
6. 拉回 `output-file` 和 `artifact-dir`
7. 检查结果是否符合脚本合同

### 第一版测试通过判定

当前建议至少满足：

- 脚本进程退出码符合合同
- 成功生成 `output-file`
- `output-file.script_id` 正确
- `output-file.status` 合理
- `structured_record_patch` / `collection_report_patch` 至少有一项符合预期
- 产物引用路径存在且可读

### 第一版已实现能力清单

#### `/plugin:start`

- 接收启动输入
- 支持“参数可选 + 交互补全”
- 创建 `incident_id`
- 创建 incident 目录和基础文件
- 验证远程环境基础可达性
- 验证基础 Kubernetes 操作能力
- 判断并输出 `ready / blocked`
- 将新记录设为当前会话目标记录

#### `/plugin:analyse`

- 基于当前目标记录继续执行
- 执行第 3 段信号采集与治理
- 输出：
  - `structured_record`
  - `signal_bundle`
  - `collection_report`
- 执行第 4 段通用推理
- 生成多条假设
- 生成验证动作
- 输出第 5 段阶段性结论
- 输出知识沉淀候选

#### MongoDB

- 环境与对象盘点
- Kubernetes 对象采集
  - `StatefulSet`
  - Pod
  - `Service`
  - Node
- 分片集群 / 副本集基础 topology 识别
- `rs.status()` 基础成员状态采集
- Pod 日志采集
  - 当前日志
  - 重启前日志（如可用）
- 基础信号治理
  - 时间对齐
  - 对象关联
  - 初步过滤降噪
- 第 3 段脚本组织
  - `domains/mongodb/scripts/collect/`
  - `domains/mongodb/scripts/normalize/`
  - `domains/mongodb/scripts/helpers/`
- 第 3 段脚本命名规则
  - 采用 `<phase>-<target>-<action>`

#### MongoDB 第一批脚本清单

当前 `/plugin:analyse` 的 MongoDB MVP 已完成以下 11 个第 3 段脚本的合同级实现：

1. `mongodb.collect.pods.state`
2. `mongodb.collect.statefulsets.yaml`
3. `mongodb.collect.services.yaml`
4. `mongodb.collect.nodes.state`
5. `mongodb.collect.events.yaml`
6. `mongodb.collect.mongos.get_shard_map`
7. `mongodb.collect.replicaset.rs_status`
8. `mongodb.collect.logs.current`
9. `mongodb.collect.logs.previous`
10. `mongodb.normalize.logs.highlights`
11. `mongodb.normalize.signals.bundle`

当前收敛原则：

- 先覆盖对象盘点、Kubernetes Events、分片拓扑确认、成员状态、当前日志、重启前日志和基础信号治理
- 先保证 `/plugin:analyse` 的主路径闭环
- 更复杂的事件、指标、节点系统日志和高级诊断脚本放后续版本补充

真实环境验证状态：

- 以上 11 个脚本已通过真实 K8s 环境 smoke test
- 测试环境为 3 节点 Kubernetes 集群
- 目标 namespace 为 `psmdb-test`
- 验证对象包括：
  - 12 个 Pod
  - 3 个 StatefulSet
  - 2 个 Service
  - 3 个 Node
  - 2 个 shard
  - 3 个副本集，9 个成员
  - 22 个日志文件
  - 63 条日志 highlights
  - 1 个 signal bundle

#### MongoDB 第一批脚本执行顺序

当前建议执行顺序如下：

1. `mongodb.collect.pods.state`
   - 先确认 Pod 存活、重启、时间和节点归属
2. `mongodb.collect.statefulsets.yaml`
   - 再确认 StatefulSet 编排和副本目标
3. `mongodb.collect.services.yaml`
   - 再确认 Service、NodePort 和入口映射
4. `mongodb.collect.nodes.state`
   - 再补节点状态、IP 和标签信息
5. `mongodb.collect.events.yaml`
   - 采集 Kubernetes Events，补充对象变更与异常事件信号
6. `mongodb.collect.mongos.get_shard_map`
   - 先从 `mongos` 视角确认分片路由和 shard 拓扑
7. `mongodb.collect.replicaset.rs_status`
   - 再确认副本集成员状态、角色、选举和同步情况
8. `mongodb.collect.logs.current`
   - 默认采当前日志
9. `mongodb.collect.logs.previous`
   - 对重启 Pod 补采前一轮日志
10. `mongodb.normalize.logs.highlights`
   - 先对日志做摘要和降噪
11. `mongodb.normalize.signals.bundle`
   - 最后做对象关联、时间线归并和信号打包

#### `/plugin:review`

- 保留命令入口
- 保留运行时规则和目标记录选择规则

### 第一版未实现能力清单

#### `/plugin:analyse`

- `scope` 参数
- `force_recollect` 参数
- 复杂多记录切换命令
- 深入层能力：
  - 基线扫描
  - 代码逻辑分析
  - 代码路径追踪
  - 复现脚本生成

#### `/plugin:review`

- 五维评分与改进建议已有原型实现（见 plugin-usage.spec.md）
- 仍未实现：评分权重正式化、评分结果持久化归档细则

#### MongoDB

- 更复杂的高级场景自动化分析
- 节点系统日志的完整实现
- 指标采集的完整实现
- 日志系统接入的完整实现

#### 其他中间件

- Pulsar 正式支持
- Redis 正式支持
- Elasticsearch 正式支持
- Kafka 正式支持

### 使用原则

- 第一版输出中应显式标记未实现能力
- 第一版文档中应明确标记支持范围
- 第一版实现优先保证主路径可跑通，而不是追求覆盖全部已讨论能力

## 13. Incident 目录结构

当前采用“一次排障一个目录”的方式：

```text
incidents/
  <incident_id>/
    meta.yaml
    input.yaml
    structured_record.yaml
    signal_bundle.yaml
    collection_report.yaml
    analysis.yaml
    logs/
      raw/
      processed/
```

## 14. 核心文件职责

| 文件 | 职责 |
|---|---|
| `meta.yaml` | 记录级元信息、状态和导航入口 |
| `input.yaml` | 启动输入和原始故障线索 |
| `structured_record.yaml` | 对象、拓扑、状态、日志等结构化明细 |
| `signal_bundle.yaml` | 治理后的信号结果 |
| `collection_report.yaml` | 采集结果、失败、留白和证据缺口 |
| `analysis.yaml` | 假设、验证、结论、知识沉淀候选、review 结果 |

## 15. 关键文件最小骨架

### `meta.yaml`

建议字段：

- `incident_id`
- `middleware`
- `status`
- `created_at`
- `updated_at`
- `plugin_version`
- `current_command`
- `namespace`
- `cluster_id`
- `owner`

原则：

- 只做总入口和导航
- 不放分析内容

### `input.yaml`

建议字段：

- `middleware`
- `k8s_access_ips`
- `username`
- `password`
- `port`
- `customer_clue`
- `clue_enrichment`
- `input_source`
- `received_at`

原则：

- 保留启动时第一手输入
- 基础输入默认冻结

### `structured_record.yaml`

最小骨架：

- `summary`
- `details`
- `generated_at`

### `signal_bundle.yaml`

最小骨架：

- `signal_overview`
- `abnormal_signals`
- `object_signal_links`
- `timeline_summary`
- `processed_log_highlights`
- `generated_at`
- `updated_at`

### `collection_report.yaml`

最小骨架：

- `collection_actions`
- `successful_items`
- `failed_items`
- `blank_items`
- `evidence_gaps`
- `generated_at`
- `updated_at`

### `analysis.yaml`

最小骨架：

- `hypotheses`
- `validation_actions`
- `conclusion_summary`
- `knowledge_candidates`
- `review`
- `generated_at`
- `updated_at`

## 16. 脚本与 Agent 边界

第 3 段当前应优先设计为脚本友好：

- 采集
- 整理
- 时间对齐
- 初步过滤降噪
- 结构化输出

第 4 段当前应优先设计为 Agent 友好：

- 假设生成
- 因果路径归纳
- 反证条件归纳
- 证据缺口提取
- 验证动作生成
- 阶段性结论整理

## 17. 当前结论

当前已经具备编码前的最小运行时基线：

- 命令模型已定
- 状态机已定
- 会话级当前目标记录规则已定
- MVP 范围已定
- 脚本运行时来源与最小 `script_id` 规则已定
- 插件侧 `script_id -> runtime_path` 最小映射规则已定
- 第 3 段脚本最小调用合同已定
- `remote executor` 职责边界已定
- 中间件工具优先通过 Pod 内执行的原则已定
- 脚本测试与远程执行分层原则已定
- incident 目录和核心文件骨架已定

后续未实现项可继续在：

- [docs/TODO.md](../project/todo.md)

中持续追加。
