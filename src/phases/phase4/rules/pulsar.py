#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[4]


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
    parser = argparse.ArgumentParser(description="Generate a minimal Pulsar analysis.yaml from a fixture or incident directory.")
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


def collection_gaps(collection_report: Dict[str, Any]) -> List[Dict[str, Any]]:
    gaps = collection_report.get("evidence_gaps") or []
    return [item for item in gaps if isinstance(item, dict)]


def hypothesis(hid: str, statement: str, evidence: List[Dict[str, str]], gaps: List[Dict[str, Any]], status: str) -> Dict[str, Any]:
    return {
        "hypothesis_id": hid,
        "statement": statement,
        "supporting_evidence": evidence,
        "evidence_gaps": gaps,
        "validation_result": status,
        "status": status,
    }


def knowledge_candidates_for_scenario(scenario: str) -> List[Dict[str, str]]:
    if scenario in ("", "unknown", "baseline"):
        return []
    candidates: List[Dict[str, str]] = []
    roots = [
        ("runbook", ROOT / "domains" / "pulsar" / "runbooks"),
        ("command", ROOT / "domains" / "pulsar" / "commands"),
        ("skill", ROOT / "domains" / "pulsar" / "skills"),
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
                    "reason": "Existing Pulsar %s asset matches scenario %s." % (candidate_type, scenario),
                }
            )
    return candidates


def analyse(input_data: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> Dict[str, Any]:
    scenario = str(input_data.get("scenario") or "unknown")
    ids = set(signal_ids(signal_bundle))
    evidence = evidence_from_signals(signal_bundle)
    gaps = collection_gaps(collection_report)

    if scenario == "queue-backlog" or "topic-backlog-high" in ids or "consumer-lag-high" in ids:
        supported = "topic-backlog-high" in ids or "consumer-lag-high" in ids
        hypotheses = [
            hypothesis(
                "H1",
                "Topic backlog growth is caused by consumer lag or stalled consumption.",
                evidence,
                gaps,
                "supported" if "consumer-lag-high" in ids else "insufficient",
            ),
            hypothesis(
                "H2",
                "Topic backlog growth is caused by broker or bookie write pressure.",
                evidence,
                gaps,
                "supported" if "topic-backlog-high" in ids else "insufficient",
            ),
        ]
        conclusion = {
            "statement": "Initial evidence supports a Pulsar topic backlog issue affecting the reported tenant/topic.",
            "confidence": "medium" if supported else "low",
            "impact_scope": "affected topic publish/consume path",
            "primary_cause_category": "topic-backlog" if supported else "unknown",
            "evidence": [item["detail"] for item in evidence],
            "limitations": gaps,
            "deepest_supported_level": "mechanism" if supported else "phenomenon",
        }
    else:
        hypotheses = [hypothesis("H1", "The incident requires scenario-specific Pulsar analysis rules.", evidence, gaps, "insufficient")]
        conclusion = {
            "statement": "No scenario-specific Pulsar analyse rule exists yet.",
            "confidence": "low",
            "impact_scope": "unknown",
            "primary_cause_category": "unknown",
            "evidence": [item["detail"] for item in evidence],
            "limitations": gaps,
            "deepest_supported_level": "phenomenon",
        }

    return {
        "hypotheses": hypotheses,
        "conclusion_summary": conclusion,
        "next_actions": [
            {
                "action": "Review broker topic stats and subscription lag for the affected topic.",
                "risk_level": "read-only",
                "requires_confirmation": False,
            }
        ],
        "knowledge_candidates": knowledge_candidates_for_scenario(scenario if scenario not in ("unknown", "baseline") else "queue-backlog"),
        "generated_at": "generated-by-pulsar-analyse",
        "updated_at": "generated-by-pulsar-analyse",
    }


def generate_analysis(input_dir: Path) -> Dict[str, Any]:
    return analyse(
        load_yaml(input_dir / "input.yaml"),
        load_yaml(input_dir / "signal_bundle.yaml"),
        load_yaml(input_dir / "collection_report.yaml"),
    )


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
