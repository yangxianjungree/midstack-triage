# Phase 4: 多轨推理引擎

这里是旧导入路径的兼容目录。第 4 段运行时正式实现已经迁到 `src/phases/phase4/multitrack/`。

这个目录只保留兼容入口，避免历史 import 立即断裂；新的实现和后续演进都应放在正式目录，不再继续往这里新增代码。

## 目录职责

这里只允许保留兼容 shim：

- `__init__.py`
- `cli_integration.py`
- `agent_interface.py`
- 其他与历史 import 对应的薄转发模块

禁止事项：

- 不要在这里新增 Phase 4 真实实现
- 不要把新 agent、推理逻辑、数据结构继续放回这个目录
- 不要让这个目录重新长成第二套正式实现

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

如果只是仓库内部新代码、测试或示例，请直接导入正式路径 `phases.phase4.multitrack`，不要继续扩大对这个兼容目录的依赖。

## 测试入口

```bash
pytest tests/phases/phase4/multitrack/unit -v
pytest tests/phases/phase4/multitrack/e2e -v
```

## 工程约束

- 示例和测试不要把输出写回仓库根目录或真实 fixture 目录。
- 设计文档只留在 `docs/proposals/...`，不要再在仓库根目录放额外 `SPEC.md`。
- Phase 4 的命令入口由 `src/commands/analyse.py` 编排；`tools/plugin/midstack-local.py` 只负责 CLI 适配。
