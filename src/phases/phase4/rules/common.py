"""Shared helpers for Phase 4 rule analysers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List
import sys

SRC_DIR = Path(__file__).resolve().parents[3]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from shared.io import load_yaml_object, write_yaml_object
from shared.workspace import runtime_root


def load_yaml(path: Path) -> Dict[str, Any]:
    return load_yaml_object(path)


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    write_yaml_object(path, payload)


def _unique_nonempty(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _incident_time_mode(input_data: Dict[str, Any]) -> str:
    incident_time = input_data.get("incident_time") or {}
    if isinstance(incident_time, dict):
        mode = str(incident_time.get("mode") or "").strip()
        if mode:
            return mode
    return "current_or_unknown"


def build_retrieval_context(
    input_data: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
) -> Dict[str, Any]:
    abnormal_signals = [item for item in signal_bundle.get("abnormal_signals") or [] if isinstance(item, dict)]
    evidence_gaps = [item for item in collection_report.get("evidence_gaps") or [] if isinstance(item, dict)]

    scenario_candidates = _unique_nonempty(
        [
            input_data.get("scenario"),
            input_data.get("primary_scenario"),
        ]
        + _as_list(input_data.get("scenario_candidates"))
    )
    signal_ids = _unique_nonempty(item.get("signal_id") for item in abnormal_signals)
    object_refs = _unique_nonempty(item.get("object_ref") or item.get("pod_ref") or item.get("node_ref") for item in abnormal_signals)
    evidence_gap_categories = _unique_nonempty(item.get("gap_category") or item.get("gap_type") for item in evidence_gaps)
    gap_text = _unique_nonempty(item.get("gap") for item in evidence_gaps)
    query_terms = _unique_nonempty(
        scenario_candidates
        + signal_ids
        + object_refs
        + evidence_gap_categories
        + gap_text
    )

    return {
        "query_text": " ".join(query_terms),
        "time_mode": _incident_time_mode(input_data),
        "scenario_candidates": scenario_candidates,
        "signal_ids": signal_ids,
        "object_refs": object_refs,
        "evidence_gap_categories": evidence_gap_categories,
    }


def source_boundaries() -> Dict[str, Any]:
    return {
        "current_incident_evidence": [
            "structured_record",
            "signal_bundle",
            "collection_report",
        ],
        "hypothesis_sources_only": [
            "customer_clue",
            "historical_experience",
            "runbook",
            "knowledge_asset",
        ],
        "rule": "hypothesis_sources_only must not be used as direct supporting evidence for conclusion_summary",
    }


def analysis_contract_fields(
    input_data: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "retrieval_context": build_retrieval_context(input_data, signal_bundle, collection_report),
        "experience_matches": [],
        "source_boundaries": source_boundaries(),
    }
