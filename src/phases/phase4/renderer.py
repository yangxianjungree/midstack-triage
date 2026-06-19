"""Render Phase 4 reasoning outputs into persisted analysis contracts."""

from __future__ import annotations

from typing import Any, Dict

from .analysis_contract import analysis_contract_fields
from .reasoning_timeline import build_reasoning_timeline


def format_analysis_output(phase4_result: Dict[str, Any], signal_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """Render multitrack reasoning output into the Phase 4 analysis contract."""
    hypotheses = phase4_result["hypotheses"]
    best_hypothesis = max(hypotheses, key=lambda item: item["status"].get("confidence", 0))
    status = best_hypothesis["status"]["status"]
    confidence_map = {
        "supported": "high",
        "insufficient": "medium",
        "refuted": "low",
        "pending": "low",
    }
    return {
        "conclusion_summary": {
            "statement": best_hypothesis["final_text"],
            "confidence": confidence_map.get(status, "low"),
            "impact_scope": "%s availability" % signal_bundle.get("middleware", "unknown"),
            "primary_cause_category": "runtime-issue",
        },
        "reasoning_process": {
            "total_rounds": phase4_result["total_rounds"],
            "hypotheses_evaluated": len(hypotheses),
            "reasoning_board": "reasoning-board.yaml",
        },
        "reasoning_timeline": build_reasoning_timeline(signal_bundle, {"evidence_gaps": []}, {}, []),
        **analysis_contract_fields(signal_bundle, signal_bundle, {"evidence_gaps": []}),
    }
