"""Phase 3 scenario routing helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from shared.scenario_router import infer_scenario
from shared.workspace import load_yaml, now_iso, write_yaml


def apply_scenario_routing_if_needed(output_dir: Path, args) -> Dict[str, Any]:
    input_file = output_dir / "input.yaml"
    signal_bundle_file = output_dir / "signal_bundle.yaml"
    if not input_file.exists() or not signal_bundle_file.exists():
        return load_yaml(input_file) if input_file.exists() else {}

    input_data = load_yaml(input_file)
    existing_scenario = str(input_data.get("scenario") or "unknown")
    if existing_scenario not in ("", "unknown", "baseline"):
        return input_data

    structured_record_file = output_dir / "structured_record.yaml"
    structured_record = load_yaml(structured_record_file) if structured_record_file.exists() else {}
    signal_bundle = load_yaml(signal_bundle_file)
    routing = infer_scenario(
        signal_bundle,
        structured_record=structured_record,
        customer_clue=str(input_data.get("customer_clue") or getattr(args, "customer_clue", "") or ""),
        middleware=str(input_data.get("middleware") or "mongodb"),
    )
    input_data["scenario"] = routing["scenario"]
    input_data["scenario_inference"] = routing["scenario_inference"]
    input_data["updated_at"] = now_iso()
    write_yaml(input_file, input_data)
    args.scenario = routing["scenario"]
    return input_data
