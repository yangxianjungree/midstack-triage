#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = ROOT / "tools" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from patch_merge import apply_script_output  # noqa: E402


FIXTURE_ROOT = ROOT / "tests" / "golden-paths" / "fixtures" / "patch-merge"


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def fail(errors: List[str], message: str) -> None:
    errors.append(message)


def assert_dict_equal(actual: Dict[str, Any], expected: Dict[str, Any], context: str, errors: List[str]) -> None:
    if actual != expected:
        fail(errors, "%s mismatch\nexpected=%r\nactual=%r" % (context, expected, actual))


def validate_multi_script_merge(errors: List[str]) -> None:
    structured_record: Dict[str, Any] = {"summary": {}, "details": {}}
    signal_bundle: Dict[str, Any] = {}
    collection_report: Dict[str, Any] = {
        "collection_actions": [],
        "successful_items": [],
        "failed_items": [],
        "blank_items": [],
        "evidence_gaps": [],
    }

    outputs = [
        load_yaml(FIXTURE_ROOT / "pods-script-output.yaml"),
        load_yaml(FIXTURE_ROOT / "rs-status-script-output.yaml"),
    ]
    for output in outputs:
        apply_script_output(structured_record, signal_bundle, collection_report, output)

    expected = load_yaml(FIXTURE_ROOT / "expected-structured_record.yaml")
    assert_dict_equal(structured_record.get("summary") or {}, expected.get("summary") or {}, "summary", errors)
    assert_dict_equal(structured_record.get("details") or {}, expected.get("details") or {}, "details", errors)

    if len(collection_report.get("collection_actions") or []) != 2:
        fail(
            errors,
            "collection_actions should append across scripts, got %d"
            % len(collection_report.get("collection_actions") or []),
        )


def validate_pod_key_merge(errors: List[str]) -> None:
    structured_record: Dict[str, Any] = {"summary": {}, "details": {}}
    signal_bundle: Dict[str, Any] = {}
    collection_report: Dict[str, Any] = {"collection_actions": []}

    first = {
        "structured_record_patch": {
            "details": {
                "pods": [{"name": "mongo-shard0-0", "phase": "Running", "status_hint": "healthy"}],
            }
        }
    }
    second = {
        "structured_record_patch": {
            "details": {
                "pods": [{"name": "mongo-shard0-0", "restart_count": 3, "status_hint": "degraded"}],
            }
        }
    }
    apply_script_output(structured_record, signal_bundle, collection_report, first)
    apply_script_output(structured_record, signal_bundle, collection_report, second)

    pods = structured_record.get("details", {}).get("pods") or []
    if len(pods) != 1:
        fail(errors, "pods merge-by-name should keep one item, got %d" % len(pods))
        return
    pod = pods[0]
    if pod.get("phase") != "Running":
        fail(errors, "pods merge-by-name should preserve earlier fields")
    if pod.get("restart_count") != 3:
        fail(errors, "pods merge-by-name should apply later field updates")
    if pod.get("status_hint") != "degraded":
        fail(errors, "pods merge-by-name should apply later status_hint")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate incident patch merge rules.")
    parser.parse_args()
    errors: List[str] = []
    validate_multi_script_merge(errors)
    validate_pod_key_merge(errors)

    if errors:
        print("Patch merge validation failed:", file=sys.stderr)
        for item in errors:
            print("- %s" % item, file=sys.stderr)
        return 1

    print("Patch merge validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
