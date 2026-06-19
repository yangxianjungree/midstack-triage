# Phase 3

`src/phases/phase3/` 放第 3 段“信号采集与治理”的正式实现。

当前边界：

- `incident_build.py`
  从 remote run 输出还原 incident 工作目录，生成 `input.yaml`、`structured_record.yaml`、`signal_bundle.yaml` 和 `collection_report.yaml`。
- `remote_collection.py`
  control plane 侧启动 `execution.remote.executor`；remote 使用 SSH transport，
  local 使用本地 transport，并把定向补采 remote run 合并回 incident。
- `remote_run.py`
  remote executor 输出目录契约、脚本输出合并、remote-executor 结果写入采集报告。
- `recollection.py`
  基于已有证据选择定向补采脚本，不负责启动远程执行。
- `recollection_run.py`
  执行定向补采：选择脚本后按 incident 的 remote/local collection 配置补采，
  并把结果合并回 incident。
- `report_gaps.py`
  采集报告 evidence gap 的归一化、收口和补采缺口记录。
- `scenario_routing.py`
  基于 Phase 3 证据和用户线索推断或补全 incident scenario。
- `skill_runtime.py`
  根据 middleware/scenario 匹配 skill、检查脚本证据完整性，并写回 runtime 上下文。

规则：

- 第 3 段负责证据构建和治理，不直接给出最终分析结论。
- `scenario_inference.unresolved=true` 时，Phase 3 保留 top1 `scenario` 作为主路由，
  但 skill runtime 会合并候选场景的 evidence/skill 覆盖，避免交叉场景过早收敛。
- Phase 3 执行 live collection 时必须以显式 `execution_mode` 为权威：
  `remote` 只使用 `remote-config.yaml`，`local` 只使用 `local-config.yaml`，
  `offline` 不启动采集或定向补采。`remote_config` / `local_config` 只作为
  对应 mode 的配置文件，不作为 mode 推断来源。
- 远程执行器的正式实现已经下沉到 `src/execution/remote/executor.py`。
- Phase 3 不保留聚合壳；新运行时代码必须从具体模块导入。
- 仓库不再保留 `tools/remote-*` 兼容壳；工程验证和插件 runtime 统一直接调用 `execution.remote.executor`。
