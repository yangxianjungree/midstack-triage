---
status: draft
last_updated: 2026-06-21
supersedes: none
superseded_by: none
---

# Slash Command Surface

本文说明 Midstack 对外的 `/midstack:*` 命令与 5 阶段排障流程的对应关系。它不描述具体实现，只描述命令语义、边界和文档责任。

相关事实源：

- [Plugin Runtime Spec](../specs/plugin-runtime.spec.md)
- [测试与安装门禁](testing-and-install-gates.md)

## 命令与阶段映射

| 命令 | 主要阶段 | 命令语义 | 备注 |
| --- | --- | --- | --- |
| `/midstack:start` | Phase 1 | 创建或恢复 incident，完成最小输入收集 | 成功后应提示 `next run /midstack:analyse` |
| `/midstack:start` | Phase 2 | 完成远端接入校验和基础盘点 | 继续在 start 阶段内完成 |
| `/midstack:analyse` | Phase 3 | 进行采集治理 | 进入控制面后触发采集或读取已有 remote run |
| `/midstack:analyse` | Phase 4 | 进行推理验证 | 形成多轨推理和规则回退判断 |
| `/midstack:analyse` | Phase 5 | 结论输出和报告收口 | 成功后产出 `analysis.yaml`、`report.md` 等 |
| `/midstack:review` | Phase 5 | 对已有分析做质量评分和反馈 | 不属于用户排障主路径的必跑步骤 |
| `/midstack:validate` | 维护者检查 | 校验安装态 runtime、资产和门禁 | 不是用户排障路径 |

## 命令责任边界

- `start` 负责把自然语言线索转成可执行 incident。
- `analyse` 负责把 incident 推进到推理、结论和报告。
- `analyse` 的默认执行方式是 `remote`；`local` 是实验性/部分支持路径，针对 ready incident 通过本地 transport 执行同一批采集脚本；`offline` 只消费完整已有产物，尚不是用户-facing 闭环排障路径。
- `review` 负责给已有分析打分，不替代 `analyse`。
- `validate` 负责维护者安装态检查，不对外承诺排障效果。

## 安装态要求

所有 slash 命令都必须通过安装态 runtime 执行，不得直接回退到源码 checkout。

- Claude 走 `${CLAUDE_PLUGIN_ROOT}/runtime/bin/...`
- Cursor 走 `.cursor/midstack-triage.workspace.json` 中的 `runtime_root`

## 文档责任

- `docs/project/slash-command-surface.md` 说明 slash surface 与 5 阶段的对应关系。
- `docs/specs/plugin-runtime.spec.md` 说明命令行为的唯一权威定义。
- `docs/project/testing-and-install-gates.md` 说明各命令对应的门禁和安装态 smoke。
