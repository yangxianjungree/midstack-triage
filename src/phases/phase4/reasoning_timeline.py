"""Build Phase 4 reasoning timeline from current incident evidence."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


def _text(value: Any) -> str:
    return str(value or "").strip()


def _log_local_time(message: str) -> str:
    match = re.search(r"(?:^|\bmongodb\s+|\s)(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)\b", message or "")
    return match.group(1) if match else ""


def _event_time_from_log_highlight(item: Dict[str, Any], message: str) -> Dict[str, str]:
    exact_time = _text(item.get("time") or item.get("timestamp") or item.get("observed_at"))
    if exact_time:
        return {"time": exact_time, "time_precision": "exact"}
    local_time = _log_local_time(message)
    if local_time:
        return {"time": local_time, "time_precision": "log_local_time"}
    return {"time": "", "time_precision": "observed_at_collection"}


def _event_type_priority(event_type: str) -> int:
    priorities = {
        "replica-set-split-brain": 0,
        "current-tcp-reachability": 1,
        "dns-log-highlight": 2,
    }
    if str(event_type or "").startswith("log-highlight-"):
        return 3
    return priorities.get(str(event_type or ""), 9)


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


def _replica_member_diagnostic_events(structured_record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    by_replica_set: Dict[str, List[Dict[str, Any]]] = {}
    for item in details.get("replica_members") or []:
        if not isinstance(item, dict):
            continue
        replica_set_id = _text(item.get("replica_set_id")) or "unknown"
        by_replica_set.setdefault(replica_set_id, []).append(item)
    for replica_set_id, members in sorted(by_replica_set.items()):
        primary_views = 0
        quorum_counts = set()
        config_views = set()
        for item in members:
            self_member = item.get("self_member") or {}
            if _text(self_member.get("state_str")).upper() == "PRIMARY":
                primary_views += 1
            quorum = item.get("voting_members_count")
            if quorum not in (None, ""):
                quorum_counts.add(str(quorum))
            config_version = self_member.get("config_version")
            config_term = self_member.get("config_term")
            if config_version not in (None, "") or config_term not in (None, ""):
                config_views.add("%s/%s" % (_text(config_version), _text(config_term)))
        if primary_views >= 2 and (len(quorum_counts) > 1 or len(config_views) > 1):
            yield {
                "time_precision": "observed_at_collection",
                "layer": "diagnostic",
                "object_ref": replica_set_id,
                "event_type": "replica-set-split-brain",
                "summary": "Replica set %s split-brain observed: %s PRIMARY views and divergent voting quorum counts." % (replica_set_id, primary_views),
                "source": "structured_record.details.replica_members",
                "evidence_ref": "replica_members:%s" % replica_set_id,
                "confidence": "high",
            }


def _network_diagnostic_events(structured_record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    network_overlay = details.get("network_overlay") or {}
    checks = network_overlay.get("pod_connectivity_checks") or []
    success = [
        item
        for item in checks
        if isinstance(item, dict)
        and _text(item.get("status")).lower() == "success"
        and str(item.get("target_port") or "") == "27017"
    ]
    if success:
        yield {
            "time_precision": "observed_at_collection",
            "layer": "diagnostic",
            "event_type": "current-tcp-reachability",
            "summary": "Current TCP/27017 reachability succeeded after divergent replica-set views were observed.",
            "source": "structured_record.details.network_overlay.pod_connectivity_checks",
            "evidence_ref": "network_overlay.pod_connectivity_checks",
            "confidence": "medium",
        }


def _log_highlight_diagnostic_events(signal_bundle: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in signal_bundle.get("log_highlights") or []:
        if not isinstance(item, dict):
            continue
        text = _text(item.get("message") or item.get("detail"))
        lowered = text.lower()
        category = _text(item.get("category") or "log")
        material = category in ("election", "connection", "timeout", "fatal", "storage", "error", "resource") or any(
            token in lowered
            for token in (
                "cannot resolve host",
                "hostunreachable",
                "connection refused",
                "setting node as primary",
                "setting node as secondary",
                "primary node ready",
                "wiredtiger",
                "segmentation fault",
                "unclean shutdown",
                "i/o timeout",
                "timed out",
            )
        )
        if not material:
            continue
        time_fields = _event_time_from_log_highlight(item, text)
        dns_failure = (
            ("dns" in lowered or "10.96.0.10:53" in lowered or "lookup " in lowered)
            and ("connection refused" in lowered or "timeout" in lowered or "i/o timeout" in lowered)
        )
        event_type = "dns-log-highlight" if dns_failure else "log-highlight-%s" % category
        if dns_failure:
            summary = "DNS lookup failure observed in logs: %s" % text
        else:
            summary = "MongoDB log highlight on %s: %s" % (_text(item.get("pod_ref") or item.get("object_ref")) or "unknown", text)
        yield {
            "time": time_fields["time"],
            "time_precision": time_fields["time_precision"],
            "layer": "diagnostic",
            "object_ref": item.get("pod_ref") or item.get("object_ref"),
            "event_type": event_type,
            "summary": summary,
            "source": "signal_bundle.log_highlights",
            "evidence_ref": item.get("category") or event_type,
            "confidence": "medium",
        }


def _diagnostic_events(signal_bundle: Dict[str, Any], structured_record: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    yield from _replica_member_diagnostic_events(structured_record)
    yield from _network_diagnostic_events(structured_record)
    yield from _log_highlight_diagnostic_events(signal_bundle)


def build_reasoning_timeline(
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
    structured_record: Dict[str, Any] = None,
    hypotheses: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    for source_events in (
        _diagnostic_events(signal_bundle, structured_record or {}),
        _timeline_summary_events(signal_bundle),
        _signal_events(signal_bundle),
        _kubernetes_event_events(structured_record or {}),
        _collection_action_events(collection_report),
    ):
        for event in source_events:
            _append_event(events, event)

    layer_priority = {"diagnostic": 0, "signal": 1, "kubernetes": 2, "analysis": 3, "collection": 4}
    events.sort(
        key=lambda item: (
            layer_priority.get(item.get("layer") or "", 9),
            _event_type_priority(item.get("event_type") or ""),
            item.get("time") == "",
            item.get("time") or "",
            item.get("summary") or "",
        )
    )
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
