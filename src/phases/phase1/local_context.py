"""Lightweight local Kubernetes context probing for Phase 1 intake."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable, Dict


RunFn = Callable[..., subprocess.CompletedProcess]
WhichFn = Callable[[str], str | None]


def _run_kubectl(run_fn: RunFn, args: list[str]) -> subprocess.CompletedProcess:
    return run_fn(["kubectl"] + args, timeout=5, text=True, capture_output=True)


def probe_local_context(
    *,
    which_fn: WhichFn = shutil.which,
    run_fn: RunFn = subprocess.run,
) -> Dict[str, str]:
    if not which_fn("kubectl"):
        return {
            "status": "unavailable",
            "reason": "kubectl_not_found",
            "current_context": "",
        }

    context_proc = _run_kubectl(run_fn, ["config", "current-context"])
    current_context = context_proc.stdout.strip() if context_proc.returncode == 0 else ""
    if context_proc.returncode != 0:
        return {
            "status": "unavailable",
            "reason": "current_context_failed",
            "current_context": current_context,
        }

    cluster_proc = _run_kubectl(run_fn, ["cluster-info"])
    if cluster_proc.returncode != 0:
        return {
            "status": "unreachable",
            "reason": "cluster_info_failed",
            "current_context": current_context,
        }

    return {
        "status": "available",
        "reason": "",
        "current_context": current_context,
    }
