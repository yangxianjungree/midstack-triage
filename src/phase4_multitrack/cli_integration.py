"""Phase 4集成入口 - 被midstack-local.py调用"""

from pathlib import Path
from typing import Dict, Any
import yaml

from phase4_multitrack import LeadOrchestrator, L1TemplateMapper


def run_phase4_analysis(incident_dir: Path) -> Dict[str, Any]:
    """
    Phase 4分析入口 - 被midstack-local.py的command_analyse调用

    输入：incident_dir包含
        - signal_bundle.yaml (Phase 1-3收集的信号)
        - structured_record.yaml (结构化记录)

    输出：reasoning-board.yaml + analysis.yaml
    """
    incident_dir = Path(incident_dir)

    # 1. 读取Phase 1-3的输出
    signal_bundle_path = incident_dir / "signal_bundle.yaml"
    if not signal_bundle_path.exists():
        raise FileNotFoundError(f"缺少signal_bundle.yaml: {signal_bundle_path}")

    with open(signal_bundle_path) as f:
        signal_bundle = yaml.safe_load(f)

    # 2. 从signal_bundle生成初始假设
    mapper = L1TemplateMapper()

    abnormal_signals = signal_bundle.get("abnormal_signals", [])
    if abnormal_signals:
        primary_signal = abnormal_signals[0]
        symptom = primary_signal.get("detail", "")
    else:
        symptom = "未知故障"

    l1_output = {
        "primary_symptom": symptom,
        "affected_component": signal_bundle.get("middleware", "mongodb")
    }

    hypotheses = mapper.map_from_l1_output(l1_output)

    # 3. 运行多轨推理
    orchestrator = LeadOrchestrator(incident_dir, hypotheses)
    result = orchestrator.run()

    # 4. 生成analysis.yaml（符合L1模板格式）
    analysis = _format_analysis_output(result, signal_bundle)

    analysis_path = incident_dir / "analysis.yaml"
    with open(analysis_path, 'w') as f:
        yaml.dump(analysis, f, allow_unicode=True, sort_keys=False)

    return result


def _format_analysis_output(phase4_result: Dict, signal_bundle: Dict) -> Dict:
    """转换Phase 4输出为analysis.yaml格式"""
    # 找到置信度最高的假设
    hypotheses = phase4_result["hypotheses"]
    best_hypothesis = max(
        hypotheses,
        key=lambda h: h["status"].get("confidence", 0)
    )

    status = best_hypothesis["status"]["status"]
    confidence_map = {
        "supported": "high",
        "insufficient": "medium",
        "refuted": "low",
        "pending": "low"
    }

    return {
        "conclusion_summary": {
            "statement": best_hypothesis["final_text"],
            "confidence": confidence_map.get(status, "low"),
            "impact_scope": f"{signal_bundle.get('middleware', 'unknown')} availability",
            "primary_cause_category": "runtime-issue"
        },
        "reasoning_process": {
            "total_rounds": phase4_result["total_rounds"],
            "hypotheses_evaluated": len(hypotheses),
            "reasoning_board": "reasoning-board.yaml"
        }
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("用法: python phase4_cli.py <incident_dir>")
        sys.exit(1)

    incident_dir = Path(sys.argv[1])
    result = run_phase4_analysis(incident_dir)
    print(f"分析完成：{result['total_rounds']}轮推理")
    print(f"输出：{incident_dir}/analysis.yaml")
