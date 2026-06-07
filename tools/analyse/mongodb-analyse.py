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


def knowledge_candidates_for_scenario(scenario: str) -> List[Dict[str, str]]:
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


def analyse(input_data: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> Dict[str, Any]:
    scenario = str(input_data.get("scenario") or "unknown")
    ids = set(signal_ids(signal_bundle))
    evidence = evidence_from_signals(signal_bundle)
    gaps = collection_gaps(collection_report)

    if scenario == "baseline":
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

    return {
        "hypotheses": hypotheses,
        "conclusion_summary": conclusion,
        "next_actions": [
            {
                "action": "Review evidence gaps and run the scenario-specific runbook.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ],
        "knowledge_candidates": knowledge_candidates_for_scenario(scenario),
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
