# MongoDB Scripts

本目录用于存放 MongoDB 自动化排查脚本。

当前第一版只规范第 3 段 `信号采集与治理` 相关脚本，不在这里放第 4 段推理逻辑。

## 目录结构

```text
domains/mongodb/scripts/
  manifest.yaml
  collect/
  normalize/
  helpers/
```

目录职责：

- `collect/`
  - 单一采集动作入口
  - 面向 Kubernetes、MongoDB 服务端、日志入口或监控入口取数
- `normalize/`
  - 对采集结果做时间对齐、对象关联、日志降噪、异常摘要和信号归并
- `helpers/`
  - 公共函数、解析辅助、命令封装和共享校验

## Manifest

当前建议使用一份 `manifest.yaml` 统一登记 MongoDB 脚本资产。

作用：

- 作为 MongoDB 脚本入口清单
- 供插件构建和打包流程使用
- 供运行时生成 `script_id -> plugin_relative_path` 映射

当前原则：

- 一个中间件一份 manifest
- 一个 manifest 登记多个脚本
- `helpers/` 中的共享脚本默认不登记，除非它本身也是直接执行入口
- `source` 只表示主仓库资产路径，不表示插件安装后的运行路径

## Script Contract

当前建议 MongoDB 第 3 段脚本统一采用以下调用方式：

```text
<script> --context-file <path> --output-file <path> --artifact-dir <path>
```

合同原则：

- `context-file`
  - 提供本次脚本执行所需上下文
- `output-file`
  - 输出机器可读结果
- `artifact-dir`
  - 保存原始命令输出、原始日志和临时采集文件

状态原则：

- `status` 统一使用：
  - `success`
  - `partial`
  - `blocked`
- 当脚本按合同成功写出 `output-file` 时，退出码应为 `0`
- 非 `0` 退出码仅用于表示脚本自身执行失败或合同违规

运行时依赖原则：

- 第一版脚本应兼容 Python 3.6
- 优先使用 Python 标准库
- 不默认要求跳板机安装 `PyYAML`
- `context-file` 和 `output-file` 支持 JSON-compatible YAML

## Output Profile

当前建议 MongoDB 第 3 段脚本的 `output-file` 采用“结果概览 + patch + 产物引用”的结构。

最小字段：

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

当前原则：

- `collect/*` 脚本主要写 `structured_record_patch` 和 `collection_report_patch`
- `normalize/*` 脚本主要写 `signal_bundle_patch`
- `artifacts` 只引用 `artifact-dir` 内的相对路径
- 机器可读结果不写到 `stdout`

## Remote Test Strategy

当前建议 MongoDB 脚本测试采用“执行层远程进入环境，脚本层只处理采集逻辑”的方式。

原则：

- 脚本本身不负责 SSH
- 远程测试执行器负责登录跳板机并在远程环境执行脚本
- 脚本应先投放到跳板机 `/tmp/<plugin_name>/assets/scripts/...`
- 单次执行目录使用 `/tmp/<plugin_name>/runs/<incident_id>/<script_id>/`
- 远程环境需要能直接执行 `kubectl`
- `mongosh` 默认通过 `kubectl exec` 在 `mongos` 或 `mongod` Pod 内执行
- 多个入口 IP 默认以第一个 IP 作为跳板入口
- 真实测试环境配置不写入仓库
- 本地私有配置建议放在：
  - `.local/test-envs/mongodb-k8s.yaml`

当前建议远程测试最小步骤：

1. 验证 SSH 连通
2. 验证远程 `kubectl` 可用
3. 验证基础 Kubernetes 操作可用
4. 生成本次测试用 `context-file`
5. 在远程环境运行脚本
6. 拉回 `output-file` 和 `artifact-dir`
7. 按脚本合同做通过性检查

## MongoDB Context Profile

当前建议 MongoDB 第一批基础采集脚本共享以下 `context-file` 字段：

- `deployment_architecture`
- `topology_type`
- `access`
- `targets`
- `capabilities`

其中：

- `access`
  - `primary_ip`
  - `candidate_ips`
  - `username`
  - `password`
  - `port`
- `targets`
  - `namespace`
  - `statefulset_refs`
  - `service_refs`
  - `pod_refs`
  - `node_refs`
  - `mongos_pod_ref`
- `capabilities`
  - `kubectl_available`
  - `kubectl_exec_available`
  - `mongosh_in_pod_available`

### Per-Script Context

- `mongodb.collect.pods.state`
  - `pod_query.mode`
- `mongodb.collect.statefulsets.yaml`
  - `statefulset_query.include_yaml`
- `mongodb.collect.services.yaml`
  - `service_query.include_nodeport`
- `mongodb.collect.nodes.state`
  - `node_query.resolve_from_pods`
- `mongodb.collect.mongos.get_shard_map`
  - `mongos_query.shell`
  - `mongos_query.database`
  - `mongos_query.command`
  - `mongos_query.username`
  - `mongos_query.password`
  - `mongos_query.password_env`
  - `mongos_query.password_file_env`
  - `mongos_query.auth_database`
  - `mongos_query.secret_ref`

### MongoDB Auth Sources

MongoDB 服务端命令通常需要认证信息。

当前约定：

- Bitnami 部署优先从 Pod 内环境变量读取认证信息，例如 `MONGODB_ROOT_PASSWORD`
- 若 Bitnami 使用文件挂载形式，则通过 `MONGODB_ROOT_PASSWORD_FILE` 这类环境变量在 Pod 内读取密码文件
- operator+CRD 部署通常需要从 Kubernetes Secret 资源读取认证信息
- 第一版脚本支持 `mongos_query.password`、`mongos_query.password_env`、`mongos_query.password_file_env` 和 `mongos_query.secret_ref`
- `replicaset_query.secret_ref` 也可用于 `rs.status()` 采集；未提供时会回退读取 `mongos_query.secret_ref`
- 密码不应写入脚本 output、artifact 或日志

`secret_ref` 最小字段：

- `namespace`
- `name`
- `key`

其中 `namespace` 可省略，默认使用当前 `context-file.namespace`。

## Structured Targets

当前建议第一批 MongoDB 基础脚本的主要落点如下：

- `mongodb.collect.pods.state`
  - `structured_record.details.pods`
- `mongodb.collect.statefulsets.yaml`
  - `structured_record.details.statefulsets`
- `mongodb.collect.services.yaml`
  - `structured_record.details.services`
- `mongodb.collect.nodes.state`
  - `structured_record.details.nodes`
- `mongodb.collect.mongos.get_shard_map`
  - `structured_record.details.shard_map`
- `mongodb.collect.replicaset.rs_status`
  - `structured_record.details.replica_members`
- `mongodb.collect.logs.current`
  - `structured_record.details.raw_logs`
- `mongodb.collect.logs.previous`
  - `structured_record.details.raw_logs`
- `mongodb.normalize.logs.highlights`
  - `structured_record.details.processed_logs`
- `mongodb.normalize.signals.bundle`
  - `signal_bundle`

## MVP Script Set

当前 MongoDB 第一版已实现以下 11 个脚本：

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

收敛理由：

- 覆盖第 2 段和第 3 段所需的最小对象盘点
- 覆盖 MongoDB 分片集群 / 副本集基础 topology 判断
- 覆盖 `mongos` 视角的 shard map 采集
- 覆盖 Kubernetes Events、当前日志和重启前日志
- 覆盖第一轮日志降噪和信号打包

当前暂不放入第一批的能力包括：

- 事件采集
- 指标采集
- 节点系统日志
- 更复杂的高级分析脚本

## Implementation Status

当前实现状态：

| script_id | 状态 | 说明 |
|---|---|---|
| `mongodb.collect.pods.state` | implemented | 已支持合同解析、Pod 状态采集、artifact 输出和 blocked 输出 |
| `mongodb.collect.statefulsets.yaml` | implemented | 已支持合同解析、StatefulSet 编排采集、artifact 输出和 blocked 输出 |
| `mongodb.collect.services.yaml` | implemented | 已支持合同解析、Service/NodePort 编排采集、artifact 输出和 blocked 输出 |
| `mongodb.collect.nodes.state` | implemented | 已支持合同解析、Node 状态采集、从 Pod 反推节点、artifact 输出和 blocked 输出 |
| `mongodb.collect.mongos.get_shard_map` | implemented | 已支持 mongos Pod 自动识别、Bitnami Pod 内认证、shard map 采集、artifact 输出和 blocked 输出 |
| `mongodb.collect.replicaset.rs_status` | implemented | 已支持 mongod Pod 自动识别、Bitnami Pod 内认证、rs.status 采集、artifact 输出和 blocked/partial 输出 |
| `mongodb.collect.logs.current` | implemented | 已支持 MongoDB Pod 自动识别、当前日志采集、artifact 输出和 blocked/partial 输出 |
| `mongodb.collect.logs.previous` | implemented | 已复用日志采集主逻辑，支持 previous 日志采集、artifact 输出和 blocked/partial 输出 |
| `mongodb.normalize.logs.highlights` | implemented | 已支持 current/previous 日志 artifact 扫描、ANSI 清理、关键日志提取、processed artifact 和 signal patch 输出 |
| `mongodb.normalize.signals.bundle` | implemented | 已支持标准脚本 output 合并、inventory/topology/log signals 汇总、signal bundle artifact 和 signal patch 输出 |

## Execution Order

当前建议主顺序如下：

1. `mongodb.collect.pods.state`
2. `mongodb.collect.statefulsets.yaml`
3. `mongodb.collect.services.yaml`
4. `mongodb.collect.nodes.state`
5. `mongodb.collect.mongos.get_shard_map`
6. `mongodb.collect.replicaset.rs_status`
7. `mongodb.collect.logs.current`
8. `mongodb.collect.logs.previous`
9. `mongodb.normalize.logs.highlights`
10. `mongodb.normalize.signals.bundle`

## 命名规则

当前建议采用：

`<phase>-<target>-<action>`

示例：

- `collect-pods-state.sh`
- `collect-statefulsets-yaml.sh`
- `collect-replicaset-rs-status.sh`
- `collect-logs-current.sh`
- `collect-logs-previous.sh`
- `normalize-logs-highlights.py`
- `normalize-signals-bundle.py`

命名原则：

- 明确输入和输出
- 默认优先只读
- 与 runbook 和 skill 通过 metadata 建立关联
- 文件名不重复 `mongodb` 前缀
- 一个脚本只做一类动作，不混采集、治理和推理
