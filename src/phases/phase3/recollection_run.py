"""Directed recollection execution for Phase 3."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from execution.modes import resolve_execution_mode
from .recollection import directed_recollection_script_ids
from .remote_collection import merge_remote_run_outputs, run_local_collection, run_remote_collection


def _select_recollection_runner(args):
    mode = resolve_execution_mode(getattr(args, "execution_mode", None))
    if mode.name == "remote" and getattr(args, "remote_config", ""):
        return run_remote_collection
    if mode.name == "local" and getattr(args, "local_config", ""):
        return run_local_collection
    return None


def run_directed_recollection_if_needed(args, output_dir: Path, skill_pool: Optional[set[str]] = None) -> bool:
    runner = _select_recollection_runner(args)
    if runner is None:
        return False
    script_ids = directed_recollection_script_ids(output_dir, skill_pool=skill_pool)
    if not script_ids:
        return False
    trace_dir = output_dir / "directed-recollection"
    remote_run_dir = runner(args, trace_dir, script_ids)
    merge_remote_run_outputs(remote_run_dir, output_dir)
    return True
