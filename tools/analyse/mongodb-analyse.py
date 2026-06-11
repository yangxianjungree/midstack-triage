#!/usr/bin/env python3

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[2]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


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

    candidates: List[Dict[str, str]] = []
    roots = [
        ("runbook", ROOT / "domains" / "mongodb" / "runbooks"),
        ("command", ROOT / "domains" / "mongodb" / "commands"),
        ("skill", ROOT / "domains" / "mongodb" / "skills"),
    ]
    for candidate_type, root in roots:
        if not root.exists():
            continue
        for metadata_file in sorted(root.glob("**/metadata.yaml")):
            metadata = load_yaml(metadata_file)
            asset_scenario = metadata.get("scenario") or metadata.get("primary_scenario")
            if asset_scenario != scenario:
                continue
            candidates.append(
                {
                    "candidate_type": candidate_type,
                    "title": str(metadata.get("title") or metadata_file.parent.name),
                    "asset_path": str(metadata_file.parent.relative_to(ROOT)),
                    "reason": "Existing MongoDB %s asset matches scenario %s." % (candidate_type, scenario),
                }
            )
    return candidates


def has_critical_gap(gaps: List[Dict[str, Any]]) -> bool:
    return any(str(item.get("gap_type") or "") == "critical_gap" for item in gaps if isinstance(item, dict))


def direct_mongodb_error_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = "\n".join(str(item.get("detail") or "") for item in evidence).lower()
    return any(token in text for token in ("fatal", "wiredtiger", "corrupt", "journal", "bad magic number", "assertion", "unclean shutdown"))


def evidence_text(evidence: List[Dict[str, str]]) -> str:
    return "\n".join(str(item.get("detail") or "") for item in evidence).lower()


def has_peer_connection_log_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = evidence_text(evidence)
    return ("hostunreachable" in text or "host failed in replica set" in text or "rsm received error response" in text) and "connection refused" in text


def has_dns_startup_log_evidence(evidence: List[Dict[str, str]]) -> bool:
    text = evidence_text(evidence)
    return "cannot resolve host" in text and any(token in text for token in ("10.96.0.10:53", "i/o timeout", "connection refused", "temporary failure"))


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
    if has_critical_gap(gaps):
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
    if "pod-crashloop" in ids and not direct_mongodb_error_evidence(evidence) and level == "root_cause":
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


def kubernetes_runtime_conclusion(ids: set, evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
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
    for signal_id, category, confidence, conclusion_statement, hypothesis_statement in rules:
        if signal_id not in ids:
            continue
        peer_log_supported = has_peer_connection_log_evidence(evidence)
        dns_probe_supported = "dns-resolution-failed" in ids
        dns_log_seen = has_dns_startup_log_evidence(evidence)
        hypotheses = [
            hypothesis_with_actions(
                "H1",
                hypothesis_statement,
                evidence,
                gaps,
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
        hypotheses.append(
            hypothesis_with_actions(
                "H%s" % (len(hypotheses) + 1),
                "MongoDB internal replica set state caused the unavailable member symptom.",
                evidence,
                gaps,
                "insufficient",
                [
                    {
                        "action": "Collect rs.status from all schedulable members and compare member states.",
                        "result": "Evidence is insufficient when the affected Pod is not schedulable or not reachable.",
                        "risk_level": "read-only",
                    }
                ],
                [],
                ["All Kubernetes Pod and StatefulSet signals are healthy while rs.status shows an internal member state issue"],
            )
        )
        conclusion_level = "impact"
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
                "limitations": gaps,
                "deepest_supported_level": conclusion_level,
            },
            "next_actions": next_actions,
        }
    return {}


def analyse(input_data: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> Dict[str, Any]:
    scenario = str(input_data.get("scenario") or "unknown")
    ids = set(signal_ids(signal_bundle))
    evidence = evidence_from_signals(signal_bundle)
    gaps = collection_gaps(collection_report)

    runtime_result = kubernetes_runtime_conclusion(ids, evidence, gaps)
    if runtime_result:
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

    return {
        "hypotheses": hypotheses,
        "conclusion_summary": conclusion,
        "next_actions": next_actions,
        "knowledge_candidates": knowledge_candidates_for_scenario(scenario, str(conclusion.get("primary_cause_category") or "")),
        "generated_at": "generated-by-mongodb-analyse",
        "updated_at": "generated-by-mongodb-analyse",
    }


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir)
    input_data = load_yaml(input_dir / "input.yaml")
    signal_bundle = load_yaml(input_dir / "signal_bundle.yaml")
    collection_report = load_yaml(input_dir / "collection_report.yaml")
    result = analyse(input_data, signal_bundle, collection_report)

    if args.output_file:
        write_yaml(Path(args.output_file), result)
    else:
        print(json.dumps(result, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
