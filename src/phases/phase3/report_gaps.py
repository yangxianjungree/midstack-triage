"""Phase 3 collection report gap helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from shared.workspace import load_yaml, now_iso, write_yaml


def infer_gap_type(gap_text: str, item: Dict[str, Any]) -> str:
    explicit = str(item.get("gap_type") or item.get("type") or "").strip()
    if explicit in ("expected_gap", "critical_gap"):
        return explicit
    text = gap_text.lower()
    if "critical_gap" in text or "critical gap" in text:
        return "critical_gap"
    if "log sink" in text or "real log" in text or "true log" in text or "logs too short" in text or "file log" in text or "application log source" in text:
        return "critical_gap"
    if "script output missing" in text or "remote executor" in text or "signal bundle depends" in text:
        return "critical_gap"
    if "rs.status" in text and any(token in text for token in ("no healthy", "all", "not collected from any", "missing")):
        return "critical_gap"
    if any(token in text for token in ("affected pod", "faulty pod", "bad pod", "current pod")) and ("rs.status" in text or "fatal tail" in text):
        return "expected_gap"
    return "expected_gap"


def normalize_collection_report_gaps(collection_report: Dict[str, Any]) -> None:
    normalized: List[Any] = []
    for item in collection_report.get("evidence_gaps") or []:
        if isinstance(item, dict):
            gap = str(item.get("gap") or item)
            item = dict(item)
            item["gap_type"] = infer_gap_type(gap, item)
            if not item.get("related_stage"):
                item["related_stage"] = "signal_collection"
            if not item.get("why_important"):
                item["why_important"] = "This gap affects evidence completeness."
            normalized.append(item)
        else:
            gap = str(item)
            normalized.append(
                {
                    "gap": gap,
                    "gap_type": infer_gap_type(gap, {}),
                    "related_stage": "signal_collection",
                    "why_important": "This gap affects evidence completeness.",
                }
            )
    collection_report["evidence_gaps"] = normalized


def gap_closed_by_file_tail(gap_text: str) -> bool:
    text = gap_text.lower()
    return (
        ("file-backed" in text or "file log" in text or "log sink" in text or "application logs" in text)
        and any(token in text for token in ("kubectl logs", "collect", "not proven", "may only appear", "insufficient"))
    )


def drop_closed_evidence_gaps(structured_record: Dict[str, Any], collection_report: Dict[str, Any]) -> None:
    details = structured_record.get("details") or {}
    has_file_tail = any(isinstance(item, dict) and str(item.get("log_type") or "") == "file_tail" for item in details.get("raw_logs") or []) or bool(isinstance(details.get("processed_logs"), dict) and (details.get("processed_logs") or {}).get("file_tail_highlights"))
    if not has_file_tail:
        return
    kept: List[Any] = []
    for item in collection_report.get("evidence_gaps") or []:
        gap_text = str((item or {}).get("gap") if isinstance(item, dict) else item)
        if gap_closed_by_file_tail(gap_text):
            continue
        kept.append(item)
    collection_report["evidence_gaps"] = kept


def record_recollection_skill_pool_miss(output_dir: Path) -> None:
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    collection_report.setdefault("warnings", []).append(
        "directed recollection fell back to legacy script selection because matched skill pool did not cover triggered playbooks (gap_type=skill_pool_miss)"
    )
    collection_report["updated_at"] = now_iso()
    write_yaml(output_dir / "collection_report.yaml", collection_report)
