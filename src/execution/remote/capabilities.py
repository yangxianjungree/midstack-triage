"""Compatibility exports for remote capability helpers."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Callable, Dict, List, Tuple

from execution.remote.error_contract import (
    BLOCKED_ERROR_CODES,
    capability_result,
    classify_kubectl_error,
    classify_remote_error,
    classify_ssh_error,
    error_payload,
    status_from_error_code,
)
from execution.remote.script_output_contract import (
    SCRIPT_OUTPUT_ALLOWED_STATUSES,
    SCRIPT_OUTPUT_REQUIRED_FIELDS,
    validate_script_output_contract,
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
    probe_pod_container_shell,
    probe_pod_tool,
    record_pod_tool_probe_summary,
    remote_kubectl_get_pods,
    replicaset_pod_score,
    resolve_mongos_target_pod,
    resolve_replicaset_target_pods,
    shell_candidates,
    validate_script_capabilities,
)

RunSshFn = Callable[[Dict[str, Any], str, int], subprocess.CompletedProcess]


def validate_executor_capabilities(
    access: Dict[str, Any],
    *,
    run_ssh_fn: RunSshFn,
    which_fn: Callable[[str], str | None] = shutil.which,
) -> Tuple[bool, List[Dict[str, str]], Dict[str, str]]:
    from execution.remote.executor_preflight import validate_executor_capabilities as validate_preflight

    return validate_preflight(access, run_ssh_fn=run_ssh_fn, which_fn=which_fn)
