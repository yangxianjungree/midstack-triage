"""Phase 1 startup helpers."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List


def ssh_command(access: Dict[str, Any], remote_command: str) -> List[str]:
    return [
        "sshpass",
        "-e",
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "ServerAliveInterval=5",
        "-o",
        "ServerAliveCountMax=2",
        "-o",
        "PreferredAuthentications=password,keyboard-interactive",
        "-o",
        "PubkeyAuthentication=no",
        "-o",
        "NumberOfPasswordPrompts=1",
        "-p",
        str(access.get("port", 22)),
        "%s@%s" % (access["username"], access["primary_ip"]),
        "bash -lc %s" % __import__("json").dumps(remote_command),
    ]


def run_env_check(access: Dict[str, Any], remote_command: str) -> Dict[str, Any]:
    if not shutil.which("sshpass"):
        return {"status": "failed", "stdout": "", "stderr": "sshpass is not installed"}
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    try:
        proc = subprocess.run(
            ssh_command(access, remote_command),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "stdout": exc.stdout or "",
            "stderr": "remote command timed out after 30s: %s" % remote_command,
            "exit_code": 124,
        }
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "exit_code": proc.returncode,
    }


def validate_remote_environment(access: Dict[str, Any]) -> Dict[str, Any]:
    checks = [
        {"check_id": "ssh", "command": "echo ok"},
        {"check_id": "kubectl-client", "command": "kubectl version --client=true >/dev/null"},
        {"check_id": "kubectl-nodes", "command": "kubectl get nodes -o name >/dev/null"},
    ]
    results = []
    for item in checks:
        result = run_env_check(access, item["command"])
        result["check_id"] = item["check_id"]
        results.append(result)
        if result["status"] != "passed":
            break
    return {"status": "passed" if all(item["status"] == "passed" for item in results) else "failed", "checks": results}
