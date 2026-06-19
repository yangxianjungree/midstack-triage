#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

try:
    from phases.phase4.analysis_contract import analysis_contract_fields
    from phases.phase4.verification_requests import dedupe_verification_requests, first_class_script_request
    from shared.asset_resolver import knowledge_candidates_for_scenario as shared_knowledge_candidates_for_scenario
    from .common import load_yaml, runtime_root, write_yaml
    from .mongodb_log_evidence import evidence_from_log_highlights
except ImportError:  # pragma: no cover - supports direct file execution
    RULES_DIR = Path(__file__).resolve().parent
    if str(RULES_DIR) not in sys.path:
        sys.path.insert(0, str(RULES_DIR))
    SRC_DIR = RULES_DIR.parents[2]
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))
    from phases.phase4.analysis_contract import analysis_contract_fields
    from phases.phase4.verification_requests import dedupe_verification_requests, first_class_script_request
    from shared.asset_resolver import knowledge_candidates_for_scenario as shared_knowledge_candidates_for_scenario
    from common import load_yaml, runtime_root, write_yaml
    from mongodb_log_evidence import evidence_from_log_highlights


ROOT = runtime_root()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a minimal MongoDB analysis.yaml from a fixture or incident directory.")
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output-file", help="If omitted, write JSON to stdout.")
    return parser.parse_args()


def signal_ids(signal_bundle: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for item in signal_bundle.get("abnormal_signals") or []:
        if isinstance(item, dict) and item.get("signal_id"):
            result.append(str(item["signal_id"]))
    return result


def replica_members_from_record(structured_record: Dict[str, Any]) -> List[Dict[str, Any]]:
    details = (structured_record or {}).get("details") or {}
    return [item for item in (details.get("replica_members") or []) if isinstance(item, dict)]


def evidence_from_events(structured_record: Dict[str, Any]) -> List[Dict[str, str]]:
    evidence: List[Dict[str, str]] = []
    for event in ((structured_record or {}).get("details") or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        involved = event.get("involved_object") or {}
        object_ref = str(involved.get("name") or event.get("name") or "unknown")
        reason = str(event.get("reason") or "")
        message = str(event.get("message") or "")
        evidence.append(
            {
                "source": "structured_record.details.events",
                "detail": "%s on %s: %s" % (reason, object_ref, message),
            }
        )
    return evidence


def expand_kubernetes_runtime_ids(ids: Set[str], structured_record: Dict[str, Any], scenario: str) -> Set[str]:
    expanded = set(ids)
    if scenario != "kubernetes-runtime":
        return expanded
    for event in ((structured_record or {}).get("details") or {}).get("events") or []:
        if not isinstance(event, dict):
            continue
        reason = str(event.get("reason") or "")
        message = str(event.get("message") or "").lower()
        if reason == "Evicted" and "ephemeral" in message:
            expanded.add("pod-not-ready")
        elif reason == "Unhealthy":
            expanded.add("pod-not-ready")
        elif reason == "FailedScheduling":
            if "node selector" in message or "affinity" in message:
                expanded.add("pod-node-selector-mismatch")
            elif "volume" in message or "persistentvolumeclaim" in message or "binding" in message:
                expanded.add("pod-volume-binding-failed")
            elif "insufficient" in message:
                expanded.add("pod-resource-insufficient")
            else:
                expanded.add("pod-unschedulable")
        elif reason in ("ErrImagePull", "ImagePullBackOff"):
            expanded.add("pod-image-pull-failed")
        elif reason == "BackOff" and "restart" in message:
            expanded.add("pod-crashloop")
    return expanded


def rs_status_evidence_items(member_records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for record in member_records:
        pod = str(record.get("source_pod_ref") or "")
        replica_set_id = str(record.get("replica_set_id") or "")
        self_member = record.get("self_member") or {}
        items.append(
            {
                "source": "structured_record.replica_members",
                "detail": "rs.status from pod/%s replica_set=%s reports self_state=%s health=%s"
                % (pod, replica_set_id, self_member.get("state_str"), self_member.get("health")),
            }
        )
    return items


def replica_members_unhealthy(member_records: List[Dict[str, Any]]) -> bool:
    bad_states = {"DOWN", "REMOVED", "ROLLBACK", "UNKNOWN", "STARTUP2"}
    for record in member_records:
        self_member = record.get("self_member") or {}
        if self_member.get("health") == 0:
            return True
        state = str(self_member.get("state_str") or "")
        if state in bad_states or state.startswith("("):
            return True
    return False


def gaps_without_closed_rs_status(gaps: List[Dict[str, Any]], member_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not member_records:
        return gaps
    kept: List[Dict[str, Any]] = []
    for gap in gaps:
        if not isinstance(gap, dict):
            kept.append(gap)
            continue
        text = str(gap.get("gap") or "").lower()
        if "rs.status" in text and any(token in text for token in ("not collected", "missing", "blocked", "script output")):
            continue
        kept.append(gap)
    return kept


def has_ephemeral_eviction_evidence(evidence: List[Dict[str, str]]) -> bool:
    for item in evidence:
        detail = str(item.get("detail") or "")
        if "Evicted" in detail and "ephemeral" in detail.lower():
            return True
    return False


def evidence_from_signals(signal_bundle: Dict[str, Any]) -> List[Dict[str, str]]:
    evidence: List[Dict[str, str]] = []
    for item in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(item, dict):
            continue
        evidence.append(
            {
                "source": "signal_bundle",
                "detail": "%s: %s" % (item.get("signal_id"), item.get("detail")),
            }
        )
    evidence.extend(evidence_from_log_highlights(signal_bundle))
    return evidence


def classify_gap_type(gap_text: str, item: Dict[str, Any]) -> str:
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
    if "rs.status" in text and any(token in text for token in ("no healthy", "all", "not collected", "missing")):
        return "critical_gap"
    if any(token in text for token in ("affected pod", "faulty pod", "bad pod", "current pod")) and ("rs.status" in text or "fatal tail" in text):
        return "expected_gap"
    return "expected_gap"


def normalize_gap(item: Any) -> Dict[str, Any]:
    if isinstance(item, str):
        gap_text = item
        raw: Dict[str, Any] = {}
    elif isinstance(item, dict):
        raw = dict(item)
        gap_text = str(raw.get("gap") or raw)
    else:
        raw = {}
        gap_text = str(item)
    normalized = {
        "gap": gap_text,
        "gap_type": classify_gap_type(gap_text, raw),
        "related_stage": str(raw.get("related_stage") or "signal_collection"),
        "why_important": str(raw.get("why_important") or "This gap affects evidence completeness."),
    }
    if raw.get("affects"):
        normalized["affects"] = raw.get("affects")
    if raw.get("recommended_action"):
        normalized["recommended_action"] = raw.get("recommended_action")
    return normalized


def collection_gaps(collection_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    gaps: List[Dict[str, Any]] = []
    for item in collection_report.get("evidence_gaps") or []:
        gaps.append(normalize_gap(item))
    return gaps


def verification_requests_for_gaps(
    scenario: str,
    ids: Set[str],
    gaps: List[Dict[str, Any]],
    member_records: List[Dict[str, Any]],
    hypotheses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if scenario in ("baseline",):
        return []

    requests: List[Dict[str, Any]] = []
    gap_text = "\n".join(str(item.get("gap") or "") for item in gaps if isinstance(item, dict)).lower()
    has_runtime_signal = bool(ids & {"pod-crashloop", "pod-not-ready", "pod-resource-pressure", "node-resource-pressure"})
    primary_hypothesis_id = str((hypotheses[0] if hypotheses else {}).get("hypothesis_id") or "H1")
    replica_hypothesis_id = primary_hypothesis_id
    for item in hypotheses:
        if "internal replica set state" in str(item.get("statement") or ""):
            replica_hypothesis_id = str(item.get("hypothesis_id") or primary_hypothesis_id)
            break

    if "rs.status" in gap_text and not member_records:
        requests.append(
            first_class_script_request(
                "vr-mongodb-rs-status",
                replica_hypothesis_id,
                "verify MongoDB replica set member state",
                "mongodb.collect.replicaset.rs_status",
                ["structured_record.details.replica_members"],
                "rs.status evidence is missing, so replica-set internal state remains insufficient.",
            )
        )

    if has_runtime_signal and any(token in gap_text for token in ("logs too short", "previous logs", "fatal startup logs")):
        requests.append(
            first_class_script_request(
                "vr-mongodb-previous-logs",
                primary_hypothesis_id,
                "collect previous MongoDB pod logs around restart",
                "mongodb.collect.logs.previous",
                ["signal_bundle.log_highlights", "structured_record.details.processed_logs"],
                "Crash or readiness evidence needs process log context before deepening the conclusion.",
            )
        )

    if has_runtime_signal and any(token in gap_text for token in ("pod status", "pod conditions", "pods state")):
        requests.append(
            first_class_script_request(
                "vr-mongodb-pods-state",
                primary_hypothesis_id,
                "verify Kubernetes pod state and conditions",
                "mongodb.collect.pods.state",
                ["structured_record.details.pods"],
                "Pod state evidence is needed to validate the Kubernetes runtime hypothesis.",
            )
        )

    return dedupe_verification_requests(requests)


def hypothesis(hid: str, statement: str, evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]], status: str) -> Dict[str, Any]:
    return {
        "hypothesis_id": hid,
        "statement": statement,
        "causal_path": [],
        "supporting_evidence": evidence,
        "counter_evidence": [],
        "disconfirming_conditions": [],
        "evidence_gaps": gaps,
        "validation_actions": [],
        "validation_result": status,
        "status": status,
    }


def hypothesis_with_actions(
    hid: str,
    statement: str,
    evidence: List[Dict[str, str]],
    gaps: List[Dict[str, Any]],
    status: str,
    actions: List[Dict[str, Any]],
    causal_path: List[str],
    disconfirming_conditions: List[str],
) -> Dict[str, Any]:
    item = hypothesis(hid, statement, evidence, gaps, status)
    item["validation_actions"] = actions
    item["causal_path"] = causal_path
    item["disconfirming_conditions"] = disconfirming_conditions
    return item


def knowledge_candidates_for_scenario(scenario: str, primary_cause_category: str = "") -> List[Dict[str, str]]:
    runtime_categories = {
        "kubernetes-scheduling",
        "kubernetes-storage-binding",
        "kubernetes-resource-scheduling",
        "kubernetes-resource-pressure",
        "kubernetes-image-pull",
        "container-restart",
        "kubernetes-runtime",
    }
    if scenario in ("", "unknown") and primary_cause_category in runtime_categories:
        scenario = "kubernetes-runtime"
    if scenario in ("", "unknown") and primary_cause_category == "dns-startup-failure":
        scenario = "kubernetes-runtime"
    if scenario in ("", "unknown", "baseline"):
        return []

    return shared_knowledge_candidates_for_scenario("mongodb", scenario, ROOT)


def has_critical_gap(gaps: List[Dict[str, Any]]) -> bool:
    return any(str(item.get("gap_type") or "") == "critical_gap" for item in gaps if isinstance(item, dict))


def direct_mongodb_error_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = "\n".join(str(item.get("detail") or "") for item in evidence).lower()
    return any(token in text for token in ("fatal", "wiredtiger", "corrupt", "journal", "bad magic number", "assertion", "unclean shutdown"))


def evidence_text(evidence: List[Dict[str, str]]) -> str:
    return "\n".join(str(item.get("detail") or "") for item in evidence).lower()


def mongodb_storage_corruption_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = evidence_text(evidence)
    return (
        ("wiredtiger" in text and any(token in text for token in ("corrupt", "checksum", "bad magic", "wt_panic", "try_salvage")))
        or ("journal" in text and "corrupt" in text)
        or ("metadata corruption" in text)
        or ("wiredtiger" in text and "fatal read error" in text)
        or ("wt_error" in text and "fatal read error" in text)
    )


def storage_evidence_items(evidence: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    for item in evidence:
        detail = str(item.get("detail") or "").lower()
        if any(token in detail for token in ("wiredtiger", "journal", "corrupt", "checksum", "bad magic", "wt_panic", "try_salvage", "fatal read error", "wt_error")):
            result.append(item)
    return result or evidence


def has_peer_connection_log_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = evidence_text(evidence)
    return ("hostunreachable" in text or "host failed in replica set" in text or "rsm received error response" in text) and "connection refused" in text


def has_dns_startup_log_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = evidence_text(evidence)
    return "cannot resolve host" in text and any(token in text for token in ("10.96.0.10:53", "i/o timeout", "connection refused", "temporary failure"))


def has_overlay_root_evidence(ids: Set[str]) -> bool:
    return "flannel-vxlan-down" in ids and (
        "flannel-route-install-failed" in ids
        or "pod-subnet-isolated" in ids
        or "kube-dns-backend-on-overlay-partition" in ids
    )


def direct_root_cause_evidence(evidence: List[Dict[str, str]], ids: Set[str]) -> bool:
    return mongodb_storage_corruption_evidence(evidence) or has_overlay_root_evidence(ids)


def apply_conclusion_ceiling(conclusion: Dict[str, Any], evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]], ids: set) -> Dict[str, Any]:
    result = dict(conclusion)
    category = str(result.get("primary_cause_category") or "")
    if not result.get("deepest_supported_level"):
        if category.startswith("kubernetes-") or category in ("container-restart", "service-routing"):
            result["deepest_supported_level"] = "impact"
        elif direct_mongodb_error_evidence(evidence):
            result["deepest_supported_level"] = "root_cause"
        elif category in ("replication",):
            result["deepest_supported_level"] = "mechanism"
        else:
            result["deepest_supported_level"] = "phenomenon"

    level = str(result.get("deepest_supported_level") or "")
    confidence = str(result.get("confidence") or "low")
    limitations = list(result.get("limitations") or [])
    if has_critical_gap(gaps) and not direct_root_cause_evidence(evidence, set(ids)):
        limitations.append(
            {
                "gap": "unresolved critical_gap limits deeper conclusion",
                "gap_type": "critical_gap",
                "related_stage": "reasoning",
                "why_important": "Root-cause confidence must stay capped until critical evidence gaps are closed.",
            }
        )
        if level == "root_cause" and confidence == "high":
            result["confidence"] = "medium"
    if "pod-crashloop" in ids and not direct_mongodb_error_evidence(evidence) and not has_overlay_root_evidence(set(ids)) and level == "root_cause":
        result["deepest_supported_level"] = "impact"
        if confidence == "high":
            result["confidence"] = "medium"
        limitations.append(
            {
                "gap": "MongoDB process-internal fatal evidence is not present",
                "gap_type": "critical_gap",
                "related_stage": "reasoning",
                "why_important": "CrashLoopBackOff supports process failure, but not the internal MongoDB root cause.",
                "recommended_action": "discover application log sink and collect MongoDB file logs if kubectl logs is too short",
            }
        )
    result["limitations"] = limitations
    return result


def mongodb_storage_corruption_conclusion(ids: Set[str], evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not mongodb_storage_corruption_evidence(evidence):
        return {}
    root_evidence = storage_evidence_items(evidence)
    hypotheses = [
        hypothesis_with_actions(
            "H1",
            "MongoDB startup fails because WiredTiger storage or journal corruption is reported by MongoDB file logs.",
            root_evidence,
            gaps,
            "supported",
            [
                {
                    "action": "Discover the MongoDB log sink and collect file-backed logs from the crashing Pod or its node-side volume.",
                    "result": "Supported by MongoDB file-tail evidence containing WiredTiger corruption terms.",
                    "risk_level": "read-only",
                },
                {
                    "action": "Correlate the corrupted file name with the affected Pod/PVC before any remediation.",
                    "result": "Recommended as a safety check before repair or restore actions.",
                    "risk_level": "read-only",
                },
            ],
            [
                "Kubernetes reports the MongoDB member as restarting or unavailable",
                "kubectl logs may be shallow because MongoDB writes application logs to a file sink",
                "MongoDB file logs contain WiredTiger/journal corruption or WT_PANIC evidence",
                "mongod exits during startup after the storage engine reports the fatal error",
            ],
            [
                "MongoDB file logs show a non-storage fatal error for the same restart window",
                "The affected Pod becomes stable without changing storage or journal files",
            ],
        ),
        hypothesis_with_actions(
            "H2",
            "Kubernetes scheduling, image pull, or probe configuration caused the restart symptom.",
            evidence,
            gaps,
            "refuted" if "pod-crashloop" in ids else "insufficient",
            [
                {
                    "action": "Inspect Pod status, previous logs, and termination details.",
                    "result": "Refuted as primary root cause when MongoDB file logs contain direct WiredTiger fatal evidence.",
                    "risk_level": "read-only",
                }
            ],
            [],
            ["No MongoDB file-log fatal storage evidence is present"],
        ),
    ]
    return {
        "hypotheses": hypotheses,
        "conclusion": {
            "statement": "MongoDB fails to start because WiredTiger storage or journal corruption is reported in MongoDB file logs.",
            "confidence": "high",
            "impact_scope": "Affected MongoDB member cannot start; its replica set or shard may run with reduced redundancy.",
            "primary_cause_category": "mongodb-storage-corruption",
            "evidence": [item["detail"] for item in root_evidence],
            "limitations": gaps,
            "deepest_supported_level": "root_cause",
        },
        "next_actions": [
            {
                "action": "Preserve the affected PVC and file logs before attempting repair, restore, or pod recreation.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            },
            {
                "action": "Use MongoDB/vendor recovery guidance to decide between restore, resync, or salvage; do not mutate data files during triage.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            },
        ],
    }


def network_overlay_conclusion(ids: Set[str], evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not has_overlay_root_evidence(ids):
        return {}
    overlay_evidence = [
        item
        for item in evidence
        if any(
            token in str(item.get("detail") or "").lower()
            for token in ("flannel", "vxlan", "overlay", "pod-subnet", "kube-dns endpoint")
        )
    ] or evidence
    hypotheses = [
        hypothesis_with_actions(
            "H1",
            "DNS timeouts are caused by a node-level flannel overlay partition rather than CoreDNS process failure.",
            overlay_evidence,
            gaps,
            "supported",
            [
                {
                    "action": "Inspect kube-dns endpoints and identify whether a backend is located on the node with unhealthy flannel.1.",
                    "result": "Supported when kube-dns has an endpoint on the overlay-partitioned node.",
                    "risk_level": "read-only",
                },
                {
                    "action": "Compare flannel.1 state, PodCIDR routes, FDB entries, and flannel logs across nodes.",
                    "result": "Supported when the affected node has flannel.1 down or route install failures.",
                    "risk_level": "read-only",
                },
            ],
            [
                "Workload logs report DNS lookup timeouts through kube-dns Service",
                "kube-dns has at least one backend on the affected node",
                "The affected node has flannel.1 not UP or flannel route installation failures",
                "Pod network reachability to that node's PodCIDR is impaired",
            ],
            [
                "flannel.1 is UP on all nodes with complete PodCIDR routes and FDB entries",
                "All kube-dns endpoints are reachable from multiple source Pods",
                "CoreDNS logs show an internal DNS server failure independent of node networking",
            ],
        )
    ]
    if mongodb_storage_corruption_evidence(evidence):
        hypotheses.append(
            hypothesis_with_actions(
                "H2",
                "A separate MongoDB storage corruption line is also present for at least one member.",
                storage_evidence_items(evidence),
                gaps,
                "supported",
                [
                    {
                        "action": "Keep storage corruption evidence separate from the DNS/overlay failure line.",
                        "result": "Supported by WiredTiger corruption or WT_PANIC log evidence.",
                        "risk_level": "read-only",
                    }
                ],
                [
                    "A MongoDB member reports WiredTiger corruption or WT_PANIC",
                    "This fatal storage signal is process-internal and not explained by DNS timeout alone",
                ],
                ["The same Pod has no WiredTiger or storage fatal evidence in the failure window"],
            )
        )
    else:
        hypotheses.append(
            hypothesis_with_actions(
                "H2",
                "CoreDNS itself is the primary failed component.",
                evidence,
                gaps,
                "refuted" if "kube-dns-backend-on-overlay-partition" in ids else "insufficient",
                [
                    {
                        "action": "Check CoreDNS pod readiness, logs, and endpoint distribution.",
                        "result": "CoreDNS process failure is not the primary explanation when the failing backend sits on an overlay-partitioned node.",
                        "risk_level": "read-only",
                    }
                ],
                [],
                ["CoreDNS pods crash or all endpoints fail regardless of node placement"],
            )
        )
    return {
        "hypotheses": hypotheses,
        "conclusion": {
            "statement": "Kubernetes DNS timeouts are caused by a flannel overlay partition: a node's flannel.1 is not UP and kube-dns has a backend on that node.",
            "confidence": "high",
            "impact_scope": "Pods on or targeting the affected node's PodCIDR can lose cross-node connectivity; Services with backends on that node may fail randomly or completely.",
            "primary_cause_category": "kubernetes-overlay-network-partition",
            "evidence": [item["detail"] for item in overlay_evidence],
            "limitations": gaps,
            "deepest_supported_level": "root_cause",
        },
        "next_actions": [
            {
                "action": "Confirm affected node flannel.1 state, PodCIDR routes, and flannel logs before remediation.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            },
            {
                "action": "Keep MongoDB storage corruption evidence on a separate fault line if WiredTiger fatal logs are present.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            },
        ],
    }


def kubernetes_runtime_conclusion(
    ids: set,
    evidence: List[Dict[str, str]],
    gaps: List[Dict[str, Any]],
    structured_record: Dict[str, Any] = None,
) -> Dict[str, Any]:
    rules = [
        (
            "pod-node-selector-mismatch",
            "kubernetes-scheduling",
            "high",
            "Kubernetes scheduling failure: a MongoDB member Pod is Pending because node selector or affinity does not match available nodes.",
            "MongoDB shard member Pod cannot be scheduled because its node selector or affinity does not match available Kubernetes nodes.",
        ),
        (
            "pod-volume-binding-failed",
            "kubernetes-storage-binding",
            "high",
            "Kubernetes storage binding failure: a MongoDB member Pod is Pending because PVC or volume binding failed.",
            "MongoDB member Pod cannot be scheduled because required storage is not bound or attachable.",
        ),
        (
            "pod-resource-insufficient",
            "kubernetes-resource-scheduling",
            "high",
            "Kubernetes resource scheduling failure: a MongoDB member Pod is Pending because available nodes do not satisfy requested resources.",
            "MongoDB member Pod cannot be scheduled because CPU, memory or ephemeral-storage requests cannot be satisfied.",
        ),
        (
            "node-resource-pressure",
            "kubernetes-resource-pressure",
            "medium",
            "Kubernetes resource pressure observed: a node running MongoDB workload reports high CPU or memory usage.",
            "MongoDB availability or latency may be affected by sustained resource pressure on the Kubernetes node.",
        ),
        (
            "pod-resource-pressure",
            "kubernetes-resource-pressure",
            "medium",
            "Kubernetes resource pressure observed: a MongoDB Pod reports high CPU or memory usage.",
            "MongoDB availability or latency may be affected by sustained resource pressure in the MongoDB Pod.",
        ),
        (
            "pod-image-pull-failed",
            "kubernetes-image-pull",
            "high",
            "Kubernetes image pull failure: a MongoDB member Pod cannot start because its container image cannot be pulled.",
            "MongoDB member Pod cannot start because image pulling failed.",
        ),
        (
            "pod-crashloop",
            "container-restart",
            "high",
            "MongoDB container restart loop: a member Pod is repeatedly restarting.",
            "MongoDB member Pod is unavailable because its container is repeatedly restarting.",
        ),
        (
            "pod-unschedulable",
            "kubernetes-scheduling",
            "medium",
            "Kubernetes scheduling failure: a MongoDB member Pod is Pending and unschedulable.",
            "MongoDB member Pod is unavailable because Kubernetes cannot schedule it.",
        ),
        (
            "pod-not-ready",
            "kubernetes-runtime",
            "medium",
            "Kubernetes runtime availability issue: a MongoDB member Pod is not ready.",
            "MongoDB member Pod is unavailable because Kubernetes reports it not ready.",
        ),
    ]
    member_records = replica_members_from_record(structured_record or {})
    runtime_gaps = gaps_without_closed_rs_status(gaps, member_records)
    for signal_id, category, confidence, conclusion_statement, hypothesis_statement in rules:
        if signal_id not in ids:
            continue
        peer_log_supported = has_peer_connection_log_evidence(evidence)
        dns_probe_supported = "dns-resolution-failed" in ids
        dns_log_seen = has_dns_startup_log_evidence(evidence)
        if signal_id == "pod-not-ready" and has_ephemeral_eviction_evidence(evidence):
            hypothesis_statement = (
                "Shard MongoDB data Pods were evicted because ephemeral local storage exceeded the container limit, "
                "causing readiness probe failures and forced restarts."
            )
            conclusion_statement = (
                "MongoDB member Pods were evicted after exceeding ephemeral local storage limits; "
                "Kubernetes recovery is the supported explanation."
            )
            category = "kubernetes-runtime"
            confidence = "high"
        hypotheses = [
            hypothesis_with_actions(
                "H1",
                hypothesis_statement,
                evidence,
                runtime_gaps,
                "supported",
                [
                    {
                        "action": "Inspect Kubernetes Pod status, conditions and related workload controller status.",
                        "result": "Supported by %s signal." % signal_id,
                        "risk_level": "read-only",
                    },
                    {
                        "action": "Compare affected MongoDB component readiness with StatefulSet desired and ready replicas.",
                        "result": "Supported when statefulset-replicas-not-ready or pod-level unavailability is present.",
                        "risk_level": "read-only",
                    },
                ],
                [
                    "Kubernetes reports a Pod-level runtime or scheduling abnormality",
                    "The affected Pod belongs to a MongoDB component",
                    "MongoDB component availability is reduced or cannot be fully verified",
                ],
                [
                    "Affected Pod is Running and Ready",
                    "Workload controller has desired ready replicas",
                    "Pod condition does not support the inferred Kubernetes runtime category",
                ],
            ),
        ]
        if peer_log_supported:
            hypotheses.append(
                hypothesis_with_actions(
                    "H2",
                    "MongoDB peers observe the affected member as unreachable with connection refused.",
                    [item for item in evidence if "HostUnreachable" in item.get("detail", "") or "connection refused" in item.get("detail", "")],
                    gaps,
                    "supported",
                    [
                        {
                            "action": "Correlate peer HostUnreachable timestamps with the affected Pod restart timestamps.",
                            "result": "Supported by MongoDB file-log RSM/HostUnreachable evidence.",
                            "risk_level": "read-only",
                        },
                        {
                            "action": "Collect rs.status from a healthy member to confirm replica-set member state.",
                            "result": "Still required for replica-set state details when mongosh is available.",
                            "risk_level": "read-only",
                        },
                    ],
                    [
                        "MongoDB file logs were discovered and collected from the mounted log sink",
                        "ReplicaSetMonitor reports the member host as HostUnreachable",
                        "The reported failure is connection refused to the member Pod IP and MongoDB port",
                    ],
                    [
                        "Peer logs show successful checks for the same member during the incident window",
                        "rs.status from healthy peers reports the member healthy",
                    ],
                )
            )
        if dns_log_seen or dns_probe_supported:
            hypotheses.append(
                hypothesis_with_actions(
                    "H%s" % (len(hypotheses) + 1),
                    "MongoDB startup is blocked by DNS lookup failures for MongoDB service names.",
                    [item for item in evidence if "cannot resolve host" in item.get("detail", "") or "dns-resolution-failed" in item.get("detail", "")],
                    gaps,
                    "supported" if dns_probe_supported else "insufficient",
                    [
                        {
                            "action": "Use CoreDNS pod state and an in-cluster DNS probe to validate current DNS behavior.",
                            "result": "Supported only when DNS probe or CoreDNS evidence confirms the lookup failure.",
                            "risk_level": "read-only",
                        },
                    ],
                    [
                        "MongoDB bootstrap logs contain cannot-resolve-host errors",
                        "The lookup path targets kube-dns/CoreDNS for MongoDB service names",
                        "Startup waits for the MongoDB port but the process does not become ready",
                    ],
                    [
                        "In-cluster lookup succeeds from affected or comparable Pods during the incident window",
                        "CoreDNS pods and kube-dns endpoints are healthy and no DNS probe failure is observed",
                    ],
                )
            )
        rs_evidence = rs_status_evidence_items(member_records)
        if member_records:
            h3_status = "supported" if replica_members_unhealthy(member_records) else "refuted"
            h3_actions = [
                {
                    "action": "Compare rs.status from collected members against Kubernetes Pod and StatefulSet signals.",
                    "result": "Supported when rs.status shows unhealthy or non-voting replica-set members.",
                    "risk_level": "read-only",
                }
            ]
            if h3_status == "refuted":
                h3_actions = [
                    {
                        "action": "Compare rs.status from collected members against Kubernetes recovery signals.",
                        "result": "Refuted when rs.status shows healthy replica-set members after Kubernetes recovery.",
                        "risk_level": "read-only",
                    }
                ]
        else:
            h3_status = "insufficient"
            h3_actions = [
                {
                    "action": "Collect rs.status from all schedulable members and compare member states.",
                    "result": "Evidence is insufficient when rs.status is not available from any healthy member.",
                    "risk_level": "read-only",
                }
            ]
        hypotheses.append(
            hypothesis_with_actions(
                "H%s" % (len(hypotheses) + 1),
                "MongoDB internal replica set state caused the unavailable member symptom.",
                rs_evidence or evidence,
                runtime_gaps,
                h3_status,
                h3_actions,
                [],
                ["All Kubernetes Pod and StatefulSet signals are healthy while rs.status shows an internal member state issue"],
            )
        )
        conclusion_level = "impact"
        if signal_id in ("node-resource-pressure", "pod-resource-pressure"):
            conclusion_level = "phenomenon"
        if dns_probe_supported:
            conclusion_statement = "MongoDB containers are restarting or not ready with supported DNS lookup failure evidence."
            category = "dns-startup-failure"
            confidence = "medium"
            conclusion_level = "mechanism"
        elif peer_log_supported:
            conclusion_statement = "MongoDB containers are restarting or not ready, and peer logs confirm the affected member is refusing connections."
            confidence = "high"
            conclusion_level = "mechanism"
        if signal_id == "pod-node-selector-mismatch":
            alternate = hypotheses[-1]
            alternate["statement"] = "MongoDB shard member is unavailable because of storage binding failure."
            alternate["validation_result"] = "refuted"
            alternate["status"] = "refuted"
            alternate["disconfirming_conditions"] = ["PVC is unbound or scheduler event reports volume binding failure"]
            hypotheses[0]["causal_path"] = [
                "StatefulSet creates MongoDB member Pod",
                "Pod has nodeSelector or affinity constraint",
                "No available node matches the scheduling constraint",
                "Pod remains Pending and the StatefulSet stays below desired replicas",
                "rs.status cannot be collected from the unscheduled member",
            ]
        next_actions_by_category = {
            "kubernetes-scheduling": [
                "Check affected Pod spec.nodeSelector, affinity, tolerations, and scheduler FailedScheduling events.",
                "List node labels and verify whether any node satisfies the Pod scheduling constraints.",
                "Check the owning StatefulSet rollout status and ready/desired replicas.",
            ],
            "kubernetes-storage-binding": [
                "Check PVC phase, bound PV, StorageClass, access mode, and volume binding events.",
                "Inspect FailedScheduling or FailedMount events for the affected Pod.",
                "Verify whether the MongoDB member data volume can be attached to a schedulable node.",
            ],
            "kubernetes-resource-scheduling": [
                "Compare Pod resource requests with node allocatable CPU, memory, and ephemeral storage.",
                "Inspect scheduler FailedScheduling events for Insufficient cpu, memory, or ephemeral-storage.",
                "Check whether existing workload placement or taints reduce usable node capacity.",
            ],
            "kubernetes-resource-pressure": [
                "Confirm resource pressure duration with metrics-server or platform monitoring around the incident window.",
                "Compare affected Pod CPU and memory usage with requests, limits, throttling, and OOM history.",
                "Check whether the affected Node also has disk, memory, PID, or network pressure conditions.",
            ],
            "kubernetes-image-pull": [
                "Inspect container waiting reason, image name, imagePullSecret, and image pull events.",
                "Verify registry reachability and credentials from the Kubernetes node network.",
                "Check whether the image tag exists and is accessible to the cluster runtime.",
            ],
            "container-restart": [
                "Inspect current and previous Pod logs around restart timestamps.",
                "Check container lastState termination reason, exit code, and OOMKilled status.",
                "Compare liveness/readiness probe failures with MongoDB startup logs.",
            ],
            "kubernetes-runtime": [
                "Inspect Pod conditions, readiness probe status, and recent warning events.",
                "Check current and previous logs for the affected MongoDB member.",
                "Verify whether the owning StatefulSet has fewer ready replicas than desired.",
            ],
        }
        next_actions = [
            {
                "action": action,
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
            for action in next_actions_by_category.get(category, next_actions_by_category["kubernetes-runtime"])
        ]
        return {
            "hypotheses": hypotheses,
            "conclusion": {
                "statement": conclusion_statement,
                "confidence": confidence,
                "impact_scope": "MongoDB replica or shard availability; affected workload may have fewer ready members than desired.",
                "primary_cause_category": category,
                "evidence": [item["detail"] for item in evidence],
                "limitations": runtime_gaps,
                "deepest_supported_level": conclusion_level,
            },
            "next_actions": next_actions,
        }
    return {}


def analyse(
    input_data: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
    structured_record: Dict[str, Any] = None,
) -> Dict[str, Any]:
    structured_record = structured_record or {}
    scenario = str(input_data.get("scenario") or "unknown")
    ids = expand_kubernetes_runtime_ids(set(signal_ids(signal_bundle)), structured_record, scenario)
    evidence = evidence_from_signals(signal_bundle)
    evidence.extend(evidence_from_events(structured_record))
    gaps = collection_gaps(collection_report)

    overlay_result = network_overlay_conclusion(ids, evidence, gaps)
    storage_result = mongodb_storage_corruption_conclusion(ids, evidence, gaps)
    runtime_result = kubernetes_runtime_conclusion(ids, evidence, gaps, structured_record)
    if overlay_result:
        hypotheses = overlay_result["hypotheses"]
        conclusion = overlay_result["conclusion"]
        next_actions = overlay_result["next_actions"]
    elif storage_result:
        hypotheses = storage_result["hypotheses"]
        conclusion = storage_result["conclusion"]
        next_actions = storage_result["next_actions"]
    elif runtime_result:
        hypotheses = runtime_result["hypotheses"]
        conclusion = runtime_result["conclusion"]
        next_actions = runtime_result["next_actions"]
    elif scenario == "baseline":
        hypotheses = [
            hypothesis("H1", "MongoDB baseline fixture does not show incident-specific abnormal signals.", evidence, gaps, "supported")
        ]
        conclusion = {
            "statement": "Baseline collection is healthy enough for regression comparison.",
            "confidence": "high",
            "impact_scope": "none",
            "primary_cause_category": "baseline",
            "evidence": ["no abnormal signals in baseline fixture"],
            "limitations": gaps,
            "deepest_supported_level": "phenomenon",
        }
        next_actions = [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ]
    elif scenario == "connection-failure":
        supported = "service-endpoints-not-ready" in ids or "mongos-pod-not-ready" in ids
        hypotheses = [
            hypothesis(
                "H1",
                "MongoDB connection failure is caused by Service endpoint or mongos readiness failure.",
                evidence,
                gaps,
                "supported" if supported else "insufficient",
            ),
            hypothesis(
                "H2",
                "MongoDB connection failure is caused by authentication failure.",
                evidence,
                gaps,
                "refuted" if supported else "insufficient",
            ),
        ]
        conclusion = {
            "statement": "Initial evidence points to Kubernetes Service endpoint or mongos readiness failure.",
            "confidence": "medium" if supported else "low",
            "impact_scope": "mongos connection entrypoint",
            "primary_cause_category": "service-routing" if supported else "unknown",
            "evidence": [item["detail"] for item in evidence],
            "limitations": gaps,
            "deepest_supported_level": "mechanism" if supported else "phenomenon",
        }
        next_actions = [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ]
    elif scenario == "replica-inconsistency":
        supported = "replica-member-recovering" in ids
        hypotheses = [
            hypothesis(
                "H1",
                "A replica member health issue caused replica inconsistency symptoms.",
                evidence,
                gaps,
                "supported" if supported else "insufficient",
            ),
            hypothesis(
                "H2",
                "Resource pressure caused the replica member abnormal state.",
                evidence,
                gaps,
                "insufficient",
            ),
        ]
        conclusion = {
            "statement": "Initial evidence supports a replica member health issue.",
            "confidence": "medium" if supported else "low",
            "impact_scope": "replica set read path",
            "primary_cause_category": "replication" if supported else "unknown",
            "evidence": [item["detail"] for item in evidence],
            "limitations": gaps,
            "deepest_supported_level": "mechanism" if supported else "phenomenon",
        }
        next_actions = [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ]
    else:
        hypotheses = [
            hypothesis("H1", "The incident requires scenario-specific analysis rules.", evidence, gaps, "insufficient")
        ]
        conclusion = {
            "statement": "No scenario-specific analyse rule exists yet.",
            "confidence": "low",
            "impact_scope": "unknown",
            "primary_cause_category": "unknown",
            "evidence": [item["detail"] for item in evidence],
            "limitations": gaps,
            "deepest_supported_level": "phenomenon",
        }
        next_actions = [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ]

    conclusion = apply_conclusion_ceiling(conclusion, evidence, gaps, ids)
    verification_requests = verification_requests_for_gaps(
        scenario,
        ids,
        gaps,
        replica_members_from_record(structured_record),
        hypotheses,
    )

    return {
        "hypotheses": hypotheses,
        "conclusion_summary": conclusion,
        "next_actions": next_actions,
        "verification_requests": verification_requests,
        "knowledge_candidates": knowledge_candidates_for_scenario(scenario, str(conclusion.get("primary_cause_category") or "")),
        **analysis_contract_fields(input_data, signal_bundle, collection_report),
        "generated_at": "generated-by-mongodb-analyse",
        "updated_at": "generated-by-mongodb-analyse",
    }


def generate_analysis(input_dir: Path) -> Dict[str, Any]:
    input_data = load_yaml(input_dir / "input.yaml")
    signal_bundle = load_yaml(input_dir / "signal_bundle.yaml")
    collection_report = load_yaml(input_dir / "collection_report.yaml")
    structured_record_file = input_dir / "structured_record.yaml"
    structured_record = load_yaml(structured_record_file) if structured_record_file.exists() else {}
    return analyse(input_data, signal_bundle, collection_report, structured_record)


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    result = generate_analysis(input_dir)

    if args.output_file:
        write_yaml(Path(args.output_file), result)
    else:
        print(json.dumps(result, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
