"""Request/result contracts for remote execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from execution.remote.runtime_support import now_iso, remote_path


def text_tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def build_remote_workspace(remote_root: str, incident_id: str, script_id: str, runtime_path: str) -> Dict[str, str]:
    run_root = "%s/runs/%s/%s" % (remote_root.rstrip("/"), incident_id, script_id)
    script_path = remote_path(remote_root, runtime_path)
    return {
        "plugin_root": remote_root.rstrip("/"),
        "script_root": "%s/assets/scripts" % remote_root.rstrip("/"),
        "run_root": run_root,
        "script_path": script_path,
        "context_file": "%s/context.yaml" % run_root,
        "output_file": "%s/output.yaml" % run_root,
        "artifact_dir": "%s/artifacts" % run_root,
    }


def build_executor_request(
    access: Dict[str, Any],
    incident_id: str,
    entry: Dict[str, Any],
    remote_workspace: Dict[str, str],
    plugin_name: str,
    required_capabilities: Dict[str, Any],
) -> Dict[str, Any]:
    script_id = str(entry["script_id"])
    return {
        "executor_id": "remote-executor-%s-%s" % (incident_id, script_id),
        "incident_id": incident_id,
        "script_id": script_id,
        "middleware": "mongodb",
        "plugin_name": plugin_name,
        "access": access,
        "script": {
            "runtime_path": entry["runtime_path"],
            "runtime": entry["runtime"],
            "readonly": entry["readonly"],
            "arguments": {
                "context_file": "context.yaml",
                "output_file": "output.yaml",
                "artifact_dir": "artifacts",
            },
        },
        "remote_workspace": remote_workspace,
        "required_capabilities": required_capabilities,
        "execution": {
            "timeout_seconds": 120,
            "retrieve_output_file": True,
            "retrieve_artifact_dir": True,
        },
    }


def build_executor_result(
    request: Dict[str, Any],
    status: str,
    started_at: str,
    capability_checks: List[Dict[str, str]],
    process: Dict[str, Any],
    retrieved_files: Dict[str, str],
    error: Dict[str, str],
    warnings: List[str],
) -> Dict[str, Any]:
    return {
        "executor_id": request["executor_id"],
        "incident_id": request["incident_id"],
        "script_id": request["script_id"],
        "plugin_name": request["plugin_name"],
        "status": status,
        "selected_ip": str((request.get("access") or {}).get("primary_ip") or ""),
        "started_at": started_at,
        "finished_at": now_iso(),
        "capability_checks": capability_checks,
        "remote_paths": request["remote_workspace"],
        "retrieved_files": retrieved_files,
        "process": process,
        "error": error,
        "warnings": warnings,
    }


def build_script_result_summary(result: Dict[str, Any], output: Dict[str, Any]) -> Dict[str, str]:
    error = result.get("error") or {}
    summary = {
        "script_id": str(result.get("script_id") or ""),
        "status": str(result.get("status") or ""),
        "error_code": str(error.get("code") or ""),
        "error_message": str(error.get("message") or ""),
    }
    if output:
        summary["output_status"] = str(output.get("status") or "")
        summary["output_summary"] = str(output.get("summary") or "")
    return summary


def build_run_result(
    incident_id: str,
    plugin_name: str,
    selected_ip: str,
    namespace: str,
    started_at: str,
    capability_checks: List[Dict[str, str]],
    script_results: List[Dict[str, str]],
    error: Dict[str, str],
    warnings: List[str],
    status: str,
) -> Dict[str, Any]:
    return {
        "incident_id": incident_id,
        "plugin_name": plugin_name,
        "status": status,
        "selected_ip": selected_ip,
        "namespace": namespace,
        "started_at": started_at,
        "finished_at": now_iso(),
        "capability_checks": capability_checks,
        "script_results": script_results,
        "error": error,
        "warnings": warnings,
    }


def aggregate_run_status(script_results: List[Dict[str, str]]) -> str:
    if not script_results:
        return "failed"
    statuses = [str(item.get("status") or "") for item in script_results]
    if statuses and all(item == "success" for item in statuses):
        return "success"
    return "partial"
