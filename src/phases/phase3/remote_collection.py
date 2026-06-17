"""Phase 3 control-plane wrapper for remote evidence collection."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, List

from shared.workspace import load_yaml, now_iso, resolve_path, write_yaml
from .remote_run import (
    load_remote_executor_run_result,
    merge_remote_executor_run_result,
    merge_remote_script_outputs,
    script_run_dirs,
)
from .report_gaps import drop_closed_evidence_gaps, normalize_collection_report_gaps


def run_remote_collection(args, output_dir: Path, script_ids: List[str] = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    src_dir = str(Path(__file__).resolve().parents[2])
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_dir if not pythonpath else "%s%s%s" % (src_dir, os.pathsep, pythonpath)
    command = [
        sys.executable,
        "-m",
        "execution.remote.executor",
        "--config",
        str(resolve_path(args.remote_config)),
        "--output-dir",
        str(resolve_path(args.remote_output_dir)),
    ]
    if getattr(args, "object_inventory", ""):
        command.extend(["--inventory-file", str(resolve_path(args.object_inventory))])
    if args.remote_namespace:
        command.extend(["--namespace", args.remote_namespace])
    for script_id in script_ids or []:
        command.extend(["--script-id", script_id])
    try:
        proc = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=900,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = ((exc.stderr or "") + "\nremote executor timed out after 900s").strip()
        returncode = 124
    (output_dir / "remote-executor.stdout.txt").write_text(stdout, encoding="utf-8")
    (output_dir / "remote-executor.stderr.txt").write_text(stderr, encoding="utf-8")
    local_dir = None
    for line in stdout.splitlines():
        if line.startswith("local_dir="):
            local_dir = resolve_path(line.split("=", 1)[1].strip())
            break
    if returncode != 0:
        if local_dir is not None and local_dir.exists():
            return local_dir
        raise RuntimeError("remote executor failed: %s" % stderr.strip())
    if local_dir is not None:
        return local_dir
    raise RuntimeError("remote executor output did not include local_dir")


def merge_remote_run_outputs(remote_run_dir: Path, output_dir: Path) -> None:
    structured_record = load_yaml(output_dir / "structured_record.yaml")
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml")
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    run_result = load_remote_executor_run_result(remote_run_dir)
    item_dirs = script_run_dirs(remote_run_dir)
    merge_remote_executor_run_result(collection_report, run_result, bool(item_dirs))
    merge_remote_script_outputs(remote_run_dir, output_dir, structured_record, signal_bundle, collection_report, item_dirs)
    if (remote_run_dir / "remote-executor-run.yaml").exists():
        shutil.copy2(remote_run_dir / "remote-executor-run.yaml", output_dir / "directed-recollection-run.yaml")
    drop_closed_evidence_gaps(structured_record, collection_report)
    normalize_collection_report_gaps(collection_report)
    timestamp = now_iso()
    structured_record["updated_at"] = timestamp
    signal_bundle["updated_at"] = timestamp
    collection_report["updated_at"] = timestamp
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)
