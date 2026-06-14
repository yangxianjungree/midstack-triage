"""Remote access helpers for the execution plane."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from typing import Any, Dict, List, Tuple


REMOTE_COMMAND_TIMEOUT_EXIT = 124
SSH_OPTIONS = [
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
]


def ssh_command(access: Dict[str, Any], remote_command: str) -> List[str]:
    return [
        "sshpass",
        "-e",
        "ssh",
        *SSH_OPTIONS,
        "-p",
        str(access.get("port", 22)),
        "%s@%s" % (access["username"], access["primary_ip"]),
        "bash -lc %s" % __import__("json").dumps(remote_command),
    ]


def ssh_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target = "%s@%s" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "ssh",
        *SSH_OPTIONS,
        "-p",
        str(access.get("port", 22)),
        target,
    ]
    return base, env


def scp_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str], str]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target_prefix = "%s@%s:" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "scp",
        "-O",
        *SSH_OPTIONS,
        "-P",
        str(access.get("port", 22)),
    ]
    return base, env, target_prefix


def run_process(command: List[str], env: Dict[str, str], timeout: int) -> subprocess.CompletedProcess:
    proc = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        stdout, stderr = proc.communicate()
        message = "command timed out after %ss: %s" % (timeout, " ".join(command[:4]))
        return subprocess.CompletedProcess(command, REMOTE_COMMAND_TIMEOUT_EXIT, stdout or "", ((stderr or "") + "\n" + message).strip())


def run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> subprocess.CompletedProcess:
    import shlex

    base, env = ssh_base(access)
    return run_process(base + ["bash -lc %s" % shlex.quote(remote_script)], env, timeout)


def scp_to(access: Dict[str, Any], local_path, remote_path: str) -> None:
    base, env, target_prefix = scp_base(access)
    proc = run_process(base + [str(local_path), target_prefix + remote_path], env, 60)
    if proc.returncode != 0:
        raise RuntimeError("scp_to failed for %s: %s" % (local_path, proc.stderr.strip()))


def scp_from(access: Dict[str, Any], remote_path: str, local_path, recursive: bool = False) -> None:
    base, env, target_prefix = scp_base(access)
    cmd = base[:]
    if recursive:
        cmd.append("-r")
    proc = run_process(cmd + [target_prefix + remote_path, str(local_path)], env, 60)
    if proc.returncode != 0:
        raise RuntimeError("scp_from failed for %s: %s" % (remote_path, proc.stderr.strip()))


def run_env_check(access: Dict[str, Any], remote_command: str) -> Dict[str, Any]:
    if not shutil.which("sshpass"):
        return {"status": "failed", "stdout": "", "stderr": "sshpass is not installed", "exit_code": 1}
    proc = run_ssh(access, remote_command, timeout=30)
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
