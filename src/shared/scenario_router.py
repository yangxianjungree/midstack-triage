from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAP_PATH = ROOT / "core" / "routing" / "scenario-signal-map.yaml"


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def load_routing_map(path: Optional[Path] = None) -> Dict[str, Any]:
    return load_yaml(path or DEFAULT_MAP_PATH)


def signal_ids_from_bundle(signal_bundle: Dict[str, Any]) -> Set[str]:
    ids: Set[str] = set()
    for item in signal_bundle.get("abnormal_signals") or []:
        if isinstance(item, dict):
            signal_id = str(item.get("signal_id") or "").strip()
            if signal_id:
                ids.add(signal_id)
    return ids


def log_categories_from_bundle(signal_bundle: Dict[str, Any]) -> Set[str]:
    categories: Set[str] = set()
    for item in signal_bundle.get("processed_log_highlights") or []:
        if isinstance(item, dict):
            category = str(item.get("category") or "").strip().lower()
            if category:
                categories.add(category)
    for item in signal_bundle.get("log_highlights") or []:
        if isinstance(item, dict):
            category = str(item.get("category") or "").strip().lower()
            if category:
                categories.add(category)
    return categories


def structured_record_has_path(structured_record: Dict[str, Any], dotted_path: str) -> bool:
    current: Any = structured_record
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if current is None:
        return False
    if isinstance(current, (list, dict)):
        return bool(current)
    return bool(str(current).strip())


def clue_keyword_boost(scenario: str, customer_clue: str, clue_keywords: Dict[str, List[str]]) -> float:
    clue = customer_clue.lower()
    if not clue:
        return 0.0
    keywords = clue_keywords.get(scenario) or []
    hits = sum(1 for keyword in keywords if keyword in clue)
    if hits == 0:
        return 0.0
    return min(0.1, 0.03 * hits)


def score_route(
    route: Dict[str, Any],
    signal_ids: Set[str],
    log_categories: Set[str],
    structured_record: Dict[str, Any],
    customer_clue: str,
    clue_keywords: Dict[str, List[str]],
) -> Tuple[float, List[str]]:
    matched_signals: List[str] = []
    score = 0.0
    weight = float(route.get("signal_weight") or 1.0)

    for signal_id in route.get("when_any_signal") or []:
        if signal_id in signal_ids:
            matched_signals.append(str(signal_id))
            score += weight

    for category in route.get("when_log_highlight_category") or []:
        if str(category).lower() in log_categories:
            matched_signals.append("log:%s" % category)
            score += weight * 0.5

    for path in route.get("when_structured_record_path_exists") or []:
        if structured_record_has_path(structured_record, str(path)):
            matched_signals.append("record:%s" % path)
            score += float(route.get("structured_record_weight") or 0.25)

    if score > 0.0:
        score += clue_keyword_boost(str(route.get("scenario") or ""), customer_clue, clue_keywords)

    return score, matched_signals


def confidence_from_score(score: float, thresholds: Dict[str, Any]) -> str:
    high = float(thresholds.get("high") or 0.65)
    medium = float(thresholds.get("medium") or 0.35)
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    return "low"


def infer_scenario(
    signal_bundle: Dict[str, Any],
    structured_record: Optional[Dict[str, Any]] = None,
    customer_clue: str = "",
    middleware: str = "mongodb",
    routing_map: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    routing_map = routing_map or load_routing_map()
    structured_record = structured_record or {}
    signal_ids = signal_ids_from_bundle(signal_bundle)
    log_categories = log_categories_from_bundle(signal_bundle)
    clue_keywords = routing_map.get("clue_tie_break_keywords") or {}
    thresholds = routing_map.get("confidence_thresholds") or {}
    unresolved_gap = float(routing_map.get("unresolved_score_gap") or 0.15)

    candidates: List[Dict[str, Any]] = []
    for route in routing_map.get("routes") or []:
        if not isinstance(route, dict):
            continue
        allowed = [str(item) for item in route.get("middleware") or []]
        if allowed and middleware not in allowed:
            continue
        scenario = str(route.get("scenario") or "")
        if not scenario:
            continue
        score, matched_signals = score_route(
            route,
            signal_ids,
            log_categories,
            structured_record,
            customer_clue,
            clue_keywords,
        )
        if score <= 0.0:
            continue
        candidates.append(
            {
                "scenario": scenario,
                "score": round(score, 4),
                "matched_signals": matched_signals,
            }
        )

    candidates.sort(key=lambda item: (-float(item["score"]), str(item["scenario"])))
    if not candidates:
        return {
            "scenario": "unknown",
            "scenario_inference": {
                "method": "signal_bundle_rules_v1",
                "confidence": "low",
                "candidates": [],
                "unresolved": True,
                "matched_signals": [],
            },
        }

    top = candidates[0]
    second_score = float(candidates[1]["score"]) if len(candidates) > 1 else 0.0
    unresolved = len(candidates) > 1 and (float(top["score"]) - second_score) < unresolved_gap
    confidence = confidence_from_score(float(top["score"]), thresholds)
    if unresolved and confidence == "high":
        confidence = "medium"

    return {
        "scenario": str(top["scenario"]),
        "scenario_inference": {
            "method": "signal_bundle_rules_v1",
            "confidence": confidence,
            "candidates": candidates[:5],
            "unresolved": unresolved,
            "matched_signals": list(top.get("matched_signals") or []),
        },
    }

