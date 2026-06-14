---
status: draft
last_updated: 2026-06-14
supersedes: none
superseded_by: none
---

# Phase 4 集成说明

本文档只说明当前仓库里第 4 段多轨推理模块的实际集成位置、职责边界和验证入口，不重复设计提案内容。

## 当前集成位置

第 4 段运行时入口已经接在 [tools/plugin/midstack-local.py](/home/stephen/AI/midstack-triage/tools/plugin/midstack-local.py) 的 `analyse` 路径中。

当前链路是：

1. 第 1-3 段生成 `signal_bundle.yaml`、`structured_record.yaml`、`collection_report.yaml`
2. `analyse` 在 incident 目录上调用 `phase4_multitrack.cli_integration.run_phase4_analysis()`
3. Phase 4 落盘 `reasoning-board.yaml`
4. 后续 analyse runner 继续生成 `analysis.yaml`、`report.md` 等终态文件

也就是说，Phase 4 现在是 analyse 主路径中的一个过程阶段，不是一个独立 CLI 产品。

## 模块边界

- 运行时代码：`src/phase4_multitrack/`
- 设计提案和 review：`docs/proposals/2026-06-12-phase4-reasoning-model/`
- 示例脚本：`examples/phase4/`
- 测试：`tests/phase4_multitrack/`

不要把以下内容再放回仓库根目录：

- 临时 `SPEC.md`
- `demo_*` 脚本
- demo 输出目录
- “待集成”式的过期说明文档

## 当前输入输出

输入：

- `signal_bundle.yaml`
- `structured_record.yaml`
- 可选的 `collection_report.yaml`

过程产物：

- `reasoning-board.yaml`

后续终态：

- `analysis.yaml`
- `report.md`

## 验证入口

模块级测试：

```bash
pytest tests/phase4_multitrack/unit -v
pytest tests/phase4_multitrack/e2e -v
```

示例脚本：

```bash
python3 examples/phase4/basic_usage.py
python3 examples/phase4/demo_mongodb_timeout.py
```

注意：示例脚本只往 `.local/examples/phase4/` 写输出，不应污染仓库根目录或真实 fixture。

## 当前限制

- Phase 4 默认仍使用 mock agent 路径
- 真实 Claude API 推理仍是后续能力，不在这份集成说明里承诺为当前默认行为
- 过程黑板 `reasoning-board.yaml` 已经是当前实现的一部分，但其结构仍以提案和代码为准，尚未上升为独立 L1 规范
