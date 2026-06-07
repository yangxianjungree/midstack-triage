#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

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
    return evidence


def collection_gaps(collection_report: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    for item in collection_report.get("evidence_gaps") or []:
        if isinstance(item, str):
            gaps.append(item)
        elif isinstance(item, dict):
            gaps.append(str(item.get("gap") or item))
    return gaps


def hypothesis(hid: str, statement: str, evidence: List[Dict[str, str]], gaps: List[str], status: str) -> Dict[str, Any]:
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
    gaps: List[str],
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
        scenario = "resource-exhaustion"
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


def kubernetes_runtime_conclusion(ids: set, evidence: List[Dict[str, str]], gaps: List[str]) -> Dict[str, Any]:
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
            hypothesis_with_actions(
                "H2",
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
            ),
        ]
        if signal_id == "pod-node-selector-mismatch":
            hypotheses[1]["statement"] = "MongoDB shard member is unavailable because of storage binding failure."
            hypotheses[1]["validation_result"] = "refuted"
            hypotheses[1]["status"] = "refuted"
            hypotheses[1]["disconfirming_conditions"] = ["PVC is unbound or scheduler event reports volume binding failure"]
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
        }
        next_actions = [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ]

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
