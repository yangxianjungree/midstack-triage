#!/usr/bin/env python3
"""Compatibility facade for the remote executor runtime."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from execution.remote.access import run_ssh, scp_from, scp_to
from execution.remote.runtime_support import (
    DEFAULT_LOCAL_OUTPUT,
    DEFAULT_MANIFEST,
    DEFAULT_PLUGIN_NAME,
    DEFAULT_REMOTE_ROOT,
    DEFAULT_RUNTIME_MAP,
    load_config,
    load_script_entries,
    now_id,
    now_iso,
    remote_path,
    try_load_yaml,
    write_json,
    write_yaml,
)
from execution.remote.context import (
    build_context,
    choose_namespace,
    collect_inventory,
    context_profile_from_inventory,
    default_context_profile,
)
from execution.remote.error_contract import (
    BLOCKED_ERROR_CODES,
    capability_result,
    classify_kubectl_error,
    classify_remote_error as _classify_remote_error,
    classify_ssh_error,
    error_payload,
    status_from_error_code,
)
from execution.remote.executor_preflight import validate_executor_capabilities as validate_preflight_capabilities
from execution.remote.contracts import (
    aggregate_run_status,
    build_executor_request,
    build_executor_result,
    build_remote_workspace,
    build_run_result,
    build_script_result_summary,
    text_tail,
)
from execution.remote.script_runner import (
    finalize_run,
    print_run_pointer,
    print_script_results,
    run_script as _run_script,
)
from execution.remote.script_capabilities import (
    SCRIPT_IDS_REQUIRING_MONGOSH,
    SCRIPT_ID_MONGOS_SHARD_MAP,
    SCRIPT_ID_REPLICASET_STATUS,
    build_required_capabilities,
    classify_pod_exec_error,
    mongos_pod_score,
    pod_label_text,
    pod_name,
    pod_phase,
    pod_tool_probe_script,
    probe_pod_container_shell as probe_script_pod_container_shell,
    probe_pod_tool as probe_script_pod_tool,
    record_pod_tool_probe_summary,
    remote_kubectl_get_pods as script_remote_kubectl_get_pods,
    replicaset_pod_score,
    resolve_mongos_target_pod,
    resolve_replicaset_target_pods,
    shell_candidates,
    validate_script_capabilities as validate_script_runtime_capabilities,
)
from execution.remote.script_output_contract import (
    SCRIPT_OUTPUT_ALLOWED_STATUSES,
    SCRIPT_OUTPUT_REQUIRED_FIELDS,
    validate_script_output_contract as validate_output_contract,
)
from execution.remote.transport import FunctionRemoteTransport, RemoteTransport


def classify_remote_error(detail: str, default_code: str) -> Dict[str, str]:
    return _classify_remote_error(detail, default_code)


def validate_script_output_contract(output_path: Path, expected_script_id: str):
    return validate_output_contract(output_path, expected_script_id, load_config_fn=load_config)


def default_remote_transport() -> RemoteTransport:
    return FunctionRemoteTransport(run_ssh, scp_to, scp_from)


def remote_kubectl_get_pods(access: Dict[str, Any], namespace: str, transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return script_remote_kubectl_get_pods(access, namespace, run_ssh_fn=transport.run)


def probe_pod_tool(access: Dict[str, Any], namespace: str, pod: str, candidates: List[str], transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return probe_script_pod_tool(access, namespace, pod, candidates, run_ssh_fn=transport.run)


def probe_pod_container_shell(
    access: Dict[str, Any],
    namespace: str,
    pod_item: Dict[str, Any],
    mongo_exec: Dict[str, Any],
    transport: RemoteTransport | None = None,
):
    transport = transport or default_remote_transport()
    return probe_script_pod_container_shell(access, namespace, pod_item, mongo_exec, run_ssh_fn=transport.run)


def validate_script_capabilities(
    access: Dict[str, Any],
    namespace: str,
    script_id: str,
    context: Dict[str, Any],
    inherited_checks: List[Dict[str, str]],
    transport: RemoteTransport | None = None,
):
    transport = transport or default_remote_transport()
    return validate_script_runtime_capabilities(
        access,
        namespace,
        script_id,
        context,
        inherited_checks,
        run_ssh_fn=transport.run,
    )


def validate_executor_capabilities(access: Dict[str, Any], transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return validate_preflight_capabilities(access, run_ssh_fn=transport.run, which_fn=shutil.which)


def run_script(
    access: Dict[str, Any],
    incident_id: str,
    entry: Dict[str, Any],
    namespace: str,
    local_dir: Path,
    remote_root: str,
    script_ids: List[str],
    context_profile: Dict[str, Any],
    plugin_name: str,
    capability_checks: List[Dict[str, str]],
    *,
    transport: RemoteTransport | None = None,
) -> Dict[str, Any]:
    transport = transport or default_remote_transport()
    return _run_script(
        access,
        incident_id,
        entry,
        namespace,
        local_dir,
        remote_root,
        script_ids,
        context_profile,
        plugin_name,
        capability_checks,
        transport=transport,
    )


def parse_args(argv: List[str] | None = None):
    from execution.remote.cli import parse_args as cli_parse_args

    return cli_parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    from execution.remote.cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
