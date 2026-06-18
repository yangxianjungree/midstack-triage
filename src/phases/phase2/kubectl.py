"""Phase 2 compatibility wrapper for remote kubectl inventory helpers."""

from __future__ import annotations

from typing import Any, Dict

from execution.remote.access import run_env_check
from execution.remote.kubectl import run_remote_kubectl_json as _run_remote_kubectl_json


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    return _run_remote_kubectl_json(access, resource, namespace, namespaced, run_env_check_fn=run_env_check)
