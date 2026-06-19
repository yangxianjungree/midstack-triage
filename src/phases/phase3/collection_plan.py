"""Phase 3 collection planning helpers."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from shared.workspace import load_yaml, now_iso, runtime_root, write_yaml


DEFAULT_COLLECTION_TIER = "directed"
DEFAULT_COST_CLASS = "medium"
DEFAULT_NOISE_CLASS = "medium"
DEFAULT_SIGNAL_LAYER = "unknown"


def manifest_path_for(middleware: str) -> Path:
    return runtime_root() / "domains" / middleware / "scripts" / "manifest.yaml"


def _script_plan_item(item: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        "script_id": str(item.get("script_id") or ""),
        "phase": str(item.get("phase") or ""),
        "target": str(item.get("target") or ""),
        "tier": str(item.get("collection_tier") or DEFAULT_COLLECTION_TIER),
        "signal_layer": str(item.get("signal_layer") or DEFAULT_SIGNAL_LAYER),
        "cost_class": str(item.get("cost_class") or DEFAULT_COST_CLASS),
        "noise_class": str(item.get("noise_class") or DEFAULT_NOISE_CLASS),
        "readonly": bool(item.get("readonly")),
        "mvp": bool(item.get("mvp")),
    }
    if item.get("sample_policy"):
        result["sample_policy"] = item["sample_policy"]
    if item.get("trigger_policy"):
        result["trigger_policy"] = item["trigger_policy"]
    return result


def _candidate_scripts(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    scripts = []
    for item in manifest.get("scripts") or []:
        if not isinstance(item, dict):
            continue
        if item.get("phase") not in ("collect", "normalize"):
            continue
        if item.get("default_packaged") is not True:
            continue
        scripts.append(_script_plan_item(item))
    return scripts


def _layer_summary(scripts: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    summary: Dict[str, Dict[str, int]] = {}
    for item in scripts:
        layer = str(item.get("signal_layer") or DEFAULT_SIGNAL_LAYER)
        tier = str(item.get("tier") or DEFAULT_COLLECTION_TIER)
        entry = summary.setdefault(layer, {"baseline_count": 0, "directed_count": 0})
        if tier == "baseline":
            entry["baseline_count"] += 1
        else:
            entry["directed_count"] += 1
    return dict(sorted(summary.items()))


def _resource_budget(baseline_scripts: List[Dict[str, Any]], directed_scripts: List[Dict[str, Any]]) -> Dict[str, Any]:
    baseline_costs = Counter(str(item.get("cost_class") or DEFAULT_COST_CLASS) for item in baseline_scripts)
    directed_costs = Counter(str(item.get("cost_class") or DEFAULT_COST_CLASS) for item in directed_scripts)
    return {
        "baseline_cost_classes": dict(sorted(baseline_costs.items())),
        "directed_cost_classes": dict(sorted(directed_costs.items())),
        "baseline_high_noise_count": sum(1 for item in baseline_scripts if item.get("noise_class") == "high"),
        "directed_high_noise_count": sum(1 for item in directed_scripts if item.get("noise_class") == "high"),
    }


def build_collection_plan(manifest: Dict[str, Any]) -> Dict[str, Any]:
    scripts = _candidate_scripts(manifest)
    baseline_scripts = [item for item in scripts if item["tier"] == "baseline"]
    directed_scripts = [item for item in scripts if item["tier"] != "baseline"]
    return {
        "middleware": str(manifest.get("middleware") or ""),
        "generated_at": now_iso(),
        "baseline_script_ids": [item["script_id"] for item in baseline_scripts],
        "directed_script_ids": [item["script_id"] for item in directed_scripts],
        "baseline_scripts": baseline_scripts,
        "directed_scripts": directed_scripts,
        "layer_summary": _layer_summary(scripts),
        "resource_budget": _resource_budget(baseline_scripts, directed_scripts),
    }


def write_collection_plan(output_dir: Path, middleware: str = "mongodb") -> Dict[str, Any]:
    manifest_path = manifest_path_for(middleware)
    if not manifest_path.exists():
        return {}
    manifest = load_yaml(manifest_path)
    plan = build_collection_plan(manifest)
    write_yaml(output_dir / "collection_plan.yaml", plan)
    return plan
