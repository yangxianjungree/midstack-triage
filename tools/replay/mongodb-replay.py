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
    parser = argparse.ArgumentParser(description="Replay MongoDB fixture summaries.")
    parser.add_argument("--fixture-root", default="tests/fixtures/mongodb")
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
        return {
            "case_id": case_dir.name,
            "status": "invalid",
            "missing": missing,
        }

    input_data = load_yaml(case_dir / "input.yaml")
    expected = load_yaml(case_dir / "expected_analysis.yaml")
    conclusion = expected.get("conclusion_summary") or {}
    result = {
        "case_id": case_dir.name,
        "status": "ready",
        "incident_id": input_data.get("incident_id"),
        "middleware": input_data.get("middleware"),
        "scenario": input_data.get("scenario"),
        "customer_clue": input_data.get("customer_clue"),
        "expected_conclusion": conclusion.get("statement"),
        "expected_confidence": conclusion.get("confidence"),
        "expected_primary_cause_category": conclusion.get("primary_cause_category"),
    }
    if run_analyse:
        output_file = output_root / ("%s.analysis.yaml" % case_dir.name)
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "analyse" / "mongodb-analyse.py"),
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
        result["analysis_output_file"] = str(output_file)
        if proc.returncode != 0:
            result["status"] = "failed"
            result["analyse_error"] = proc.stderr.strip()
        else:
            actual = load_yaml(output_file)
            actual_conclusion = actual.get("conclusion_summary") or {}
            expected_category = conclusion.get("primary_cause_category")
            actual_category = actual_conclusion.get("primary_cause_category")
            result["actual_primary_cause_category"] = actual_category
            result["category_match"] = expected_category == actual_category
            if not result["category_match"]:
                result["status"] = "failed"
    return result


def main() -> int:
    args = parse_args()
    fixture_root = ROOT / args.fixture_root
    if not fixture_root.exists():
        print("ERROR: fixture root does not exist: %s" % fixture_root, file=sys.stderr)
        return 1

    output_root = ROOT / args.output_root
    results = [replay_case(path, args.run_analyse, output_root) for path in sorted(fixture_root.iterdir()) if path.is_dir()]
    failed = [item for item in results if item.get("status") != "ready"]

    if args.format == "json":
        print(json.dumps({"results": results}, indent=2, sort_keys=False))
    else:
        for item in results:
            suffix = ""
            if args.run_analyse:
                suffix = " actual=%s match=%s output=%s" % (
                    item.get("actual_primary_cause_category", ""),
                    item.get("category_match", ""),
                    item.get("analysis_output_file", ""),
                )
            print("%s: %s scenario=%s expected=%s%s" % (
                item.get("case_id"),
                item.get("status"),
                item.get("scenario", ""),
                item.get("expected_primary_cause_category", ""),
                suffix,
            ))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
