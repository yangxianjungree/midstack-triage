"""Remote kubectl helpers for execution-plane inventory collection."""

from __future__ import annotations

import json
from typing import Any, Callable, Dict

from execution.remote.access import run_env_check

RunEnvCheckFn = Callable[[Dict[str, Any], str], Dict[str, Any]]


def kubectl_scope(namespace: str, namespaced: bool = True) -> str:
    if not namespaced:
        return ""
    return "-n %s" % namespace if namespace else "-A"


def run_remote_kubectl_json(
    access: Dict[str, Any],
    resource: str,
    namespace: str,
    namespaced: bool = True,
    *,
    run_env_check_fn: RunEnvCheckFn = run_env_check,
) -> Dict[str, Any]:
    result = run_env_check_fn(access, "kubectl get %s %s -o json" % (resource, kubectl_scope(namespace, namespaced)))
    if result["status"] != "passed":
        return {"status": "failed", "resource": resource, "error": result}
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "failed", "resource": resource, "error": {"message": str(exc), "stdout": result.get("stdout", "")[:1000]}}
    return {"status": "passed", "resource": resource, "payload": payload}
