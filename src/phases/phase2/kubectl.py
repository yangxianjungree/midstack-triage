"""Remote kubectl helpers for Phase 2 inventory."""

from __future__ import annotations

import json
from typing import Any, Dict

from execution.remote.access import run_env_check


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    if namespaced:
        scope = "-n %s" % namespace if namespace else "-A"
    else:
        scope = ""
    result = run_env_check(access, "kubectl get %s %s -o json" % (resource, scope))
    if result["status"] != "passed":
        return {"status": "failed", "resource": resource, "error": result}
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "failed", "resource": resource, "error": {"message": str(exc), "stdout": result.get("stdout", "")[:1000]}}
    return {"status": "passed", "resource": resource, "payload": payload}
