#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

import yaml


ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = ROOT / "core" / "taxonomies" / "kubernetes-runtime-signal-types.yaml"
NORMALIZER = ROOT / "domains" / "mongodb" / "scripts" / "normalize" / "normalize-signals-bundle.py"
REQUIRED_CATEGORIES = {
    "scheduling",
    "storage-binding",
    "resource-scheduling",
    "image",
    "restart",
    "readiness",
    "workload-controller",
}


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def emitted_signal_ids(path: Path) -> Set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r'add\(\s*["\']([a-z0-9-]+)["\']', text))


def main() -> int:
    errors: List[str] = []
    data = load_yaml(TAXONOMY)
    if data.get("scope") != "kubernetes-runtime":
        errors.append("taxonomy scope must be kubernetes-runtime")

    values = data.get("values") or []
    if not isinstance(values, list) or not values:
        errors.append("taxonomy values must be a non-empty list")
        values = []

    ids: Set[str] = set()
    categories: Set[str] = set()
    for item in values:
        if not isinstance(item, dict):
            errors.append("taxonomy value must be an object: %r" % item)
            continue
        signal_id = item.get("id")
        category = item.get("category")
        if not isinstance(signal_id, str) or not signal_id:
            errors.append("taxonomy value missing id: %r" % item)
            continue
        if signal_id in ids:
            errors.append("duplicate signal id: %s" % signal_id)
        ids.add(signal_id)
        if not isinstance(category, str) or not category:
            errors.append("%s missing category" % signal_id)
        else:
            categories.add(category)
        if item.get("middleware_agnostic") is not True:
            errors.append("%s must be middleware_agnostic=true" % signal_id)
        if not isinstance(item.get("description"), str) or not item.get("description"):
            errors.append("%s missing description" % signal_id)

    missing_categories = REQUIRED_CATEGORIES - categories
    if missing_categories:
        errors.append("taxonomy missing required generic categories: %s" % sorted(missing_categories))

    emitted = emitted_signal_ids(NORMALIZER)
    unregistered = emitted - ids
    unused = ids - emitted
    if unregistered:
        errors.append("normalizer emits unregistered Kubernetes runtime signals: %s" % sorted(unregistered))
    if unused:
        errors.append("taxonomy contains signals not emitted by normalizer: %s" % sorted(unused))

    fixture = ROOT / "tests" / "fixtures" / "mongodb" / "kubernetes-scheduling-failure-sample" / "expected_analysis.yaml"
    expected = load_yaml(fixture)
    category = ((expected.get("conclusion_summary") or {}).get("primary_cause_category"))
    if category != "kubernetes-scheduling":
        errors.append("kubernetes scheduling fixture must expect kubernetes-scheduling category")

    if errors:
        for error in errors:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1

    print("Kubernetes runtime classification validation passed: %d signal type(s)" % len(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
