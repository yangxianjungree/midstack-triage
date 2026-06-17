"""Plan Phase 4 initial hypotheses from Phase 3 signal bundles."""

from __future__ import annotations

from typing import Any, Dict, List

from .multitrack.l1_mapper import L1TemplateMapper


def build_l1_output(signal_bundle: Dict[str, Any]) -> Dict[str, Any]:
    abnormal_signals = signal_bundle.get("abnormal_signals") or []
    if abnormal_signals:
        primary_signal = abnormal_signals[0] if isinstance(abnormal_signals[0], dict) else {}
        symptom = str(primary_signal.get("detail") or "")
    else:
        symptom = "未知故障"
    return {
        "primary_symptom": symptom,
        "affected_component": signal_bundle.get("middleware", "mongodb"),
    }


def plan_initial_hypotheses(signal_bundle: Dict[str, Any]) -> List[str]:
    mapper = L1TemplateMapper()
    return mapper.map_from_l1_output(build_l1_output(signal_bundle))
