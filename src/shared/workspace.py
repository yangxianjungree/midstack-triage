"""Workspace and file-contract helpers shared by Midstack runtime entrypoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def adapter_output(command: str, incident_id: str, middleware: str, status: str, summary: str, output_dir: Path) -> Dict[str, Any]:
    return {
        "plugin_name": "midstack-triage-local",
        "command": command,
        "incident_id": incident_id,
        "middleware": middleware,
        "status": status,
        "summary": summary,
        "user_message": summary,
        "record_refs": [
            {
                "name": "incident_dir",
                "path": str(output_dir),
                "description": "local incident directory",
            }
        ],
        "next_actions": [],
        "blocking_items": [],
        "warnings": [],
        "generated_at": now_iso(),
    }


def add_record_ref_if_exists(output: Dict[str, Any], output_dir: Path, name: str, filename: str, description: str) -> None:
    path = output_dir / filename
    if path.exists():
        output["record_refs"].append({"name": name, "path": str(path), "description": description})


def workspace_root() -> Path:
    value = os.environ.get("MIDSTACK_TRIAGE_WORKSPACE", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return ROOT


def path_from_arg(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else workspace_root() / path


def resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    workspace_path = workspace_root() / path
    if workspace_path.exists():
        return workspace_path
    return ROOT / path


def current_incident_marker(output_root: Path) -> Path:
    return output_root / ".current-incident"


def write_current_incident(output_root: Path, incident_dir: Path) -> None:
    marker = current_incident_marker(output_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(incident_dir) + "\n", encoding="utf-8")


def read_current_incident(output_root: Path) -> Path:
    marker = current_incident_marker(output_root)
    if not marker.exists():
        raise FileNotFoundError("current incident marker does not exist: %s" % marker)
    value = marker.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("current incident marker is empty: %s" % marker)
    return resolve_path(value)


def load_incident_meta(incident_dir: Path) -> Dict[str, Any]:
    meta_file = incident_dir / "meta.yaml"
    if not meta_file.exists():
        return {}
    return load_yaml(meta_file)


def update_incident_meta(incident_dir: Path, updates: Dict[str, Any]) -> None:
    meta_file = incident_dir / "meta.yaml"
    if not meta_file.exists():
        return
    meta = load_yaml(meta_file)
    meta.update(updates)
    meta["updated_at"] = now_iso()
    write_yaml(meta_file, meta)


def write_blocked_output(
    command: str,
    incident_id: str,
    middleware: str,
    output_dir: Path,
    summary: str,
    blocking_items: List[Dict[str, Any]],
    next_actions: List[str],
    output_filename: str = "adapter-output.yaml",
) -> int:
    output = adapter_output(command, incident_id, middleware, "blocked", summary, output_dir)
    output["blocking_items"] = blocking_items
    output["next_actions"] = next_actions
    write_yaml(output_dir / output_filename, output)
    print(str(output_dir))
    return 0


def copy_if_exists(source_dir: Path, output_dir: Path, filename: str) -> None:
    source = source_dir / filename
    if source.exists():
        target = output_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

