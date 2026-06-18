"""Phase 4 reasoning facade entrypoint."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .multitrack.lead_orchestrator import LeadOrchestrator
from .planner import plan_initial_hypotheses
from .renderer import format_analysis_output
from shared.io import load_yaml_object, write_yaml_object


def load_signal_bundle(incident_dir: Path) -> Dict[str, Any]:
    signal_bundle_path = incident_dir / "signal_bundle.yaml"
    if not signal_bundle_path.exists():
        raise FileNotFoundError("missing signal_bundle.yaml: %s" % signal_bundle_path)

    return load_yaml_object(signal_bundle_path)


def write_analysis(incident_dir: Path, analysis: Dict[str, Any]) -> None:
    analysis_path = incident_dir / "analysis.yaml"
    write_yaml_object(analysis_path, analysis, allow_unicode=True)


def run_phase4_analysis(incident_dir: Path) -> Dict[str, Any]:
    """Run the Phase 4 multitrack reasoning flow for an incident directory."""
    incident_dir = Path(incident_dir)
    signal_bundle = load_signal_bundle(incident_dir)
    hypotheses = plan_initial_hypotheses(signal_bundle)
    result = LeadOrchestrator(incident_dir, hypotheses).run()

    analysis = format_analysis_output(result, signal_bundle)
    write_analysis(incident_dir, analysis)
    return result

__all__ = ["load_signal_bundle", "run_phase4_analysis", "write_analysis"]
