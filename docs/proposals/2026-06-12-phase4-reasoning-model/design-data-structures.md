---
status: design
last_updated: 2026-06-13
purpose: 定义共享层（reasoning-board）和隔离层的完整数据结构
---

# 数据结构设计

## 1. 共享层：reasoning-board.yaml

**存储位置**：`{incident_dir}/reasoning-board.yaml`

**职责**：所有轨共享的客观证据、验证结果、发现、反证

```yaml
# reasoning-board.yaml 完整 schema

version: "1.0"
created_at: "2026-06-13T02:43:47Z"
incident_id: "inc_20260613_mongodb_001"

# ==================== 基础证据（只读） ====================
base_evidence:
  # 第3段证据包的引用（不复制，避免冗余）
  structured_record_path: "./structured_record.yaml"
  signal_bundle_path: "./signal_bundle.yaml"
  collection_report_path: "./collection_report.yaml"
  
  # 时间线（故障主线之一）
  timeline:
    - time: "2026-06-12T14:23:05Z"
      event: "连接开始失败"
      source: "mongodb-log"
      evidence_id: "timeline_001"
    - time: "2026-06-12T14:23:12Z"
      event: "Pod mongodb-0 重启"
      source: "k8s-event"
      evidence_id: "timeline_002"
  
  # 历史案例（未来从数据库检索，第一版为空）
  historical_cases: []

# ==================== 假设状态（共享） ====================
hypothesis_status:
  h1:
    desc: "DNS解析失败"
    status: "refuted"  # pending/refuted/supported/insufficient
    confidence: 0.9  # 0-1
    last_updated_round: 1
    last_updated_by: "track_h1"
  
  h2:
    desc: "网络分区"
    status: "insufficient"
    confidence: 0.3
    last_updated_round: 1
    last_updated_by: "track_h2"
  
  h3:
    desc: "连接池耗尽"
    status: "supported"
    confidence: 0.8
    last_updated_round: 2
    last_updated_by: "track_h3"

# ==================== 验证队列（避免重复） ====================
validation_queue:
  - id: "val_001"
    action: "check_dns_resolution"
    requested_by: ["track_h1"]
    requested_at_round: 1
    status: "completed"  # pending/executing/completed/failed
    result_id: "E_dns_001"
    completed_at: "2026-06-13T02:44:10Z"
  
  - id: "val_002"
    action: "check_connection_pool_metrics"
    requested_by: ["track_h3"]
    requested_at_round: 1
    status: "completed"
    result_id: "E_pool_001"
    completed_at: "2026-06-13T02:44:15Z"
  
  - id: "val_003"
    action: "check_slow_queries"
    requested_by: ["track_h3"]
    requested_at_round: 2
    status: "completed"
    result_id: "E_query_001"
    completed_at: "2026-06-13T02:45:20Z"

# ==================== 已执行验证结果 ====================
executed_validations:
  E_dns_001:
    evidence_id: "E_dns_001"  # 修复阻塞点5：显式记录
    action: "check_dns_resolution"
    result: "DNS响应正常，平均12ms，无异常"
    evidence_type: "refutation"
    raw_data:
      avg_response_ms: 12
      success_rate: 1.0
    shared_to: ["track_h1"]
    executed_at: "2026-06-13T02:44:10Z"
  
  E_pool_001:
    evidence_id: "E_pool_001"  # 修复阻塞点5：显式记录
    action: "check_connection_pool_metrics"
    result: "连接数 95/100，接近上限，14:23:05开始积压"
    evidence_type: "support"
    raw_data:
      current: 95
      max: 100
      utilization: 0.95
      onset_time: "2026-06-12T14:23:05Z"
    shared_to: ["track_h3"]
    executed_at: "2026-06-13T02:44:15Z"
  
  E_query_001:
    evidence_id: "E_query_001"  # 修复阻塞点5：显式记录
    action: "check_slow_queries"
    result: "14:22:50开始慢查询突增，平均500ms→2000ms"
    evidence_type: "support"
    raw_data:
      baseline_avg_ms: 500
      spike_avg_ms: 2000
      spike_start: "2026-06-12T14:22:50Z"
    shared_to: ["track_h3"]
    executed_at: "2026-06-13T02:45:20Z"

# ==================== 客观发现（各轨追加） ====================
findings:
  - id: "F001"
    track: "track_h1"
    round: 1
    type: "refutation"  # refutation/support/gap/observation
    content: "DNS解析正常，h1假设被反证"
    evidence: ["E_dns_001", "timeline_001"]
    affects:
      - hypothesis: "h1"
        impact: "refute"
        confidence: 0.9
    created_at: "2026-06-13T02:44:12Z"
  
  - id: "F002"
    track: "track_h3"
    round: 1
    type: "support"
    content: "连接池接近满载，与故障onset时间吻合"
    evidence: ["E_pool_001", "timeline_001"]
    affects:
      - hypothesis: "h3"
        impact: "support"
        confidence: 0.7
    created_at: "2026-06-13T02:44:17Z"
  
  - id: "F003"
    track: "track_h2"
    round: 1
    type: "gap"
    content: "无法获取overlay网络拓扑，h2假设无法验证"
    evidence: []
    affects:
      - hypothesis: "h2"
        impact: "insufficient"
        confidence: 0.0
    gap_detail:
      missing: "overlay_network_topology"
      reason: "CNI插件未启用拓扑导出"
      can_resolve: false
      criticality: "high"  # 修复阻塞点4：新增字段
    created_at: "2026-06-13T02:44:20Z"
  
  - id: "F004"
    track: "track_h3"
    round: 2
    type: "support"
    content: "慢查询突增比故障早15秒，可能是根因"
    evidence: ["E_query_001", "timeline_001"]
    affects:
      - hypothesis: "h3"
        impact: "support"
        confidence: 0.9
    created_at: "2026-06-13T02:45:22Z"

# ==================== 跨轨反证 ====================
cross_refutations:
  - id: "CR001"
    from_track: "track_h3"
    to_hypothesis: "h1"
    from_finding: "F002"
    reason: "连接池问题可以完整解释现象，DNS假设不必要（奥卡姆剃刀）"
    confidence: "medium"  # low/medium/high
    created_at: "2026-06-13T02:44:18Z"
  
  - id: "CR002"
    from_track: "track_h3"
    to_hypothesis: "h1"
    from_finding: "F004"
    reason: "慢查询→连接池→故障的因果链完整，DNS无必要"
    confidence: "high"
    created_at: "2026-06-13T02:45:23Z"

# ==================== 证据缺口池 ====================
evidence_gaps:
  - gap: "overlay_network_topology"
    requested_by: ["track_h2"]
    status: "unavailable"  # unavailable/deferred/resolved
    reason: "CNI插件未启用拓扑导出"
    can_resolve: false
    criticality: "high"  # 修复阻塞点4：新增字段
    alternative: "可通过 ping/traceroute 间接验证，但成本高"
    created_at: "2026-06-13T02:44:20Z"

# ==================== 轮次元数据 ====================
rounds:
  - round: 1
    started_at: "2026-06-13T02:44:00Z"
    completed_at: "2026-06-13T02:44:25Z"
    tracks_active: ["track_h1", "track_h2", "track_h3"]
    validations_executed: ["val_001", "val_002"]
    findings_added: ["F001", "F002", "F003"]
  
  - round: 2
    started_at: "2026-06-13T02:45:00Z"
    completed_at: "2026-06-13T02:45:30Z"
    tracks_active: ["track_h3"]  # h1已refuted，h2无法继续
    validations_executed: ["val_003"]
    findings_added: ["F004"]
  
  - round: 3
    started_at: "2026-06-13T02:46:00Z"
    completed_at: "2026-06-13T02:46:10Z"
    tracks_active: []  # 所有假设已结论
    validations_executed: []
    termination_reason: "all_hypotheses_conclusive"
```

---

## 2. 隔离层：track-private-context

**存储位置**：不落盘（第一版），在Lead Agent内存维护，最终写入`analysis.yaml`时提取关键信息

**职责**：每条轨的推理过程、假设演化、因果链构建

```python
# Python 数据结构（内存）

@dataclass
class TrackPrivateContext:
    """单条假设轨的隔离上下文"""
    
    track_id: str  # "track_h1"
    hypothesis_id: str  # "h1"
    
    # 假设演化路径
    hypothesis_evolution: List[HypothesisVersion] = field(default_factory=list)
    
    # 推理思考日志
    reasoning_log: List[ReasoningEntry] = field(default_factory=list)
    
    # 该轨构建的因果链
    causal_chain: Optional[CausalChain] = None
    
    # 当前轮次
    current_round: int = 0
    
    # 轨状态
    is_active: bool = True  # False表示已结论（refuted/supported）

@dataclass
class HypothesisVersion:
    """假设的某个版本（演化历史）"""
    round: int
    hypothesis_text: str
    status: str  # pending/refuted/supported/insufficient
    reasoning: str  # 为什么这样判断
    evidence_considered: List[str]  # 考虑了哪些证据ID

@dataclass
class ReasoningEntry:
    """单条推理思考记录"""
    round: int
    timestamp: str
    thought: str  # "观察到14:23开始连接失败"
    action: Optional[str]  # "验证DNS"
    result: Optional[str]  # "DNS正常，假设不成立"

@dataclass
class CausalChain:
    """因果链（有向图）"""
    nodes: List[CausalNode]
    edges: List[CausalEdge]
    confidence: float  # 整条链的置信度

@dataclass
class CausalNode:
    id: str
    event: str  # "慢查询突增"
    time: Optional[str]  # "14:22:50"
    evidence: List[str]  # 支持这个节点的证据ID

@dataclass
class CausalEdge:
    from_node: str
    to_node: str
    relationship: str  # "causes" / "correlates" / "precedes"
    confidence: float
```

**示例（track_h3 的隔离上下文）**：

```python
track_h3_private = TrackPrivateContext(
    track_id="track_h3",
    hypothesis_id="h3",
    
    hypothesis_evolution=[
        HypothesisVersion(
            round=0,
            hypothesis_text="连接池耗尽",
            status="pending",
            reasoning="初始假设，基于规则匹配",
            evidence_considered=[]
        ),
        HypothesisVersion(
            round=1,
            hypothesis_text="连接池耗尽，可能由慢查询引发",
            status="supported",
            reasoning="连接池95/100，与onset时间吻合",
            evidence_considered=["E_pool_001", "timeline_001"]
        ),
        HypothesisVersion(
            round=2,
            hypothesis_text="慢查询突增导致连接池耗尽",
            status="supported",
            reasoning="慢查询比故障早15秒，因果链完整",
            evidence_considered=["E_query_001", "E_pool_001", "timeline_001"]
        )
    ],
    
    reasoning_log=[
        ReasoningEntry(
            round=1,
            timestamp="2026-06-13T02:44:05Z",
            thought="时间线显示14:23:05开始故障，需要找前置事件",
            action="check_connection_pool_metrics",
            result="连接池95/100，吻合"
        ),
        ReasoningEntry(
            round=2,
            timestamp="2026-06-13T02:45:05Z",
            thought="连接池满是表象，需要找根因",
            action="check_slow_queries",
            result="14:22:50慢查询突增，比故障早15秒"
        ),
        ReasoningEntry(
            round=2,
            timestamp="2026-06-13T02:45:25Z",
            thought="因果链完整：慢查询→连接池满→新连接失败",
            action=None,
            result="假设成立，confidence=0.9"
        )
    ],
    
    causal_chain=CausalChain(
        nodes=[
            CausalNode(
                id="N1",
                event="慢查询突增",
                time="2026-06-12T14:22:50Z",
                evidence=["E_query_001"]
            ),
            CausalNode(
                id="N2",
                event="连接池积压",
                time="2026-06-12T14:23:05Z",
                evidence=["E_pool_001"]
            ),
            CausalNode(
                id="N3",
                event="新连接失败",
                time="2026-06-12T14:23:05Z",
                evidence=["timeline_001"]
            )
        ],
        edges=[
            CausalEdge(
                from_node="N1",
                to_node="N2",
                relationship="causes",
                confidence=0.8
            ),
            CausalEdge(
                from_node="N2",
                to_node="N3",
                relationship="causes",
                confidence=0.9
            )
        ],
        confidence=0.85  # min(edges)
    ),
    
    current_round=2,
    is_active=False  # 已得出supported结论
)
```

---

## 3. 中间合并结果（Lead内部）

**说明**：以下是 LeadOrchestrator 内部的中间数据格式，**并非** analysis.yaml 的最终输出格式。最终输出需经过 `map_to_l1_template()` 映射为 L1 模板格式（见 design-execution-flow.md）。

```yaml
# LeadOrchestrator.run() 的返回值（中间形态）

hypotheses:
  - id: h1
    description: "DNS解析失败"
    status: refuted
    confidence: 0.9
    evolution_summary: "初始怀疑DNS，验证后排除"
    key_reasoning_steps:
      - round: 1
        thought: "配置变更涉及域名，怀疑DNS"
        conclusion: "验证显示DNS正常，排除"

  - id: h3
    description: "慢查询导致连接池耗尽"
    status: supported
    confidence: 0.85
    evolution_summary: "从连接池表象深入到慢查询根因"
    key_reasoning_steps:
      - round: 1
        thought: "连接池95/100，与onset时间吻合"
        conclusion: "表象确认，需找根因"
      - round: 2
        thought: "慢查询比故障早15秒，因果链完整"
        conclusion: "根因确认"
    causal_chain:
      nodes:
        - event: "慢查询突增"
          time: "14:22:50"
        - event: "连接池积压"
          time: "14:23:05"
        - event: "新连接失败"
          time: "14:23:05"
      confidence: 0.85

reasoning_metadata:
  tracks_count: 3
  rounds_executed: 2
  termination_reason: "all_hypotheses_conclusive"
  reasoning_board_path: "./reasoning-board.yaml"
```

**此格式需映射为 L1 模板**：
- `id` → `hypothesis_id`
- `description` → `statement`
- 补充 `supporting_evidence`、`counter_evidence`、`disconfirming_conditions`、`evidence_gaps`、`validation_actions`
- 详见 `design-execution-flow.md` 中的 `map_to_l1_template()` 和 `blocker-1-complete-mapping.md`
```

---

## 4. 数据流动路径

```
[第3段证据包] 
    ↓
[reasoning-board.base_evidence] ← 所有轨读取
    ↓
[轨1隔离上下文] [轨2隔离上下文] [轨3隔离上下文]
    ↓               ↓               ↓
  推理            推理            推理
    ↓               ↓               ↓
写入 findings   写入 findings   写入 findings
    ↓               ↓               ↓
[reasoning-board] ← 所有轨共享
    ↓
[Lead 合并]
    ├─ 读取 reasoning-board（共享层）
    ├─ 读取所有轨的隔离上下文
    ├─ 选择最优因果链
    └─ 输出 analysis.yaml
```

---

## 5. Board → analysis.yaml 映射表（修复 P0-1）

**问题**：design 用的字段与 L1 模板 `core/templates/analysis.template.yaml` 不一致

**映射规则**：

| 设计层字段 | L1 模板字段 | 映射规则 |
|-----------|------------|---------|
| `track.hypothesis_id` | `hypothesis_id` | 直接映射 |
| `track.get_current_hypothesis()` | `statement` | 直接映射 |
| `board.hypothesis_status[h].status` | `validation_result` | 枚举一致：refuted/supported/insufficient |
| `board.hypothesis_status[h].confidence` (float) | `confidence` (enum) | **转换**：≥0.7→high, ≥0.4→medium, <0.4→low |
| `track.causal_chain` (CausalChain) | `causal_path` (List[str]) | **转换**：提取 nodes[].event → 列表 |
| `evolution_summary` | - | **软扩展**（可选，不被 review/finalize 依赖） |
| `key_reasoning_steps` | - | **软扩展** |
| `reasoning_metadata` | - | **软扩展** |

**置信度转换函数**：

```python
def confidence_float_to_enum(confidence: float) -> str:
    """float (0-1) → enum (high/medium/low)"""
    if confidence >= 0.7:
        return "high"
    elif confidence >= 0.4:
        return "medium"
    else:
        return "low"
```

**因果链转换函数**：

```python
def causal_chain_to_path(chain: CausalChain) -> List[str]:
    """CausalChain object → causal_path (List[str])"""
    if not chain or not chain.nodes:
        return []
    
    # 按拓扑序提取事件文本
    return [node.event for node in chain.nodes]

# 示例：
# chain.nodes = [
#   CausalNode(event="慢查询突增"),
#   CausalNode(event="连接池积压"),
#   CausalNode(event="新连接失败")
# ]
# → ["慢查询突增", "连接池积压", "新连接失败"]
```

**完整映射示例**：

```python
# 从 Board + Track → analysis.yaml

def map_to_analysis_yaml(track, board):
    hypothesis_status = board.get_hypothesis_status(track.hypothesis_id)
    
    return {
        "hypothesis_id": track.hypothesis_id,  # 直接映射
        "statement": track.get_current_hypothesis(),  # 直接映射
        "validation_result": hypothesis_status["status"],  # 枚举一致
        "confidence": confidence_float_to_enum(hypothesis_status["confidence"]),  # 转换
        "causal_path": causal_chain_to_path(track.causal_chain),  # 转换
        
        # 软扩展（可选，不影响现有流程）
        "evolution_summary": summarize_evolution(track),
        "key_reasoning_steps": extract_key_steps(track)
    }
```

---

## 6. Schema 版本管理

**reasoning-board.yaml 版本演进**：

```yaml
version: "1.0"  # 第一版MVP

# 未来版本可能新增：
# version: "1.1" - 新增 historical_cases 检索结果
# version: "1.2" - 新增 deep_analysis_branches
# version: "2.0" - 新增可视化元数据
```

**向后兼容策略**：
- 读取时检查 `version` 字段
- 旧版本缺失字段用默认值
- 新版本字段对旧版本不可见即可

---

## 7. 枚举用词统一（修复 P0-2）

| 概念 | 统一用词 | 类型 | 说明 |
|------|---------|------|------|
| 假设状态 | `refuted` / `supported` / `insufficient` / `pending` | 名词 | hypothesis_status.status |
| 发现类型 | `refutation` / `support` / `gap` / `observation` | 名词 | findings.type |
| 发现影响 | `refute` / `support` / `insufficient` / `observation` | 动词 | findings.affects[].impact |
| 置信度（内部） | `0.0 ~ 1.0` | float | 存储和计算用 |
| 置信度（对外） | `high` / `medium` / `low` | enum | analysis.yaml 输出 |
| 反证置信度 | `high` / `medium` / `low` | enum | cross_refutations.confidence |
