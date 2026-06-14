"""Runtime support helpers for remote execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_LOCAL_OUTPUT = ROOT / ".local" / "remote-runs"
DEFAULT_REMOTE_ROOT = "/tmp/midstack-triage"
DEFAULT_RUNTIME_MAP = ROOT / "interfaces" / "plugin" / "script-runtime-map.example.yaml"
DEFAULT_MANIFEST = ROOT / "domains" / "mongodb" / "scripts" / "manifest.yaml"
DEFAULT_PLUGIN_NAME = "midstack-triage"


def now_id() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def try_load_yaml(path: Path) -> Dict[str, Any]:
    try:
        data = load_config(path)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_script_entries(manifest_path: Path, runtime_map_path: Path, selected_script_ids: List[str] | None = None) -> List[Dict[str, Any]]:
    manifest = load_config(manifest_path)
    runtime_map = load_config(runtime_map_path)
    manifest_root = manifest_path.parent
    source_by_id = {}
    selected = set(selected_script_ids or [])
    for item in manifest.get("scripts") or []:
        if isinstance(item, dict) and item.get("default_packaged") is True:
            source_by_id[str(item.get("script_id") or "")] = item

    entries = []
    for item in runtime_map.get("scripts") or []:
        if not isinstance(item, dict):
            continue
        script_id = str(item.get("script_id") or "")
        manifest_item = source_by_id.get(script_id)
        if not manifest_item:
            raise RuntimeError("runtime map script is missing from default_packaged manifest: %s" % script_id)
        if selected:
            if script_id not in selected:
                continue
        elif manifest_item.get("mvp") is not True:
            continue
        source = str(manifest_item.get("source") or "")
        entry = {
            "script_id": script_id,
            "source_path": manifest_root / source,
            "runtime_path": str(item.get("runtime_path") or ""),
            "runtime": str(item.get("runtime") or manifest_item.get("runtime") or ""),
            "readonly": bool(item.get("readonly")),
        }
        if not entry["source_path"].exists():
            raise RuntimeError("script source does not exist for %s: %s" % (script_id, entry["source_path"]))
        entries.append(entry)
    if not entries:
        if selected:
            raise RuntimeError("selected script ids are not runtime-map-backed default_packaged scripts: %s" % sorted(selected))
        raise RuntimeError("runtime map contains no MVP scripts: %s" % runtime_map_path)
    return entries


def remote_path(remote_root: str, runtime_path: str) -> str:
    return "%s/%s" % (remote_root.rstrip("/"), runtime_path.lstrip("/"))
