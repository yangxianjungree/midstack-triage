"""MongoDB log-highlight evidence helpers for Phase 4 rules."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple


def log_highlight_signature(message: str) -> str:
    text = message.lower()
    host_match = re.search(r'"host"\s*:\s*"([^"]+)"', message)
    if "cannot resolve host" in text:
        quoted = re.search(r'cannot resolve host "([^"]+)"', message)
        host = quoted.group(1) if quoted else ""
        return "dns-lookup:%s" % host
    if "hostunreachable" in text or "host failed in replica set" in text or "rsm received error response" in text:
        return "peer-unreachable:%s" % (host_match.group(1) if host_match else "")
    if "connection refused" in text:
        return "connection-refused:%s" % (host_match.group(1) if host_match else "")
    if "wiredtiger" in text:
        return "wiredtiger"
    if "segmentation fault" in text:
        return "segmentation-fault"
    normalized = re.sub(r"\d{2,}", "<n>", text)
    return normalized[:180]


def log_highlight_is_material(item: Dict[str, Any]) -> bool:
    category = str(item.get("category") or "")
    message = str(item.get("message") or "")
    if category in ("fatal", "storage", "error", "timeout", "connection", "resource"):
        return True
    text = message.lower()
    return any(
        token in text
        for token in (
            "cannot resolve host",
            "hostunreachable",
            "connection refused",
            "wiredtiger",
            "segmentation fault",
            "unclean shutdown",
            "i/o timeout",
            "timed out",
        )
    )


def log_highlight_priority(item: Dict[str, Any]) -> int:
    message = str(item.get("message") or "").lower()
    log_type = str(item.get("log_type") or "")
    category = str(item.get("category") or "")
    score = 0
    if log_type == "file_tail":
        score += 50
    if category in ("fatal", "storage", "resource"):
        score += 80
    if "hostunreachable" in message or "host failed in replica set" in message or "rsm received error response" in message:
        score += 70
    if "cannot resolve host" in message:
        score += 65
    if "connection refused" in message:
        score += 35
    if "10.96.0.10:53" in message:
        score += 20
    if "timeout reached before the port went into state" in message:
        score -= 20
    return score


def evidence_from_log_highlights(signal_bundle: Dict[str, Any], limit: int = 12) -> List[Dict[str, str]]:
    evidence: List[Dict[str, str]] = []
    seen: Set[Tuple[str, str, str, str]] = set()
    candidates = [item for item in signal_bundle.get("log_highlights") or [] if isinstance(item, dict)]
    candidates.sort(key=log_highlight_priority, reverse=True)
    for item in candidates:
        if not isinstance(item, dict) or not log_highlight_is_material(item):
            continue
        pod_ref = str(item.get("pod_ref") or "unknown")
        log_type = str(item.get("log_type") or "unknown")
        category = str(item.get("category") or "log")
        message = str(item.get("message") or "")
        key = (pod_ref, log_type, category, log_highlight_signature(message))
        if key in seen:
            continue
        seen.add(key)
        evidence.append(
            {
                "source": "signal_bundle.log_highlights",
                "detail": "log-highlight[%s] pod/%s %s: %s" % (log_type, pod_ref, category, message[:700]),
            }
        )
        if len(evidence) >= limit:
            break
    return evidence
