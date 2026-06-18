"""Phase 2 kubectl inventory helpers."""

from __future__ import annotations

import json
import subprocess
from typing import Any, Dict

from execution.remote.access import run_env_check
from execution.remote.kubectl import kubectl_scope, run_remote_kubectl_json as _run_remote_kubectl_json


def _run_local_kubectl_json(resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    command = ["kubectl", "get", resource]
    scope = kubectl_scope(namespace, namespaced)
    if scope:
        command.extend(scope.split())
    command.extend(["-o", "json"])
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=30)
    if proc.returncode != 0:
        return {"status": "failed", "resource": resource, "error": {"stdout": proc.stdout, "stderr": proc.stderr, "exit_code": proc.returncode}}
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "failed", "resource": resource, "error": {"message": str(exc), "stdout": proc.stdout[:1000]}}
    return {"status": "passed", "resource": resource, "payload": payload}


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    if access.get("execution_mode") == "local":
        return _run_local_kubectl_json(resource, namespace, namespaced)
    return _run_remote_kubectl_json(access, resource, namespace, namespaced, run_env_check_fn=run_env_check)
