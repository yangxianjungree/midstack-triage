"""Shared domain asset lookup helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from shared.io import load_yaml_object
from shared.workspace import runtime_root


ASSET_ROOTS = (
    ("runbook", "runbooks"),
    ("command", "commands"),
    ("skill", "skills"),
)
MIDDLEWARE_DISPLAY_NAMES = {
    "mongodb": "MongoDB",
    "pulsar": "Pulsar",
}


def knowledge_candidates_for_scenario(middleware: str, scenario: str, root: Path | None = None) -> List[Dict[str, str]]:
    if scenario in ("", "unknown", "baseline"):
        return []

    runtime = root or runtime_root()
    display_name = MIDDLEWARE_DISPLAY_NAMES.get(middleware, middleware)
    candidates: List[Dict[str, str]] = []
    for candidate_type, asset_dir in ASSET_ROOTS:
        domain_root = runtime / "domains" / middleware / asset_dir
        if not domain_root.exists():
            continue
        for metadata_file in sorted(domain_root.glob("**/metadata.yaml")):
            metadata = load_yaml_object(metadata_file)
            asset_middleware = metadata.get("middleware")
            if asset_middleware and str(asset_middleware) != middleware:
                continue
            asset_scenario = metadata.get("scenario") or metadata.get("primary_scenario")
            if asset_scenario != scenario:
                continue
            candidates.append(
                {
                    "candidate_type": candidate_type,
                    "title": str(metadata.get("title") or metadata_file.parent.name),
                    "asset_path": str(metadata_file.parent.relative_to(runtime)),
                    "reason": "Existing %s %s asset matches scenario %s." % (display_name, candidate_type, scenario),
                }
            )
    return candidates
