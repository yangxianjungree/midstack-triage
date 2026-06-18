from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from shared.io import load_yaml_object as load_yaml

ROOT = Path(__file__).resolve().parents[2]


def load_manifest_readonly_scripts(middleware: str) -> Set[str]:
    manifest_path = ROOT / "domains" / middleware / "scripts" / "manifest.yaml"
    if not manifest_path.exists():
        return set()
    data = load_yaml(manifest_path)
    readonly: Set[str] = set()
    for item in data.get("scripts") or []:
        if not isinstance(item, dict):
            continue
        script_id = str(item.get("script_id") or "")
        if script_id and bool(item.get("readonly", True)):
            readonly.add(script_id)
    return readonly


def skill_roots(middleware: str) -> Path:
    return ROOT / "domains" / middleware / "skills"


def resolve_skills(middleware: str, scenario: str) -> List[Dict[str, Any]]:
    root = skill_roots(middleware)
    if not root.exists() or scenario in ("", "unknown", "baseline"):
        return []

    matches: List[Dict[str, Any]] = []
    for metadata_file in sorted(root.glob("**/metadata.yaml")):
        metadata = load_yaml(metadata_file)
        if str(metadata.get("middleware") or middleware) != middleware:
            continue
        if str(metadata.get("primary_scenario") or "") != scenario:
            continue
        skill_dir = metadata_file.parent
        matches.append(
            {
                "id": str(metadata.get("id") or skill_dir.name),
                "metadata": metadata,
                "metadata_path": metadata_file,
                "skill_dir": skill_dir,
                "skill_md_path": skill_dir / "skill.md",
            }
        )
    return matches


def extract_required_assets(metadata: Dict[str, Any], asset_type: Optional[str] = None) -> List[Dict[str, str]]:
    assets: List[Dict[str, str]] = []
    for item in metadata.get("required_assets") or []:
        if isinstance(item, dict):
            item_type = str(item.get("type") or "")
            item_id = str(item.get("id") or "")
            if item_type and item_id:
                if asset_type is None or item_type == asset_type:
                    assets.append({"type": item_type, "id": item_id})
        elif isinstance(item, str) and asset_type is None:
            assets.append({"type": "path", "id": item})
    return assets


def extract_script_ids(metadata: Dict[str, Any]) -> List[str]:
    return [item["id"] for item in extract_required_assets(metadata, "script")]


def recollection_script_pool(middleware: str, scenario: str) -> Set[str]:
    readonly = load_manifest_readonly_scripts(middleware)
    pool: Set[str] = set()
    for skill in resolve_skills(middleware, scenario):
        for script_id in extract_script_ids(skill["metadata"]):
            if script_id in readonly:
                pool.add(script_id)
    return pool


def resolve_asset_path(middleware: str, asset_type: str, asset_id: str) -> Optional[Path]:
    if asset_type == "scenario":
        path = ROOT / "scenarios" / asset_id / "scenario.yaml"
        return path if path.exists() else None
    if asset_type == "runbook":
        root = ROOT / "domains" / middleware / "runbooks"
        for metadata_file in root.glob("**/metadata.yaml"):
            metadata = load_yaml(metadata_file)
            if str(metadata.get("id") or "") == asset_id:
                return metadata_file.parent
        return None
    if asset_type == "command":
        root = ROOT / "domains" / middleware / "commands"
        for metadata_file in root.glob("**/metadata.yaml"):
            metadata = load_yaml(metadata_file)
            if str(metadata.get("id") or "") == asset_id:
                return metadata_file.parent
        return None
    if asset_type == "skill":
        root = ROOT / "domains" / middleware / "skills"
        for metadata_file in root.glob("**/metadata.yaml"):
            metadata = load_yaml(metadata_file)
            if str(metadata.get("id") or "") == asset_id:
                return metadata_file.parent
        return None
    return None


def matched_asset_refs(middleware: str, skills: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    refs: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for skill in skills:
        metadata = skill["metadata"]
        for asset in extract_required_assets(metadata):
            key = "%s:%s" % (asset["type"], asset["id"])
            if key in seen:
                continue
            seen.add(key)
            path = resolve_asset_path(middleware, asset["type"], asset["id"])
            refs.append(
                {
                    "type": asset["type"],
                    "id": asset["id"],
                    "path": str(path.relative_to(ROOT)) if path else "",
                }
            )
    return refs


SCRIPT_SUCCESS_STATUSES = {"success", "partial"}


def script_collection_statuses(output_dir: Path, collection_report: Dict[str, Any]) -> Dict[str, str]:
    statuses: Dict[str, str] = {}
    script_outputs = output_dir / "script_outputs"
    if script_outputs.is_dir():
        for child in sorted(script_outputs.iterdir()):
            if not child.is_dir():
                continue
            output_path = child / "output.yaml"
            if not output_path.exists():
                continue
            data = load_yaml(output_path)
            script_id = str(data.get("script_id") or child.name)
            statuses[script_id] = str(data.get("status") or "unknown")

    for bucket, default_status in (
        ("successful_items", "success"),
        ("failed_items", "failed"),
        ("blank_items", "blank"),
    ):
        for item in collection_report.get(bucket) or []:
            if not isinstance(item, dict):
                continue
            ref = str(item.get("item") or "")
            if ref.startswith("remote-executor/"):
                script_id = ref.split("/", 1)[1]
                statuses.setdefault(script_id, default_status)

    for action in collection_report.get("collection_actions") or []:
        if not isinstance(action, dict):
            continue
        name = str(action.get("name") or "")
        if name.startswith("remote executor run "):
            script_id = name[len("remote executor run ") :].strip()
            if script_id:
                statuses.setdefault(script_id, str(action.get("status") or "unknown"))

    return statuses


def missing_required_scripts(required_scripts: List[str], statuses: Dict[str, str]) -> List[str]:
    missing_or_failed: List[str] = []
    for script_id in required_scripts:
        status = statuses.get(script_id)
        if status is None or status not in SCRIPT_SUCCESS_STATUSES:
            missing_or_failed.append(script_id)
    return missing_or_failed


def extract_skill_workflow(skill_md_path: Path, max_lines: int = 30) -> str:
    if not skill_md_path.exists():
        return ""
    lines: List[str] = []
    in_workflow = False
    for raw in skill_md_path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            in_workflow = line.lower().startswith("## workflow")
            continue
        if in_workflow:
            if line.startswith("## "):
                break
            if line.strip():
                lines.append(line)
            if len(lines) >= max_lines:
                break
    return "\n".join(lines).strip()
