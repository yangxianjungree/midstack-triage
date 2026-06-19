"""Build Phase 4 reasoning timeline from current incident evidence."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _text(value: Any) -> str:
    return str(value or "").strip()


def _append_event(events: List[Dict[str, Any]], event: Dict[str, Any]) -> None:
    summary = _text(event.get("summary"))
    if not summary:
        return
    normalized = {
        "time": _text(event.get("time")),
        "time_precision": _text(event.get("time_precision")) or "unknown",
        "layer": _text(event.get("layer")) or "analysis",
        "object_ref": _text(event.get("object_ref")),
        "event_type": _text(event.get("event_type")),
        "summary": summary,
        "source": _text(event.get("source")),
        "evidence_ref": _text(event.get("evidence_ref")),
        "confidence": _text(event.get("confidence")) or "medium",
    }
    key = (normalized["time"], normalized["layer"], normalized["summary"], normalized["source"])
    for item in events:
        if (item.get("time"), item.get("layer"), item.get("summary"), item.get("source")) == key:
            return
    events.append(normalized)


def _timeline_summary_events(signal_bundle: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in signal_bundle.get("timeline_summary") or []:
        if isinstance(item, dict):
            yield {
                "time": item.get("time") or item.get("timestamp"),
                "time_precision": item.get("time_precision") or ("exact" if item.get("time") or item.get("timestamp") else "unknown"),
                "layer": item.get("layer") or "analysis",
                "object_ref": item.get("object_ref"),
                "event_type": item.get("event_type") or "timeline-summary",
                "summary": item.get("summary") or item.get("detail") or item,
                "source": "signal_bundle.timeline_summary",
                "evidence_ref": item.get("evidence_ref"),
                "confidence": item.get("confidence") or "medium",
            }
        else:
            yield {
                "time_precision": "unknown",
                "layer": "analysis",
                "event_type": "timeline-summary",
                "summary": item,
                "source": "signal_bundle.timeline_summary",
                "confidence": "medium",
            }


def _signal_events(signal_bundle: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(item, dict):
            continue
        signal_id = _text(item.get("signal_id"))
        detail = _text(item.get("detail"))
        yield {
            "time": item.get("observed_at") or item.get("time") or item.get("timestamp"),
            "time_precision": "exact" if item.get("observed_at") or item.get("time") or item.get("timestamp") else "unknown",
            "layer": item.get("layer") or "signal",
            "object_ref": item.get("object_ref") or item.get("pod_ref") or item.get("node_ref"),
            "event_type": signal_id,
            "summary": "%s: %s" % (signal_id, detail) if detail else signal_id,
            "source": "signal_bundle.abnormal_signals",
            "evidence_ref": signal_id,
            "confidence": "high" if str(item.get("severity") or "") == "high" else "medium",
        }


def _kubernetes_event_events(structured_record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    for item in details.get("events") or []:
        if not isinstance(item, dict):
            continue
        involved = item.get("involved_object") or {}
        object_ref = _text(involved.get("name") or item.get("name"))
        reason = _text(item.get("reason"))
        message = _text(item.get("message"))
        yield {
            "time": item.get("last_timestamp") or item.get("event_time") or item.get("first_timestamp") or item.get("timestamp"),
            "time_precision": "exact" if item.get("last_timestamp") or item.get("event_time") or item.get("first_timestamp") or item.get("timestamp") else "unknown",
            "layer": "kubernetes",
            "object_ref": object_ref,
            "event_type": reason,
            "summary": "%s on %s: %s" % (reason, object_ref or "unknown", message),
            "source": "structured_record.details.events",
            "evidence_ref": reason,
            "confidence": "high",
        }


def _collection_action_events(collection_report: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in collection_report.get("collection_actions") or []:
        if not isinstance(item, dict):
            continue
        action_id = _text(item.get("action_id") or item.get("name"))
        status = _text(item.get("status"))
        target = _text(item.get("target"))
        yield {
            "time": item.get("performed_at") or item.get("started_at") or item.get("completed_at"),
            "time_precision": "exact" if item.get("performed_at") or item.get("started_at") or item.get("completed_at") else "unknown",
            "layer": "collection",
            "object_ref": target,
            "event_type": action_id,
            "summary": "collection %s status=%s target=%s" % (action_id, status or "unknown", target or "unknown"),
            "source": "collection_report.collection_actions",
            "evidence_ref": action_id,
            "confidence": "high" if status == "success" else "medium",
        }


def build_reasoning_timeline(
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
    structured_record: Dict[str, Any] = None,
    hypotheses: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    for source_events in (
        _timeline_summary_events(signal_bundle),
        _signal_events(signal_bundle),
        _kubernetes_event_events(structured_record or {}),
        _collection_action_events(collection_report),
    ):
        for event in source_events:
            _append_event(events, event)

    events.sort(key=lambda item: (item.get("time") == "", item.get("time") or "", item.get("layer") or "", item.get("summary") or ""))
    supported_hypotheses = [
        _text(item.get("hypothesis_id"))
        for item in hypotheses or []
        if isinstance(item, dict) and str(item.get("status") or item.get("validation_result") or "") == "supported"
    ]
    findings = []
    if events:
        findings.append(
            {
                "statement": "Timeline order is available for correlating symptoms, collection actions, and hypotheses.",
                "supports": supported_hypotheses,
                "refutes": [],
                "related_hypotheses": supported_hypotheses,
            }
        )
    else:
        findings.append(
            {
                "statement": "No timeline evidence was available in the current incident artifacts.",
                "supports": [],
                "refutes": [],
                "related_hypotheses": [],
            }
        )
    return {"events": events, "findings": findings}
