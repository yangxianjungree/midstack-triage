"""Directed recollection execution for Phase 3."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .recollection import directed_recollection_script_ids
from .remote_collection import merge_remote_run_outputs, run_local_collection, run_remote_collection


def run_directed_recollection_if_needed(args, output_dir: Path, skill_pool: Optional[set[str]] = None) -> bool:
    if args.remote_config:
        runner = run_remote_collection
    elif getattr(args, "local_config", ""):
        runner = run_local_collection
    else:
        return False
    script_ids = directed_recollection_script_ids(output_dir, skill_pool=skill_pool)
    if not script_ids:
        return False
    trace_dir = output_dir / "directed-recollection"
    remote_run_dir = runner(args, trace_dir, script_ids)
    merge_remote_run_outputs(remote_run_dir, output_dir)
    return True
