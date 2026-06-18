---
status: draft
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# 治理清单

本文是当前工程治理的执行清单，不重复定义行为规范。行为权威请分别查看：

- [Slash 命令面说明](slash-command-surface.md)
- [测试与安装门禁](testing-and-install-gates.md)
- [插件运行时规范](../specs/plugin-runtime.spec.md)
- [插件使用规范](../specs/plugin-usage.spec.md)
- [Phase Runtime Modules](../../src/phases/README.md)
- [Slash Command Runtime](../../src/commands/README.md)

## 已收敛的模块边界

- `src/commands/`
  slash 命令正式入口，负责 `start / analyse / review / finalize-analysis` 的本地调度。
- `src/phases/phase1/`
  启动与远端接入校验。
- `src/phases/phase2/`
  环境对象盘点、认证 hint、拓扑、事件关联。
- `src/phases/phase3/`
  采集治理、remote run 合并、scenario routing、skill runtime、定向补采。
- `src/phases/phase4/`
  推理与论证；`multitrack/` 放多轨推理实现。
- `src/phases/phase5/`
  收口、review、评分。
- `src/execution/`
  远端接入、执行与结果回收。
- `src/shared/`
  跨命令、跨 phase 复用的运行时能力。

## 命令与阶段关系

| 命令 | 主职责 | 覆盖阶段 |
| --- | --- | --- |
| `/midstack:start` | 启动 incident、校验远端接入、盘点对象 | Phase 1-2 |
| `/midstack:analyse` | 采集治理、推理验证、输出结论和报告 | Phase 3-5 |
| `/midstack:review` | 质量反馈和五维评分 | Phase 5 |
| `/midstack:validate` | 安装态与工程自检 | 维护者检查 |

`/midstack:start` 成功后，唯一需要提示的下一步是 `next run /midstack:analyse`。

## 当前约束

- `src/` 只放会进入插件 runtime payload 的正式实现。
- `tools/` 只放薄入口、校验器、回放和工程脚本。
- 不再新增 `collection.py` 这类聚合入口；`__init__.py` 只做显式导出，不承载实现。
- 新的 phase 代码优先按 `src/phases/phaseN/<topic>.py` 增加，不再回到扁平 shim。
- Claude 与 Cursor 的安装态都不能回调源码 checkout。

## 还要继续治理的项

- Phase 3 已移除 `collection.py` 聚合入口；后续禁止重新引入大聚合文件。
- Phase 4 继续减少 `_data` 这类内部结构外泄。
- 安装态 smoke 继续覆盖 Claude / Cursor 的真实 workspace。
- `.local/`、`__pycache__`、fixture hygiene 等工程门禁继续保持。

## 推荐执行顺序

1. 先补/修模块边界。
2. 再跑对应单测和安装态门禁。
3. 最后提交独立小切片。
