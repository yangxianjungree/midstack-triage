#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Any, Dict, List, Set


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT, load_yaml  # noqa: E402


def load_metadata_index(domain: str, asset_kind: str) -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    root = ROOT / "domains" / domain / asset_kind
    if not root.exists():
        return index
    for path in sorted(root.glob("**/metadata.yaml")):
        data = load_yaml(path)
        asset_id = data.get("id")
        if isinstance(asset_id, str) and asset_id:
            index[asset_id] = path
    return index


def load_scenario_ids() -> Set[str]:
    return {path.parent.name for path in (ROOT / "scenarios").glob("*/scenario.yaml")}


def validate_required_asset_ref(
    ref: Any,
    context: str,
    manifest_by_id: Dict[str, Dict[str, Any]],
    runbooks: Dict[str, Path],
    commands: Dict[str, Path],
    skills: Dict[str, Path],
    scenarios: Set[str],
    errors: List[str],
) -> None:
    if isinstance(ref, str):
        ref_path = ROOT / ref
        if not ref_path.exists() or not ref_path.is_dir():
            errors.append("%s legacy required_assets path does not exist: %s" % (context, ref))
        return

    if not isinstance(ref, dict):
        errors.append("%s required_assets entry must be a string or object" % context)
        return

    ref_type = ref.get("type")
    ref_id = ref.get("id")
    if not isinstance(ref_type, str) or not isinstance(ref_id, str) or not ref_id:
        errors.append("%s structured required_assets must include type and id" % context)
        return

    if ref_type == "scenario":
        if ref_id not in scenarios:
            errors.append("%s scenario id does not exist: %s" % (context, ref_id))
    elif ref_type == "runbook":
        if ref_id not in runbooks:
            errors.append("%s runbook id does not exist: %s" % (context, ref_id))
    elif ref_type == "command":
        if ref_id not in commands:
            errors.append("%s command id does not exist: %s" % (context, ref_id))
    elif ref_type == "skill":
        if ref_id not in skills:
            errors.append("%s skill id does not exist: %s" % (context, ref_id))
    elif ref_type == "script":
        if ref_id not in manifest_by_id:
            errors.append("%s script_id does not exist in manifest: %s" % (context, ref_id))
    else:
        errors.append("%s unsupported required_assets type: %s" % (context, ref_type))
