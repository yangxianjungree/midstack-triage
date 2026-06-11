#!/usr/bin/env python3

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set


DETAILS_LIST_MERGE_BY_KEY: Dict[str, str] = {
    "pods": "name",
    "statefulsets": "name",
    "services": "name",
    "nodes": "name",
    "replica_members": "source_pod_ref",
    "components": "component_id",
    "log_sinks": "source_pod_ref",
    "pod_terminations": "pod_container_ref",
    "pod_describes": "pod_ref",
    "dns_checks": "check_id",
    "coredns_pods": "name",
    "dns_services": "name",
}

DETAILS_LIST_APPEND: Set[str] = {
    "raw_logs",
    "processed_logs",
}

SIGNAL_BUNDLE_LIST_APPEND: Set[str] = {
    "abnormal_signals",
    "object_signal_links",
    "timeline_summary",
    "processed_log_highlights",
    "log_highlights",
}

COLLECTION_REPORT_LIST_APPEND: Set[str] = {
    "collection_actions",
    "successful_items",
    "failed_items",
    "blank_items",
    "evidence_gaps",
}


def merge_dict(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def merge_list_by_key(existing: List[Any], incoming: List[Any], key_field: str) -> List[Any]:
    index = {}
    merged: List[Any] = []
    for item in existing:
        if isinstance(item, dict) and item.get(key_field) is not None:
            index[str(item[key_field])] = len(merged)
            merged.append(deepcopy(item))
        else:
            merged.append(deepcopy(item))
    for item in incoming:
        if not isinstance(item, dict) or item.get(key_field) is None:
            merged.append(deepcopy(item))
            continue
        item_key = str(item[key_field])
        if item_key in index:
            pos = index[item_key]
            if isinstance(merged[pos], dict):
                merge_dict(merged[pos], item)
            else:
                merged[pos] = deepcopy(item)
        else:
            index[item_key] = len(merged)
            merged.append(deepcopy(item))
    return merged


def append_list(existing: List[Any], incoming: List[Any]) -> List[Any]:
    merged = list(existing)
    merged.extend(deepcopy(incoming))
    return merged


def merge_details_patch(target_details: Dict[str, Any], patch_details: Dict[str, Any]) -> None:
    for key, value in patch_details.items():
        if key in DETAILS_LIST_MERGE_BY_KEY and isinstance(value, list):
            key_field = DETAILS_LIST_MERGE_BY_KEY[key]
            current = target_details.get(key)
            if not isinstance(current, list):
                current = []
            target_details[key] = merge_list_by_key(current, value, key_field)
        elif key in DETAILS_LIST_APPEND and isinstance(value, list):
            current = target_details.get(key)
            if not isinstance(current, list):
                current = []
            target_details[key] = append_list(current, value)
        elif isinstance(value, dict) and isinstance(target_details.get(key), dict):
            merge_dict(target_details[key], value)
        else:
            target_details[key] = deepcopy(value)


def merge_structured_record_patch(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    if not patch:
        return
    if "summary" in patch and isinstance(patch["summary"], dict):
        summary = target.setdefault("summary", {})
        if isinstance(summary, dict):
            merge_dict(summary, patch["summary"])
    if "details" in patch and isinstance(patch["details"], dict):
        details = target.setdefault("details", {})
        if isinstance(details, dict):
            merge_details_patch(details, patch["details"])
    for key, value in patch.items():
        if key in ("summary", "details"):
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dict(target[key], value)
        else:
            target[key] = deepcopy(value)


def merge_signal_bundle_patch(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    if not patch:
        return
    for key, value in patch.items():
        if key in SIGNAL_BUNDLE_LIST_APPEND and isinstance(value, list):
            current = target.get(key)
            if not isinstance(current, list):
                current = []
            target[key] = append_list(current, value)
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dict(target[key], value)
        else:
            target[key] = deepcopy(value)


def append_collection_report_patch(target: Dict[str, Any], patch: Dict[str, Any]) -> None:
    if not patch:
        return
    for key, value in patch.items():
        if key in COLLECTION_REPORT_LIST_APPEND and isinstance(value, list):
            current = target.setdefault(key, [])
            if isinstance(current, list):
                current.extend(deepcopy(value))
            else:
                target[key] = deepcopy(value)
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dict(target[key], value)
        else:
            target[key] = deepcopy(value)


def apply_script_output(
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
    script_output: Dict[str, Any],
) -> None:
    patch = script_output.get("structured_record_patch")
    if isinstance(patch, dict):
        merge_structured_record_patch(structured_record, patch)
    patch = script_output.get("signal_bundle_patch")
    if isinstance(patch, dict):
        merge_signal_bundle_patch(signal_bundle, patch)
    patch = script_output.get("collection_report_patch")
    if isinstance(patch, dict):
        append_collection_report_patch(collection_report, patch)
