"""Batch-level remote executor preflight checks."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable, Dict, List, Tuple

from execution.remote.error_contract import capability_result, classify_kubectl_error, classify_ssh_error

RunSshFn = Callable[[Dict[str, Any], str, int], subprocess.CompletedProcess]


def validate_executor_capabilities(
    access: Dict[str, Any],
    *,
    run_ssh_fn: RunSshFn,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> Tuple[bool, List[Dict[str, str]], Dict[str, str]]:
    checks: List[Dict[str, str]] = []
    is_local = access.get("execution_mode") == "local"
    if not is_local and not which_fn("sshpass"):
        return False, [capability_result("sshpass", "blocked", "sshpass is not installed locally", "missing_sshpass")], {
            "code": "missing_sshpass",
            "message": "sshpass is not installed locally",
        }

    ssh_proc = run_ssh_fn(access, "echo ok", 20)
    if ssh_proc.returncode != 0:
        code = classify_ssh_error(ssh_proc.stderr)
        check_name = "local_shell" if is_local else "ssh"
        detail = ssh_proc.stderr.strip() or "%s check failed" % check_name
        checks.append(capability_result(check_name, "blocked", detail, code))
        return False, checks, {"code": code, "message": detail}
    if is_local:
        checks.append(capability_result("local_shell", "success", "local shell echo ok succeeded"))
    else:
        checks.append(capability_result("ssh", "success", "ssh echo ok succeeded"))

    kubectl_proc = run_ssh_fn(access, "kubectl version --client=true >/dev/null", 20)
    if kubectl_proc.returncode != 0:
        code = classify_kubectl_error(kubectl_proc.stderr)
        checks.append(capability_result("kubectl", "blocked", kubectl_proc.stderr.strip() or "kubectl client check failed", code))
        return False, checks, {"code": code, "message": kubectl_proc.stderr.strip() or "kubectl client check failed"}
    checks.append(capability_result("kubectl", "success", "kubectl client is available"))

    cluster_proc = run_ssh_fn(access, "kubectl get nodes -o name >/dev/null", 20)
    if cluster_proc.returncode != 0:
        code = classify_kubectl_error(cluster_proc.stderr)
        checks.append(capability_result("k8s_context", "blocked", cluster_proc.stderr.strip() or "kubectl cluster access check failed", code))
        return False, checks, {"code": code, "message": cluster_proc.stderr.strip() or "kubectl cluster access check failed"}
    checks.append(capability_result("k8s_context", "success", "kubectl can access the cluster"))

    exec_proc = run_ssh_fn(access, "kubectl auth can-i create pods/exec -A", 20)
    if exec_proc.returncode != 0:
        checks.append(
            capability_result(
                "kubectl_exec",
                "blocked",
                exec_proc.stderr.strip() or "kubectl exec capability check failed",
                "kubectl_exec_unavailable",
            )
        )
        return False, checks, {
            "code": "kubectl_exec_unavailable",
            "message": exec_proc.stderr.strip() or "kubectl exec capability check failed",
        }
    if exec_proc.stdout.strip().lower() not in ("yes", "true"):
        checks.append(
            capability_result(
                "kubectl_exec",
                "blocked",
                exec_proc.stdout.strip() or "kubectl exec is not permitted",
                "kubectl_exec_unavailable",
            )
        )
        return False, checks, {
            "code": "kubectl_exec_unavailable",
            "message": exec_proc.stdout.strip() or "kubectl exec is not permitted",
        }
    checks.append(capability_result("kubectl_exec", "success", "kubectl exec capability is available"))
    return True, checks, {"code": "", "message": ""}
