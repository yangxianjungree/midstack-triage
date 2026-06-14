# Spec: Phase 4 多轨推理引擎

> 注：本文件是实现阶段留下的工作 spec，保存在提案目录内作为历史上下文。当前代码结构、测试入口和集成位置以 `src/phases/phase4/multitrack/README.md`、`docs/project/phase4-multitrack-integration.md` 和实际目录为准。

## Objective

**What we're building**: Phase 4多轨推理引擎，用于自动化故障根因分析

**Users**: 
- 主要用户：midstack-triage系统（自动分析incident）
- 次要用户：SRE/DevOps工程师（通过CLI手动触发分析）

**Success Criteria**:
1. 给定incident目录（含structured_record.yaml、signal_bundle.yaml），输出符合L1模板的analysis.yaml
2. 支持2-5条假设轨并行推理，每轨独立维护推理历史
3. 生成reasoning-board.yaml，记录完整推理过程（可审计）
4. 第一版：2个真实incident案例跑通（MongoDB连接失败、DNS故障）
5. 性能：单incident分析完成时间 < 2分钟（3轮推理）

**User Stories**:
- 作为系统，我希望从多个假设出发并行推理，避免单一假设路径的盲点
- 作为SRE，我希望看到推理过程（reasoning-board.yaml），理解系统如何得出结论
- 作为开发者，我希望能轻松mock Agent调用，快速迭代逻辑

---

## Tech Stack

- **Language**: Python 3.10+
- **Core Dependencies**:
  - `pyyaml` - YAML读写
  - `pydantic` - 数据验证（可选，用于schema验证）
  - `pytest` - 测试框架
- **LLM Integration** (第二版):
  - Claude API (`anthropic` SDK)
  - Codex API (`openai` SDK)
  - Cursor API (待定义)
- **Project Type**: Python library + CLI entry point

---

## Commands

### Development
```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests (unit + integration)
pytest tests/

# Run specific test file
pytest tests/test_reasoning_board.py -v

# Type check
mypy src/phases/phase4/multitrack/

# Format
black src/ tests/
```

### Usage
```bash
# Run Phase 4 analysis (as library)
python -c "
from phase4_multitrack.cli_integration import run_phase4_analysis
from pathlib import Path
result = run_phase4_analysis(Path('./incidents/inc_001'))
"

# Run via midstack-local.py (integration)
cd /home/stephen/AI/midstack-triage
python -m tools.plugin.midstack-local analyse incidents/inc_001
```

### Testing
```bash
# Unit tests only
pytest tests/phase4_multitrack/unit -v

# Integration tests (with mock Agent)
pytest tests/phase4_multitrack/e2e/test_full_pipeline.py -v

# E2E test (real incident, mock Agent)
pytest tests/phase4_multitrack/e2e/test_real_incidents.py -v

# E2E with real LLM (manual, in sandbox)
cd ../sandbox
claude
```

---

## Project Structure

```
midstack-triage/
├── src/
│   └── phase4_multitrack/          # 新增：Phase 4独立模块
│       ├── __init__.py
│       ├── reasoning_board.py      # ReasoningBoard类
│       ├── hypothesis_track.py     # HypothesisTrack类
│       ├── lead_orchestrator.py    # LeadOrchestrator类
│       ├── agents/                 # Agent协议、mock/Claude实现、工厂
│       ├── agent_interface.py      # 兼容导出层
│       ├── l1_mapper.py            # L1模板映射
│       ├── cli_integration.py      # 集成入口
│       └── data_structures.py      # 共享数据结构
│
├── tests/
│   └── phase4_multitrack/
│       ├── unit/
│       │   ├── test_reasoning_board.py
│       │   ├── test_hypothesis_track.py
│       │   └── test_l1_mapper.py
│       ├── e2e/
│       │   ├── test_full_pipeline.py
│       │   ├── test_real_incidents.py
│       │   └── test_cli_integration.py
│       └── conftest.py
│
├── tools/plugin/
│   └── midstack-local.py           # 修改：集成Phase 4入口
│
├── docs/proposals/2026-06-12-phase4-reasoning-model/
│   ├── design-data-structures.md   # 已有：设计文档
│   ├── design-interfaces.md
│   ├── design-execution-flow.md
│   └── blocker-*.md
│
└── docs/proposals/2026-06-12-phase4-reasoning-model/implementation-spec.md
```

**Key Directories**:
- `src/phases/phase4/multitrack/` - 核心实现，独立模块
- `tests/phase4_multitrack/unit/` - 单元测试（测ReasoningBoard API等）
- `tests/phase4_multitrack/integration/` - 集成测试（测三相位流程）
- `tests/phase4_multitrack/e2e/` - E2E测试（完整incident）
- `tests/phase4_multitrack/fixtures/` - 测试数据（真实incident样本）

---

## Code Style

### Example: ReasoningBoard API

```python
from pathlib import Path
from typing import List, Dict, Optional
from threading import Lock
import yaml

class ReasoningBoard:
    """共享推理黑板，线程安全的YAML读写"""
    
    def __init__(self, incident_dir: Path):
        self.incident_dir = incident_dir
        self.board_path = incident_dir / "reasoning-board.yaml"
        self._lock = Lock()
        self._data: Dict = {}
        
        if self.board_path.exists():
            self._load()
        else:
            self._initialize()
    
    def add_finding(
        self,
        track_id: str,
        round_num: int,
        finding_type: str,
        content: str,
        evidence: List[str],
        affects: List[Dict]
    ) -> str:
        """添加发现（线程安全），返回finding_id"""
        with self._lock:
            finding_id = f"F{len(self._data['findings']) + 1:03d}"
            self._data["findings"].append({
                "id": finding_id,
                "track": track_id,
                "round": round_num,
                "type": finding_type,
                "content": content,
                "evidence": evidence,
                "affects": affects
            })
            self._save()
            return finding_id
```

### Conventions

**Naming**:
- Classes: `PascalCase` (ReasoningBoard, HypothesisTrack)
- Functions/methods: `snake_case` (add_finding, run_phase_r1)
- Constants: `UPPER_SNAKE_CASE` (MAX_ROUNDS, MAX_TRACKS)
- Private methods: `_prefix` (_load, _save, _derive_status)

**Type Hints**:
- All public APIs must have type hints
- Use `Optional[T]` for nullable values
- Use `List[Dict]` over `list` for clarity

**Error Handling**:
- Use exceptions for contract violations (e.g., invalid hypothesis_id)
- Log warnings for recoverable issues (e.g., missing evidence)
- No bare `except:` - always catch specific exceptions

**Documentation**:
- Docstrings for all public classes/methods
- Format: Google style (brief summary + Args/Returns)
- No inline comments unless logic is non-obvious

**Example Docstring**:
```python
def update_hypothesis_status(
    self,
    hypothesis_id: str,
    status: str,
    confidence: float,
    round_num: int,
    track_id: str
) -> None:
    """更新假设状态到共享层
    
    Args:
        hypothesis_id: 假设ID（如"h1"）
        status: 状态枚举（refuted/supported/insufficient/pending）
        confidence: 置信度（0.0-1.0）
        round_num: 当前轮次
        track_id: 更新者轨ID
    """
```

---

## Testing Strategy

### Test Pyramid

1. **Unit Tests (60%)** - `tests/phase4_multitrack/unit/`
   - Test: ReasoningBoard API（add_finding、get_hypothesis_status等）
   - Test: HypothesisTrack状态机（_should_track_continue、_derive_final_status_in_r2）
   - Test: L1映射函数（map_to_l1_template、determine_deepest_level）
   - Coverage target: 80%

2. **E2E Tests (40%)** - `tests/phase4_multitrack/e2e/`
   - Test: 完整incident分析（真实fixture + mock Agent）
   - Test: reasoning-board.yaml格式正确
   - Test: analysis.yaml符合L1模板

### Test Framework & Tools

- **Framework**: `pytest`
- **Fixtures**: `tests/phase4_multitrack/fixtures/`
  - `incident_mongodb_001/` - MongoDB连接失败案例
  - `mock_agent_responses.py` - mock Agent返回值
- **Assertions**: Use `assert` with clear messages
- **Mocking**: Use `unittest.mock` for Agent/Runner

### Example Test

```python
# tests/phase4_multitrack/unit/test_reasoning_board.py

from pathlib import Path
from phase4_multitrack import ReasoningBoard

def test_add_finding_thread_safe(tmp_path):
    """测试add_finding线程安全且返回正确ID"""
    board = ReasoningBoard(tmp_path)
    
    finding_id = board.add_finding(
        track_id="track_h1",
        round_num=1,
        finding_type="refutation",
        content="DNS正常",
        evidence=["E_dns_001"],
        affects=[{"hypothesis": "h1", "impact": "refute"}]
    )
    
    assert finding_id == "F001"
    findings = board.get_all_findings()
    assert len(findings) == 1
    assert findings[0]["content"] == "DNS正常"
```

### Verification Steps per Test Level

**Unit Test Checklist**:
- [ ] Test passes with mock data
- [ ] Test fails when contract violated (e.g., invalid status enum)
- [ ] Edge cases covered (empty list, None values)

**Integration Test Checklist**:
- [ ] reasoning-board.yaml written correctly
- [ ] rounds_executed matches actual completed rounds
- [ ] termination_reason correct (all_hypotheses_conclusive vs max_rounds_reached)

**E2E Test Checklist**:
- [ ] analysis.yaml schema valid (matches core/templates/analysis.template.yaml)
- [ ] conclusion_summary.statement matches deepest_supported_level
- [ ] supporting_evidence/counter_evidence non-empty for supported hypothesis

---

## Boundaries

### Always Do

1. **Write tests before implementation** (TDD for core logic)
2. **Use type hints** for all public APIs
3. **Lock _data access** in ReasoningBoard (thread safety)
4. **Validate enums** (status: refuted/supported/insufficient/pending)
5. **Write findings before hypothesis_status** (R1 phase rule)
6. **Check rounds_executed accuracy** (no empty terminal round)

### Ask First

1. **Modify existing midstack-local.py flow** - Confirm integration point
2. **Change L1 template schema** - Must align with core/templates/
3. **Add new LLM provider** - Confirm API choice (Claude/Codex/Cursor)
4. **Add new validation action** - Confirm Runner/Collector reuse strategy
5. **Change termination logic** - Currently: all_inactive or max_rounds only

### Never Do

1. **直接访问 ReasoningBoard._data** - Always use封装方法
2. **在R1写入hypothesis_status** - Only in R2 after validation
3. **固定声称"根因"** - Use deepest_supported_level判断措辞
4. **开启空的terminal round** - Check active_tracks before incrementing round
5. **跳过type hints** - Even for private methods
6. **Merge without E2E test passing** - At least 1 real incident fixture must pass

---

## Success Criteria (Expanded)

**MVP (Phase 1 - 2 weeks)**:
1. ✅ ReasoningBoard + HypothesisTrack + LeadOrchestrator实现完成
2. ✅ Mock Agent，2个fixture incident跑通
3. ✅ 输出reasoning-board.yaml + analysis.yaml（L1格式）
4. ✅ Unit test coverage > 80%
5. ✅ 1个E2E test通过

**Phase 2 (MVP + 2 weeks)**:
1. ✅ 真实Agent集成（Claude API）
2. ✅ 在sandbox项目跑通
3. ✅ 集成到midstack-local.py
4. ✅ 性能优化（< 2分钟/incident）

**Phase 3 (MVP + 4 weeks)**:
1. ✅ 支持Codex/Cursor API
2. ✅ 历史案例检索（TD-005）
3. ✅ 智能终止（TD-002）

---

## Open Questions

1. Agent prompt设计 - 具体prompt模板待定（见design-execution-flow.md §3引用）
2. Runner复用 vs 重写 - 初步复用，如遇结构问题再独立
3. Sandbox测试环境 - 需确认sandbox项目路径和测试数据

---

## References

- Design Docs: `docs/proposals/2026-06-12-phase4-reasoning-model/`
- L1 Template: `core/templates/analysis.template.yaml`
- Existing Plugin: `tools/plugin/midstack-local.py`
- Technical Debt: `docs/proposals/.../technical-debt.md`
