"""Phase 4 reasoning facade entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .multitrack.l1_mapper import L1TemplateMapper
from .multitrack.lead_orchestrator import LeadOrchestrator
from .renderer import format_analysis_output


def run_phase4_analysis(incident_dir: Path) -> Dict[str, Any]:
    """Run the Phase 4 multitrack reasoning flow for an incident directory."""
    incident_dir = Path(incident_dir)
    signal_bundle_path = incident_dir / "signal_bundle.yaml"
    if not signal_bundle_path.exists():
        raise FileNotFoundError("missing signal_bundle.yaml: %s" % signal_bundle_path)

    with signal_bundle_path.open("r", encoding="utf-8") as fh:
        signal_bundle = yaml.safe_load(fh) or {}

    mapper = L1TemplateMapper()
    abnormal_signals = signal_bundle.get("abnormal_signals") or []
    if abnormal_signals:
        primary_signal = abnormal_signals[0] if isinstance(abnormal_signals[0], dict) else {}
        symptom = str(primary_signal.get("detail") or "")
    else:
        symptom = "未知故障"

    l1_output = {
        "primary_symptom": symptom,
        "affected_component": signal_bundle.get("middleware", "mongodb"),
    }
    hypotheses = mapper.map_from_l1_output(l1_output)
    result = LeadOrchestrator(incident_dir, hypotheses).run()

    analysis = format_analysis_output(result, signal_bundle)
    analysis_path = incident_dir / "analysis.yaml"
    with analysis_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(analysis, fh, allow_unicode=True, sort_keys=False)
    return result

__all__ = ["run_phase4_analysis"]
