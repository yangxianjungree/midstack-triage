import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from support.common import ROOT, load_yaml, now_iso, run_command, write_yaml

DIMENSIONS = [
    "evidence_completeness",
    "hypothesis_coverage",
    "validation_depth",
    "conclusion_confidence",
    "knowledge_reusability",
]
LEVEL_ORDER = {"low": 1, "medium": 2, "high": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score MongoDB replay analysis outputs.")
    parser.add_argument("--fixture-root", default="tests/fixtures/active/mongodb")
    parser.add_argument("--analysis-root", default=".local/replay")
    parser.add_argument("--output-root", default=".local/scores/mongodb")
    parser.add_argument("--run-analyse", action="store_true", help="Generate missing or stale analysis files before scoring.")
    parser.add_argument("--min-level", choices=["low", "medium", "high"], default="low", help="Fail if any score dimension is below this level.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def score_item(level: str, reason: str) -> Dict[str, str]:
    return {"level": level, "reason": reason}


def hypotheses_by_id(data: Dict[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in data.get("hypotheses") or []:
        if not isinstance(item, dict):
            continue
        hypothesis_id = item.get("hypothesis_id")
        if hypothesis_id:
            result[str(hypothesis_id)] = str(item.get("validation_result") or item.get("status") or "")
    return result


def knowledge_titles(data: Dict[str, Any]) -> List[str]:
    titles: List[str] = []
    for item in data.get("knowledge_candidates") or []:
        if isinstance(item, dict) and item.get("title"):
            titles.append(str(item["title"]))
    return titles


def ensure_analysis(case_dir: Path, analysis_file: Path, run_analyse: bool) -> Tuple[bool, str]:
    if analysis_file.exists() and not run_analyse:
        return True, ""
    if not run_analyse:
        return False, "missing analysis file: %s" % analysis_file
    proc = run_command(
        [
            sys.executable,
            str(ROOT / "src" / "phases" / "phase4" / "rules" / "mongodb.py"),
            "--input-dir",
            str(case_dir),
            "--output-file",
            str(analysis_file),
        ]
    )
    if proc.returncode != 0:
        return False, proc.stderr.strip()
    return True, ""


def score_case(case_dir: Path, analysis_root: Path, output_root: Path, run_analyse: bool) -> Dict[str, Any]:
    case_id = case_dir.name
    input_file = case_dir / "input.yaml"
    expected_file = case_dir / "expected_analysis.yaml"
    if not input_file.exists() or not expected_file.exists():
        return {"case_id": case_id, "status": "invalid", "error": "missing input.yaml or expected_analysis.yaml"}

    input_data = load_yaml(input_file)
    expected = load_yaml(expected_file)
    analysis_file = analysis_root / ("%s.analysis.yaml" % case_id)
    ready, error = ensure_analysis(case_dir, analysis_file, run_analyse)
    if not ready:
        return {"case_id": case_id, "status": "failed", "error": error}

    actual = load_yaml(analysis_file)
    expected_conclusion = expected.get("conclusion_summary") or {}
    actual_conclusion = actual.get("conclusion_summary") or {}
    expected_category = expected_conclusion.get("primary_cause_category")
    actual_category = actual_conclusion.get("primary_cause_category")
    expected_confidence = expected_conclusion.get("confidence")
    actual_confidence = actual_conclusion.get("confidence")
    category_match = expected_category == actual_category
    confidence_match = expected_confidence == actual_confidence

    expected_hypotheses = hypotheses_by_id(expected)
    actual_hypotheses = hypotheses_by_id(actual)
    matched_hypotheses = {
        key: expected_hypotheses[key] == actual_hypotheses.get(key)
        for key in expected_hypotheses
    }
    hypothesis_all_match = bool(expected_hypotheses) and all(matched_hypotheses.values())

    actual_evidence = actual_conclusion.get("evidence") or []
    if input_data.get("scenario") == "baseline" or actual_evidence:
        evidence_level = "high"
        evidence_reason = "Actual analysis includes conclusion evidence or baseline does not require abnormal evidence."
    elif category_match:
        evidence_level = "medium"
        evidence_reason = "Primary cause matches, but conclusion evidence is thin."
    else:
        evidence_level = "low"
        evidence_reason = "Primary cause does not match and evidence is insufficient."

    if hypothesis_all_match:
        hypothesis_level = "high"
        hypothesis_reason = "Expected hypothesis ids and validation results match."
    elif category_match:
        hypothesis_level = "medium"
        hypothesis_reason = "Primary cause matches, but hypothesis statuses differ or are incomplete."
    else:
        hypothesis_level = "low"
        hypothesis_reason = "Hypothesis coverage does not support the expected conclusion."

    validation_actions = actual.get("validation_actions") or []
    if validation_actions and hypothesis_all_match:
        validation_level = "high"
        validation_reason = "Analysis includes explicit validation actions and matching hypothesis results."
    elif category_match:
        validation_level = "medium"
        validation_reason = "Replay validates the conclusion path, but no extra live validation actions were executed."
    else:
        validation_level = "low"
        validation_reason = "Validation output does not confirm the expected primary cause."

    if category_match and confidence_match:
        conclusion_level = "high"
        conclusion_reason = "Primary cause category and confidence match expected analysis."
    elif category_match:
        conclusion_level = "medium"
        conclusion_reason = "Primary cause category matches, but confidence differs."
    else:
        conclusion_level = "low"
        conclusion_reason = "Primary cause category differs from expected analysis."

    expected_knowledge = knowledge_titles(expected)
    actual_knowledge = knowledge_titles(actual)
    if expected_knowledge and set(expected_knowledge).issubset(set(actual_knowledge)):
        knowledge_level = "high"
        knowledge_reason = "Expected knowledge candidates are present."
    elif expected_knowledge:
        knowledge_level = "medium"
        knowledge_reason = "Expected case has reusable knowledge, but generated candidates are incomplete."
    else:
        knowledge_level = "medium"
        knowledge_reason = "Case is useful as replay regression data, not as a new knowledge source."

    score = {
        "evidence_completeness": score_item(evidence_level, evidence_reason),
        "hypothesis_coverage": score_item(hypothesis_level, hypothesis_reason),
        "validation_depth": score_item(validation_level, validation_reason),
        "conclusion_confidence": score_item(conclusion_level, conclusion_reason),
        "knowledge_reusability": score_item(knowledge_level, knowledge_reason),
    }
    status = "ready" if category_match else "failed"
    result = {
        "case_id": case_id,
        "middleware": input_data.get("middleware"),
        "scenario": input_data.get("scenario"),
        "status": status,
        "analysis_file": str(analysis_file),
        "expected": {
            "primary_cause_category": expected_category,
            "confidence": expected_confidence,
            "hypotheses": expected_hypotheses,
            "knowledge_titles": expected_knowledge,
        },
        "actual": {
            "primary_cause_category": actual_category,
            "confidence": actual_confidence,
            "hypotheses": actual_hypotheses,
            "knowledge_titles": actual_knowledge,
        },
        "checks": {
            "category_match": category_match,
            "confidence_match": confidence_match,
            "matched_hypotheses": matched_hypotheses,
        },
        "score": score,
        "generated_at": now_iso(),
    }
    write_yaml(output_root / ("%s.score.yaml" % case_id), result)
    return result


def below_threshold(score: Dict[str, Any], min_level: str) -> List[str]:
    threshold = LEVEL_ORDER[min_level]
    failed: List[str] = []
    for dimension in DIMENSIONS:
        item = score.get(dimension) or {}
        level = str(item.get("level") or "low")
        if LEVEL_ORDER.get(level, 0) < threshold:
            failed.append(dimension)
    return failed


def main() -> int:
    args = parse_args()
    fixture_root = ROOT / args.fixture_root
    analysis_root = ROOT / args.analysis_root
    output_root = ROOT / args.output_root
    if not fixture_root.exists():
        print("ERROR: fixture root does not exist: %s" % fixture_root, file=sys.stderr)
        return 1

    results = [
        score_case(path, analysis_root, output_root, args.run_analyse)
        for path in sorted(fixture_root.iterdir())
        if path.is_dir()
    ]
    failed = [item for item in results if item.get("status") != "ready"]
    for item in results:
        score = item.get("score") or {}
        threshold_failures = below_threshold(score, args.min_level) if score else []
        item["threshold_failures"] = threshold_failures
        if threshold_failures and item not in failed:
            failed.append(item)
    if args.format == "json":
        print(json.dumps({"results": results}, indent=2, sort_keys=False))
    else:
        for item in results:
            score = item.get("score") or {}
            conclusion = score.get("conclusion_confidence") or {}
            print("%s: %s conclusion=%s category_match=%s" % (
                item.get("case_id"),
                "failed" if item.get("threshold_failures") else item.get("status"),
                conclusion.get("level", ""),
                (item.get("checks") or {}).get("category_match", ""),
            ))
    return 1 if failed else 0
