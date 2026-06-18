"""Shared remote execution error and status contract."""

from __future__ import annotations

from typing import Dict

BLOCKED_ERROR_CODES = {
    "missing_sshpass",
    "ssh_auth_failed",
    "ssh_unreachable",
    "kubectl_missing",
    "k8s_context_unavailable",
    "kubectl_exec_unavailable",
    "target_pod_not_found",
    "pod_tool_missing",
}


def error_payload(code: str = "", message: str = "") -> Dict[str, str]:
    return {"code": code, "message": message}


def status_from_error_code(code: str) -> str:
    return "blocked" if code in BLOCKED_ERROR_CODES else "failed"


def capability_result(name: str, status: str, detail: str, error_code: str = "") -> Dict[str, str]:
    item = {"name": name, "status": status, "detail": detail}
    if error_code:
        item["error_code"] = error_code
    return item


def classify_ssh_error(stderr: str) -> str:
    text = stderr.lower()
    if "permission denied" in text or "authentication failed" in text:
        return "ssh_auth_failed"
    if (
        "timed out" in text
        or "no route to host" in text
        or "connection refused" in text
        or "could not resolve hostname" in text
    ):
        return "ssh_unreachable"
    return "ssh_unreachable"


def classify_kubectl_error(stderr: str) -> str:
    text = stderr.lower()
    if "command not found" in text and "kubectl" in text:
        return "kubectl_missing"
    if "the connection to the server" in text or "no configuration has been provided" in text or "context deadline exceeded" in text:
        return "k8s_context_unavailable"
    return "k8s_context_unavailable"


def classify_remote_error(detail: str, default_code: str) -> Dict[str, str]:
    message = detail.strip() or default_code
    lowered = message.lower()
    if any(token in lowered for token in ("permission denied", "authentication failed")):
        return error_payload("ssh_auth_failed", message)
    if any(token in lowered for token in ("timed out", "no route to host", "connection refused", "could not resolve hostname", "lost connection")):
        return error_payload("ssh_unreachable", message)
    if "kubectl" in lowered or "the connection to the server" in lowered or "no configuration has been provided" in lowered:
        return error_payload(classify_kubectl_error(message), message)
    return error_payload(default_code, message)
