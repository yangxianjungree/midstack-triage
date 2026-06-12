#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FILES = [
    "input.yaml",
    "structured_record.yaml",
    "signal_bundle.yaml",
    "collection_report.yaml",
    "expected_analysis.yaml",
]


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Pulsar fixture summaries.")
    parser.add_argument("--fixture-root", default="tests/fixtures/pulsar")
    parser.add_argument("--run-analyse", action="store_true", help="Generate analysis.yaml for each ready fixture.")
    parser.add_argument("--output-root", default=".local/replay", help="Output root for generated analysis files.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def replay_case(case_dir: Path, run_analyse: bool, output_root: Path) -> Dict[str, Any]:
    missing: List[str] = []
    for filename in REQUIRED_FILES:
        if not (case_dir / filename).exists():
            missing.append(filename)
    if missing:
        return {"case_id": case_dir.name, "status": "invalid", "missing": missing}

    input_data = load_yaml(case_dir / "input.yaml")
    expected = load_yaml(case_dir / "expected_analysis.yaml")
    conclusion = expected.get("conclusion_summary") or {}
    result = {
        "case_id": case_dir.name,
        "status": "ready",
        "incident_id": input_data.get("incident_id"),
        "middleware": input_data.get("middleware"),
        "scenario": input_data.get("scenario"),
        "expected_conclusion": conclusion.get("statement"),
        "expected_confidence": conclusion.get("confidence"),
        "expected_primary_cause_category": conclusion.get("primary_cause_category"),
    }
    if run_analyse:
        output_file = output_root / ("%s.analysis.yaml" % case_dir.name)
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "analyse" / "pulsar-analyse.py"),
                "--input-dir",
                str(case_dir),
                "--output-file",
                str(output_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        result["analyse_exit_code"] = proc.returncode
        result["analysis_output"] = str(output_file)
        if proc.returncode != 0:
            result["status"] = "analyse_failed"
            result["stderr"] = proc.stderr.strip()
            return result
        actual = load_yaml(output_file)
        actual_conclusion = actual.get("conclusion_summary") or {}
        result["actual_conclusion"] = actual_conclusion.get("statement")
        result["actual_confidence"] = actual_conclusion.get("confidence")
        result["actual_primary_cause_category"] = actual_conclusion.get("primary_cause_category")
        result["conclusion_match"] = actual_conclusion.get("statement") == conclusion.get("statement")
        result["confidence_match"] = actual_conclusion.get("confidence") == conclusion.get("confidence")
        result["category_match"] = actual_conclusion.get("primary_cause_category") == conclusion.get("primary_cause_category")
    return result


def main() -> int:
    args = parse_args()
    fixture_root = ROOT / args.fixture_root
    output_root = ROOT / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)
    results = [replay_case(path, args.run_analyse, output_root) for path in sorted(fixture_root.iterdir()) if path.is_dir()]
    if args.format == "json":
        print(json.dumps(results, indent=2, sort_keys=False))
    else:
        for item in results:
            if item.get("status") == "ready" and args.run_analyse:
                print(
                    "%s: %s conclusion=%s category_match=%s output=%s"
                    % (
                        item["case_id"],
                        item["status"],
                        item.get("actual_confidence"),
                        item.get("category_match"),
                        item.get("analysis_output"),
                    )
                )
            else:
                print("%s: %s" % (item["case_id"], item.get("status")))
    failed = [item for item in results if item.get("status") != "ready" or (args.run_analyse and not item.get("category_match", True))]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
