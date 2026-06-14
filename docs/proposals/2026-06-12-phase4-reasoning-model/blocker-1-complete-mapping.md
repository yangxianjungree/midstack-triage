---
status: critical-fix
last_updated: 2026-06-13
purpose: 完整 Board → analysis.yaml (L1 模板) 映射规范
---

# 完整 analysis.yaml 映射规范（修复阻塞点1）

## L1 模板完整字段清单

```yaml
hypotheses:
  - hypothesis_id
    statement
    causal_path: [...]
    supporting_evidence: [...]       # ← 缺失
    counter_evidence: [...]          # ← 缺失
    disconfirming_conditions: [...]  # ← 缺失
    evidence_gaps: [...]             # ← 缺失
    validation_actions: [...]        # ← 缺失
    validation_result

conclusion_summary:
  statement
  confidence
  impact_scope
  primary_cause_category            # ← 缺失
  evidence: [...]                   # ← 缺失
  limitations: [...]

next_actions: [...]                 # ← 缺失
knowledge_candidates: [...]         # ← 缺失
generated_at
updated_at
```

---

## 完整映射函数

```python
def map_to_l1_template(result: Dict, board: ReasoningBoard, incident_dir: Path) -> Dict:
    """完整映射到 L1 模板（修复阻塞点1）"""
    
    return {
        "hypotheses": [
            map_hypothesis_to_l1(h, board)
            for h in result["hypotheses"]
        ],
        "conclusion_summary": map_conclusion_to_l1(result, board),
        "next_actions": extract_next_actions(result, board),
        "knowledge_candidates": extract_knowledge_candidates(result, board),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

def map_hypothesis_to_l1(hypothesis: Dict, board: ReasoningBoard) -> Dict:
    """映射单个假设到 L1 格式"""
    hypothesis_id = hypothesis["id"]
    
    # 从 board 提取该假设相关的所有数据
    findings = board.get_findings_for_hypothesis(hypothesis_id)
    validations = board.get_validations_for_hypothesis(hypothesis_id)
    
    return {
        "hypothesis_id": hypothesis_id,
        "statement": hypothesis["description"],
        "causal_path": causal_chain_to_path(hypothesis.get("causal_chain")),
        
        # 支持证据：从 findings(support) 提取
        "supporting_evidence": extract_supporting_evidence(findings, board),
        
        # 反证：从 findings(refutation) 提取
        "counter_evidence": extract_counter_evidence(findings, board),
        
        # 反证条件：从假设逻辑推导
        "disconfirming_conditions": extract_disconfirming_conditions(hypothesis),
        
        # 证据缺口：从 evidence_gaps 提取
        "evidence_gaps": extract_evidence_gaps_for_hypothesis(hypothesis_id, board),
        
        # 验证动作：从 validation_queue 提取
        "validation_actions": extract_validation_actions(validations),
        
        # 验证结果
        "validation_result": hypothesis["status"]  # refuted/supported/insufficient
    }

def extract_supporting_evidence(findings: List[Dict], board: ReasoningBoard) -> List[Dict]:
    """提取支持证据（修复阻塞点1）"""
    evidence_list = []
    
    for f in findings:
        if f["type"] in ["support", "observation"]:
            # 从 finding.evidence 引用的 executed_validations 提取详情
            for evidence_id in f.get("evidence", []):
                val_result = board.get_validation_result_data(evidence_id)
                if val_result:
                    evidence_list.append({
                        "source": val_result.get("action", "unknown"),
                        "detail": val_result.get("result", f["content"])
                    })
                else:
                    # 如果是来自 base_evidence 的引用
                    evidence_list.append({
                        "source": "structured_record",
                        "detail": f["content"]
                    })
    
    return evidence_list if evidence_list else [{"source": "none", "detail": "无直接支持证据"}]

def extract_counter_evidence(findings: List[Dict], board: ReasoningBoard) -> List[Dict]:
    """提取反证"""
    counter_list = []
    
    for f in findings:
        if f["type"] == "refutation":
            for evidence_id in f.get("evidence", []):
                val_result = board.get_validation_result_data(evidence_id)
                if val_result:
                    counter_list.append({
                        "source": val_result.get("action", "validation"),
                        "detail": val_result.get("result", f["content"])
                    })
                else:
                    counter_list.append({
                        "source": "observation",
                        "detail": f["content"]
                    })
    
    return counter_list

def extract_disconfirming_conditions(hypothesis: Dict) -> List[str]:
    """提取反证条件（逻辑推导）"""
    # 基于假设类型推导反证条件
    statement = hypothesis["description"].lower()
    conditions = []
    
    if "dns" in statement:
        conditions.append("DNS 响应正常且延迟低于阈值")
    if "连接池" in statement or "connection pool" in statement:
        conditions.append("连接池未满载（<80%）")
    if "网络" in statement or "network" in statement:
        conditions.append("网络连通性正常，无丢包")
    if "慢查询" in statement or "slow query" in statement:
        conditions.append("查询响应时间在基线范围内")
    
    if not conditions:
        conditions.append("存在其他完整因果链解释现象")
    
    return conditions

def extract_evidence_gaps_for_hypothesis(hypothesis_id: str, board: ReasoningBoard) -> List[str]:
    """提取证据缺口"""
    gaps = []
    
    # 从 findings(gap) 提取
    findings = board.get_findings_for_hypothesis(hypothesis_id)
    for f in findings:
        if f["type"] == "gap":
            gap_detail = f.get("gap_detail", {})
            gaps.append(gap_detail.get("missing", f["content"]))
    
    # 从 board.evidence_gaps 提取
    for gap in board._data.get("evidence_gaps", []):
        if hypothesis_id in gap.get("related_hypotheses", []):
            gaps.append(gap["gap"])
    
    return gaps if gaps else []

def extract_validation_actions(validations: List[Dict]) -> List[Dict]:
    """提取验证动作"""
    actions = []
    
    for v in validations:
        status_map = {
            "pending": "planned",
            "executing": "planned",
            "completed": "executed",
            "failed": "blocked"
        }
        
        actions.append({
            "action": v["action"],
            "status": status_map.get(v["status"], "planned"),
            "result": v.get("result", "") if v["status"] == "completed" else ""
        })
    
    return actions

def map_conclusion_to_l1(result: Dict, board: ReasoningBoard) -> Dict:
    """映射 conclusion_summary（修复阻塞点1）"""
    supported = [h for h in result["hypotheses"] if h["status"] == "supported"]
    
    if supported:
        primary = supported[0]
        
        return {
            "statement": f"根因：{primary['description']}",
            "confidence": confidence_float_to_enum(primary["confidence"]),
            "impact_scope": extract_impact_scope(primary, board),
            "primary_cause_category": determine_cause_category(primary),  # 新增
            "evidence": extract_key_evidence(primary, board),              # 新增
            "limitations": extract_limitations(result["hypotheses"], board)
        }
    else:
        return {
            "statement": "所有假设均未确认",
            "confidence": "low",
            "impact_scope": {},
            "primary_cause_category": "unknown",
            "evidence": [],
            "limitations": ["证据不足以确定根因"]
        }

def determine_cause_category(hypothesis: Dict) -> str:
    """判断原因类别（修复阻塞点1）
    
    使用 core/taxonomies/cause-categories.yaml 的枚举
    """
    desc_lower = hypothesis["description"].lower()
    
    # 配置类
    if any(k in desc_lower for k in ["配置", "参数", "环境变量", "config"]):
        return "configuration"
    
    # 资源类
    if any(k in desc_lower for k in ["连接池", "内存", "cpu", "磁盘", "pool", "resource"]):
        return "resource_exhaustion"
    
    # 性能类
    if any(k in desc_lower for k in ["慢查询", "延迟", "slow", "latency", "performance"]):
        return "performance_degradation"
    
    # 网络类
    if any(k in desc_lower for k in ["网络", "连接", "超时", "network", "connection", "timeout"]):
        return "network_issue"
    
    # 代码类
    if any(k in desc_lower for k in ["代码", "逻辑", "bug", "code", "logic"]):
        return "code_defect"
    
    return "other"

def extract_key_evidence(hypothesis: Dict, board: ReasoningBoard) -> List[str]:
    """提取关键证据（修复阻塞点1）"""
    evidence_list = []
    
    findings = board.get_findings_for_hypothesis(hypothesis["id"])
    
    # 只取 support 类型的 finding
    for f in findings:
        if f["type"] == "support":
            evidence_list.append(f["content"])
    
    # 最多返回前3条最关键的
    return evidence_list[:3] if evidence_list else ["无明确支持证据"]

def extract_impact_scope(hypothesis: Dict, board: ReasoningBoard) -> str:
    """提取影响范围（简化实现）"""
    # 从 timeline 或 signal_bundle 提取
    # 简化：返回字符串描述
    return "受影响组件：MongoDB, 连接池"

def extract_next_actions(result: Dict, board: ReasoningBoard) -> List[Dict]:
    """提取后续动作（修复阻塞点1）"""
    actions = []
    
    supported = [h for h in result["hypotheses"] if h["status"] == "supported"]
    insufficient = [h for h in result["hypotheses"] if h["status"] == "insufficient"]
    
    # 从 supported 假设推导修复动作
    if supported:
        primary = supported[0]
        desc_lower = primary["description"].lower()
        
        if "慢查询" in desc_lower:
            actions.append({
                "action": "优化慢查询或增加索引",
                "risk_level": "low-risk",
                "requires_confirmation": True
            })
        if "连接池" in desc_lower:
            actions.append({
                "action": "调整连接池大小或超时参数",
                "risk_level": "low-risk",
                "requires_confirmation": True
            })
    
    # 从 insufficient 假设推导验证动作
    if insufficient:
        actions.append({
            "action": f"补充验证 {len(insufficient)} 个证据不足的假设",
            "risk_level": "read-only",
            "requires_confirmation": False
        })
    
    # 从 evidence_gaps 推导
    gaps = board._data.get("evidence_gaps", [])
    for gap in gaps[:2]:  # 最多2个
        if gap.get("can_resolve", False):
            actions.append({
                "action": f"采集缺失证据：{gap['gap']}",
                "risk_level": "read-only",
                "requires_confirmation": False
            })
    
    return actions if actions else [{
        "action": "人工复核验证结论",
        "risk_level": "read-only",
        "requires_confirmation": True
    }]

def extract_knowledge_candidates(result: Dict, board: ReasoningBoard) -> List[Dict]:
    """提取知识候选（修复阻塞点1）"""
    candidates = []
    
    # 从 supported 假设生成 runbook 候选
    supported = [h for h in result["hypotheses"] if h["status"] == "supported"]
    for h in supported:
        candidates.append({
            "candidate_id": f"runbook_{h['id']}",
            "candidate_type": "runbook",
            "title": f"排查与修复：{h['description']}",
            "reason": "该假设被验证支持，可沉淀为 runbook",
            "suggested_path": f"domains/mongodb/runbooks/{slugify(h['description'])}.yaml"
        })
    
    # 从验证动作生成 script 候选
    validations = board._data.get("validation_queue", [])
    completed_validations = [v for v in validations if v["status"] == "completed"]
    if len(completed_validations) >= 2:
        candidates.append({
            "candidate_id": "script_batch_validation",
            "candidate_type": "script",
            "title": "批量验证脚本：常见假设验证",
            "reason": f"本次执行了 {len(completed_validations)} 个验证动作，可封装为脚本",
            "suggested_path": "domains/mongodb/scripts/batch-hypothesis-validation.sh"
        })
    
    return candidates

def slugify(text: str) -> str:
    """文本转 slug"""
    import re
    text = text.lower().replace(" ", "-")
    return re.sub(r'[^a-z0-9-]', '', text)[:50]
```

---

## ReasoningBoard 需新增方法

```python
class ReasoningBoard:
    # ... 现有方法
    
    def get_findings_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取某假设相关的所有 findings"""
        return [
            f for f in self._data["findings"]
            if any(a["hypothesis"] == hypothesis_id for a in f.get("affects", []))
        ]
    
    def get_validations_for_hypothesis(self, hypothesis_id: str) -> List[Dict]:
        """获取某假设请求的验证动作"""
        # 找到该假设对应的 track_id
        track_id = f"track_{hypothesis_id}"
        
        return [
            v for v in self._data["validation_queue"]
            if track_id in v.get("requested_by", [])
        ]
```

---

## deepest_supported_level 枚举修正（修复阻塞点1）

**错误**：设计用 `platform/infra/app/code`  
**正确**：L1 要求 `phenomenon/impact/mechanism/root_cause`

```python
def determine_deepest_level(hypothesis: Dict) -> str:
    """判断假设支持到的最深层级
    
    正确枚举（core/taxonomies/analysis-depth-levels.yaml）:
    - phenomenon: 观察到现象
    - impact: 识别影响
    - mechanism: 理解机制
    - root_cause: 找到根因
    """
    desc_lower = hypothesis["description"].lower()
    status = hypothesis.get("status")
    causal_chain = hypothesis.get("causal_chain")
    
    # 只有 supported 且有完整因果链才算 root_cause
    if status == "supported" and causal_chain and len(causal_chain.get("nodes", [])) >= 3:
        return "root_cause"
    
    # 有因果链但未完全验证 → mechanism
    if causal_chain:
        return "mechanism"
    
    # 识别了受影响组件 → impact
    if any(k in desc_lower for k in ["影响", "故障", "失败", "impact", "failure"]):
        return "impact"
    
    # 否则只是现象
    return "phenomenon"
```
