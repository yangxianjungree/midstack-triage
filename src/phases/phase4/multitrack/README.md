# Phase 4: 多轨推理引擎

第 4 段运行时正式实现放在 `src/phases/phase4/multitrack/`。这个目录只承载可执行模块，不放提案、评审记录、demo 输出或一次性讨论文档。

## 目录职责

- `reasoning_board.py` - 共享黑板与过程态落盘
- `hypothesis_track.py` - 单轨观察、推理、验证闭环
- `lead_orchestrator.py` - 多轨编排与终止判断
- `agents/` - 协议、mock、Claude 实现和工厂
- `l1_mapper.py` - 从第 3 段输入映射初始假设
- `data_structures.py` - 过程态数据结构

`multitrack/agents/` 子目录约束：

- `base.py` 只放协议和共享接口约定
- `mock.py` 放默认本地/测试 agent
- `claude.py` 放真实 Claude agent 适配
- `factory.py` 放 agent 选择和构建逻辑
- 不要把 phase 编排、board 读写或测试夹杂进 `agents/`

正式实现约束：

- 新代码优先写入 `src/phases/phase4/multitrack/`
- 不要再把 phase 入口、CLI 胶水或 `analysis.yaml` 输出编排新增到这个目录
- 不再保留 `src/phases/phase4/` 之外的平行 Phase 4 实现目录

配套内容分层如下：

- 设计提案：`docs/proposals/2026-06-12-phase4-reasoning-model/`
- 集成说明：`docs/project/phase4-multitrack-integration.md`
- 示例：`examples/phase4/`
- 测试：`tests/phases/phase4/multitrack/`

## 核心组件

- `ReasoningBoard` - 共享黑板，管理 `reasoning-board.yaml`
- `HypothesisTrack` - 单假设推理轨，维护隔离上下文
- `LeadOrchestrator` - 多轨协调器
- `L1TemplateMapper` - 第 3 段输入到初始假设的映射器

## 三相位推理循环

```text
Phase R1: 各轨并行推理 -> 请求验证
Phase V:  执行验证动作
Phase R2: 读取验证结果 -> 更新假设状态
```

## 最小用法

```python
from pathlib import Path

from phases.phase4.multitrack import LeadOrchestrator

incident_dir = Path(".local/examples/phase4/basic")
incident_dir.mkdir(parents=True, exist_ok=True)

hypotheses = ["假设A", "假设B", "假设C"]
result = LeadOrchestrator(incident_dir, hypotheses).run()

print(result["total_rounds"])
```

## 测试入口

```bash
pytest tests/phases/phase4/multitrack/unit -v
pytest tests/phases/phase4/multitrack/e2e -v
```

## 工程约束

- 示例和测试不要把输出写回仓库根目录或真实 fixture 目录。
- 设计文档只留在 `docs/proposals/...`，不要再在仓库根目录放额外 `SPEC.md`。
- Phase 4 的命令入口由 `src/commands/analyse.py` 编排；本地 CLI 调度在 `src/commands/plugin_cli.py`，`tools/plugin/midstack-local.py` 只保留启动壳。
