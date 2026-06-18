---
status: accepted
last_updated: 2026-06-14
supersedes: none
superseded_by: none
---

# Dual-Plane Runtime Architecture

## Context

Midstack 的真实执行模型并不是“一个本地插件包 + 一堆普通脚本”这么简单。

运行时至少有两个明确平面：

1. control plane
   - Claude/Cursor/Codex 等 agent 插件运行位置
   - slash 命令与 incident 编排
   - phase1~phase5 流程控制
   - analysis / reasoning / report 生成
2. execution plane
   - jump host、堡垒机、故障环境，或其他可达的远端执行点
   - 远端 `kubectl` / `mongosh` / shell 执行
   - 证据脚本投放、执行、结果回收

此前仓库已经按 `phase1~phase5` 梳理了流程边界，但远端接入与执行主实现一度仍混放在 phase 目录中，不足以表达真实运行拓扑。

## Decision

仓库正式采用“双平面”表达：

- `src/commands/`、`src/phases/`、`src/shared/` 归入 control plane
- `src/execution/` 归入 execution plane

具体规则：

- phase 目录表达排障流程语义，不长期承载远端 transport 或远程执行器主实现
- SSH/SSHPass 接入、scp 收发、远程 capability check、脚本投放与回收统一沉到 `src/execution/`
- `tools/` 继续只保留 CLI 壳、回放、校验器等工程入口
- Claude 插件 runtime 打包时同时包含 control plane 与 execution plane

## Consequences

正面影响：

- 仓库结构能直接反映真实运行拓扑，而不是只反映业务阶段
- 新增 jump host / todesk / 特殊远端执行策略时，有清晰的落点
- phase 代码更聚焦于“何时执行什么”，execution 代码更聚焦于“怎么连接和执行”

成本：

- 一些原本放在 `phase1` / `phase3` 的实现需要迁移或改成 facade
- 测试目录也要按 ownership 调整，避免 execution plane 逻辑继续挂在 phase 测试下

## Initial Mapping

- `src/execution/remote/access.py`
  control plane 到 jump host 的基础接入与前置校验
- `src/execution/remote/executor.py`
  远端脚本批量执行、结果回收
- `src/phases/phase1/startup.py`
  phase1 facade，消费 execution plane
- `src/phases/phase3/remote_collection.py`
  phase3 远程采集编排层，调用 execution plane 获取证据
- `src/phases/phase3/incident_build.py`
  phase3 incident 输入与采集产物构建
- `src/phases/phase3/recollection_run.py`
  phase3 定向补采编排，复用 remote collection
