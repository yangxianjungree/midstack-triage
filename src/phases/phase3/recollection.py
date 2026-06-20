"""Phase 3 directed recollection helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.workspace import load_yaml
from .report_gaps import record_recollection_skill_pool_miss

SCRIPT_LOG_SINK_DISCOVER = "mongodb.collect.logs.discover_sink"
SCRIPT_LOG_FILE_TAIL = "mongodb.collect.logs.file_tail"
SCRIPT_LOG_NODE_FILE_TAIL = "mongodb.collect.logs.node_file_tail"
SCRIPT_DNS_COREDNS = "mongodb.collect.dns.coredns"
SCRIPT_NETWORK_OVERLAY = "mongodb.collect.network.overlay"
SCRIPT_PODS_DESCRIBE = "mongodb.collect.pods.describe"
DIRECTED_RECOLLECTION_CAP = 3


def signal_bundle_has(signal_bundle: Dict[str, Any], signal_id: str) -> bool:
    for item in signal_bundle.get("abnormal_signals") or []:
        if isinstance(item, dict) and str(item.get("signal_id") or "") == signal_id:
            return True
    return False


def has_log_sink_record(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    return bool(details.get("log_sinks"))


def has_file_backed_log_sink(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("log_sinks") or []:
        if not isinstance(item, dict):
            continue
        if item.get("path") and not bool(item.get("is_stdout_link")):
            return True
    return False


def details_has_items(structured_record: Dict[str, Any], key: str) -> bool:
    details = structured_record.get("details") or {}
    value = details.get(key)
    return bool(value)


def has_file_tail_logs(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if isinstance(item, dict) and str(item.get("log_type") or "") == "file_tail":
            return True
    processed = details.get("processed_logs") or {}
    return bool(isinstance(processed, dict) and processed.get("file_tail_highlights"))


def text_has_direct_error_terms(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("fatal", "wiredtiger", "corrupt", "journal", "bad magic number", "assertion", "unclean shutdown"))


def signal_bundle_text(signal_bundle: Dict[str, Any]) -> str:
    return json.dumps(signal_bundle, ensure_ascii=False).lower()


def incident_evidence_text(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "structured_record": structured_record,
            "signal_bundle": signal_bundle,
            "collection_report": collection_report,
        },
        ensure_ascii=False,
    ).lower()


def signal_object_pods(signal_bundle: Dict[str, Any], signal_ids: List[str]) -> List[str]:
    wanted = set(signal_ids)
    pods: List[str] = []
    for item in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("signal_id") or "") not in wanted:
            continue
        object_ref = str(item.get("object_ref") or "")
        if object_ref.startswith("pod/"):
            pod = object_ref.split("/", 1)[1]
            if pod and pod not in pods:
                pods.append(pod)
    return pods


def current_logs_are_short(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("log_type") or "") != "current":
            continue
        line_count = int(item.get("line_count") or 0)
        byte_size = int(item.get("byte_size") or 0)
        if line_count <= 5 or byte_size <= 512:
            return True
    return False


def crashloop_logs_are_shallow(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    crashloop_pods = set(signal_object_pods(signal_bundle, ["pod-crashloop"]))
    if not crashloop_pods:
        return False
    highlights_text = signal_bundle_text(signal_bundle)
    if text_has_direct_error_terms(highlights_text):
        return False
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("log_type") or "") not in ("current", "previous"):
            continue
        if str(item.get("pod_ref") or "") not in crashloop_pods:
            continue
        line_count = int(item.get("line_count") or 0)
        byte_size = int(item.get("byte_size") or 0)
        if line_count <= 25 or byte_size <= 4096:
            return True
    return False


def collection_report_mentions_log_sink_gap(collection_report: Dict[str, Any]) -> bool:
    text = json.dumps(collection_report.get("evidence_gaps") or [], ensure_ascii=False).lower()
    return (
        "log sink" in text
        or "logs too short" in text
        or "real log" in text
        or "true log" in text
        or "file log" in text
        or "application log source" in text
    )


def evidence_mentions_dns_issue(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    text = incident_evidence_text(structured_record, signal_bundle, collection_report)
    return any(
        token in text
        for token in (
            "cannot resolve host",
            "lookup ",
            "10.96.0.10:53",
            "kube-dns",
            "coredns",
            "dns",
            "no servers could be reached",
        )
    ) and any(token in text for token in ("timed out", "timeout", "connection refused", "temporary failure", "i/o timeout"))


def should_run_log_sink_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if has_log_sink_record(structured_record):
        return False
    if collection_report_mentions_log_sink_gap(collection_report):
        return True
    if signal_bundle_has(signal_bundle, "pod-crashloop") and current_logs_are_short(structured_record):
        return True
    return crashloop_logs_are_shallow(structured_record, signal_bundle)


def should_run_log_file_tail_recollection(structured_record: Dict[str, Any], selected: List[str]) -> bool:
    if SCRIPT_LOG_SINK_DISCOVER in selected:
        return True
    if has_file_backed_log_sink(structured_record) and not has_file_tail_logs(structured_record):
        return True
    return False


def should_run_log_node_file_tail_recollection(structured_record: Dict[str, Any], selected: List[str]) -> bool:
    if has_file_tail_logs(structured_record):
        return False
    if SCRIPT_LOG_SINK_DISCOVER in selected or SCRIPT_LOG_FILE_TAIL in selected:
        return True
    if has_file_backed_log_sink(structured_record):
        return True
    return False


def should_run_dns_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "dns_checks"):
        return False
    return evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report)


def should_run_network_overlay_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "network_overlay"):
        return False
    return evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report) or signal_bundle_has(signal_bundle, "dns-resolution-failed")


def should_run_pod_describe_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "pod_describes"):
        return False
    if details_has_items(structured_record, "pod_terminations"):
        return False
    return bool(signal_object_pods(signal_bundle, ["pod-crashloop", "pod-not-ready"]))


def select_directed_recollection_script_ids(
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
) -> List[str]:
    selected: List[str] = []

    dns_path = evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report) or signal_bundle_has(signal_bundle, "dns-resolution-failed")
    if dns_path and should_run_dns_recollection(structured_record, signal_bundle, collection_report):
        selected.append(SCRIPT_DNS_COREDNS)
    if dns_path and should_run_network_overlay_recollection(structured_record, signal_bundle, collection_report):
        selected.append(SCRIPT_NETWORK_OVERLAY)
    if dns_path and signal_bundle_has(signal_bundle, "pod-crashloop") and not has_file_tail_logs(structured_record):
        selected.append(SCRIPT_LOG_NODE_FILE_TAIL)
    if not dns_path:
        if should_run_log_sink_recollection(structured_record, signal_bundle, collection_report):
            selected.append(SCRIPT_LOG_SINK_DISCOVER)
        if should_run_log_file_tail_recollection(structured_record, selected):
            selected.append(SCRIPT_LOG_FILE_TAIL)
        if should_run_log_node_file_tail_recollection(structured_record, selected):
            selected.append(SCRIPT_LOG_NODE_FILE_TAIL)
    if should_run_pod_describe_recollection(structured_record, signal_bundle):
        selected.append(SCRIPT_PODS_DESCRIBE)
    return selected[:DIRECTED_RECOLLECTION_CAP]


def filter_recollection_scripts_by_skill_pool(selected: List[str], skill_pool: Optional[set[str]]) -> tuple[List[str], bool]:
    if not skill_pool:
        return selected, False
    filtered = [script_id for script_id in selected if script_id in skill_pool]
    if filtered:
        return filtered, False
    return selected, bool(selected)


def directed_recollection_script_ids(output_dir: Path, skill_pool: Optional[set[str]] = None) -> List[str]:
    structured_record = load_yaml(output_dir / "structured_record.yaml")
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml")
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    selected = select_directed_recollection_script_ids(structured_record, signal_bundle, collection_report)
    selected.extend(auto_allowed_verification_script_ids(output_dir))
    selected = dedupe_script_ids(selected)
    filtered, skill_pool_miss = filter_recollection_scripts_by_skill_pool(selected, skill_pool)
    if skill_pool_miss:
        record_recollection_skill_pool_miss(output_dir)
    return filtered


def auto_allowed_verification_script_ids(output_dir: Path) -> List[str]:
    analysis_file = output_dir / "analysis.yaml"
    if not analysis_file.exists():
        return []
    analysis = load_yaml(analysis_file)
    selected: List[str] = []
    for item in analysis.get("verification_requests") or []:
        if not isinstance(item, dict):
            continue
        asset = item.get("asset") or {}
        if (
            item.get("asset_tier") == "first_class"
            and item.get("execution_policy") == "auto_allowed"
            and item.get("risk_level") == "read-only"
            and asset.get("type") == "script"
            and asset.get("id")
        ):
            selected.append(str(asset["id"]))
    return selected


def dedupe_script_ids(script_ids: List[str]) -> List[str]:
    selected: List[str] = []
    seen = set()
    for script_id in script_ids:
        if script_id in seen:
            continue
        seen.add(script_id)
        selected.append(script_id)
    return selected
