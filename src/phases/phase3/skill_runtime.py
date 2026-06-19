"""Phase 3 skill runtime context helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from shared.skill_resolver import (
    extract_script_ids,
    matched_asset_refs,
    missing_required_scripts,
    recollection_script_pool,
    resolve_skills,
    script_collection_statuses,
)
from shared.workspace import load_yaml, now_iso, write_yaml


def scenario_candidates(input_data: Dict[str, Any]) -> List[str]:
    scenarios: List[str] = []
    primary = str(input_data.get("scenario") or "unknown")
    if primary:
        scenarios.append(primary)
    inference = input_data.get("scenario_inference") or {}
    if inference.get("unresolved"):
        for item in inference.get("candidates") or []:
            if not isinstance(item, dict):
                continue
            scenario = str(item.get("scenario") or "")
            if scenario:
                scenarios.append(scenario)
    result: List[str] = []
    seen = set()
    for scenario in scenarios:
        if scenario in ("", "unknown", "baseline") or scenario in seen:
            continue
        seen.add(scenario)
        result.append(scenario)
    return result


def resolve_skill_runtime(input_data: Dict[str, Any], output_dir: Path, collection_report: Dict[str, Any]) -> Dict[str, Any]:
    middleware = str(input_data.get("middleware") or "mongodb")
    scenarios = scenario_candidates(input_data)
    skills: List[Dict[str, Any]] = []
    skill_pool = set()
    for scenario in scenarios:
        skills.extend(resolve_skills(middleware, scenario))
        skill_pool.update(recollection_script_pool(middleware, scenario))
    required_scripts: List[str] = []
    for skill in skills:
        required_scripts.extend(extract_script_ids(skill["metadata"]))
    required_scripts = sorted(set(required_scripts))

    script_statuses = script_collection_statuses(output_dir, collection_report)
    missing_or_failed = missing_required_scripts(required_scripts, script_statuses)
    return {
        "skills": skills,
        "scenarios": scenarios,
        "skill_pool": skill_pool,
        "required_scripts": required_scripts,
        "missing_or_failed": missing_or_failed,
        "script_statuses": script_statuses,
    }


def write_skill_runtime_context(
    output_dir: Path,
    input_data: Dict[str, Any],
    collection_report: Dict[str, Any],
    runtime: Dict[str, Any],
    middleware: str,
) -> None:
    skills = runtime.get("skills") or []
    skill_pool = runtime.get("skill_pool") or set()
    collection_report["skill_evidence_check"] = {
        "scenarios": runtime.get("scenarios") or [],
        "skill_ids": [skill["id"] for skill in skills],
        "required_scripts": runtime.get("required_scripts") or [],
        "recollection_script_pool": sorted(skill_pool),
        "script_statuses": runtime.get("script_statuses") or {},
        "missing_or_failed": runtime.get("missing_or_failed") or [],
    }
    collection_report["updated_at"] = now_iso()
    write_yaml(output_dir / "collection_report.yaml", collection_report)

    input_data["matched_skill_ids"] = [skill["id"] for skill in skills]
    input_data["matched_assets"] = matched_asset_refs(middleware, skills)
    write_yaml(output_dir / "input.yaml", input_data)


def enrich_skill_runtime_context(output_dir: Path, input_data: Dict[str, Any]) -> Dict[str, Any]:
    collection_report_file = output_dir / "collection_report.yaml"
    collection_report = load_yaml(collection_report_file) if collection_report_file.exists() else {}
    runtime = resolve_skill_runtime(input_data, output_dir, collection_report)
    middleware = str(input_data.get("middleware") or "mongodb")
    write_skill_runtime_context(output_dir, input_data, collection_report, runtime, middleware)
    return {
        "skills": runtime["skills"],
        "skill_pool": runtime["skill_pool"],
        "required_scripts": runtime["required_scripts"],
        "missing_or_failed": runtime["missing_or_failed"],
    }
