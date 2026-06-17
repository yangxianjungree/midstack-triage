"""Phase 4 reasoning facade entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from .multitrack.lead_orchestrator import LeadOrchestrator
from .planner import plan_initial_hypotheses
from .renderer import format_analysis_output


def run_phase4_analysis(incident_dir: Path) -> Dict[str, Any]:
    """Run the Phase 4 multitrack reasoning flow for an incident directory."""
    incident_dir = Path(incident_dir)
    signal_bundle_path = incident_dir / "signal_bundle.yaml"
    if not signal_bundle_path.exists():
        raise FileNotFoundError("missing signal_bundle.yaml: %s" % signal_bundle_path)

    with signal_bundle_path.open("r", encoding="utf-8") as fh:
        signal_bundle = yaml.safe_load(fh) or {}

    hypotheses = plan_initial_hypotheses(signal_bundle)
    result = LeadOrchestrator(incident_dir, hypotheses).run()

    analysis = format_analysis_output(result, signal_bundle)
    analysis_path = incident_dir / "analysis.yaml"
    with analysis_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(analysis, fh, allow_unicode=True, sort_keys=False)
    return result

__all__ = ["run_phase4_analysis"]
