import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from support.common import ROOT, load_yaml

DIMENSIONS = [
    "evidence_completeness",
    "hypothesis_coverage",
    "validation_depth",
    "conclusion_confidence",
    "knowledge_reusability",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize MongoDB replay score files.")
    parser.add_argument("--score-root", default="tests/scores/mongodb")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def summarize_score(path: Path) -> Dict[str, Any]:
    data = load_yaml(path)
    score = data.get("score") or {}
    missing: List[str] = []
    levels: Dict[str, str] = {}
    for dimension in DIMENSIONS:
        item = score.get(dimension) or {}
        level = item.get("level")
        if not level:
            missing.append(dimension)
        else:
            levels[dimension] = str(level)
    return {
        "case_id": data.get("case_id") or path.stem.replace(".score", ""),
        "middleware": data.get("middleware"),
        "status": "ready" if not missing else "invalid",
        "missing": missing,
        "levels": levels,
    }


def main() -> int:
    args = parse_args()
    score_root = ROOT / args.score_root
    if not score_root.exists():
        print("ERROR: score root does not exist: %s" % score_root, file=sys.stderr)
        return 1
    results = [summarize_score(path) for path in sorted(score_root.glob("*.score.yaml"))]
    failed = [item for item in results if item.get("status") != "ready"]

    if args.format == "json":
        print(json.dumps({"results": results}, indent=2, sort_keys=False))
    else:
        for item in results:
            levels = item.get("levels") or {}
            print("%s: %s evidence=%s conclusion=%s" % (
                item.get("case_id"),
                item.get("status"),
                levels.get("evidence_completeness", ""),
                levels.get("conclusion_confidence", ""),
            ))

    return 1 if failed else 0
