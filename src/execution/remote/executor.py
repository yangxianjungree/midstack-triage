#!/usr/bin/env python3

import shlex
import shutil
from pathlib import Path
from typing import Any, Dict, List

from execution.remote.access import run_ssh, scp_from, scp_to
from execution.remote import capabilities as remote_capabilities
from execution.remote.context import (
    build_context,
    choose_namespace,
    collect_inventory,
    context_profile_from_inventory,
    default_context_profile,
)
from execution.remote.contracts import (
    aggregate_run_status,
    build_executor_request,
    build_executor_result,
    build_remote_workspace,
    build_run_result,
    build_script_result_summary,
    text_tail,
)
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
from execution.remote.transport import FunctionRemoteTransport, RemoteTransport
BLOCKED_ERROR_CODES = remote_capabilities.BLOCKED_ERROR_CODES
SCRIPT_IDS_REQUIRING_MONGOSH = remote_capabilities.SCRIPT_IDS_REQUIRING_MONGOSH
SCRIPT_ID_MONGOS_SHARD_MAP = remote_capabilities.SCRIPT_ID_MONGOS_SHARD_MAP
SCRIPT_ID_REPLICASET_STATUS = remote_capabilities.SCRIPT_ID_REPLICASET_STATUS
SCRIPT_OUTPUT_REQUIRED_FIELDS = remote_capabilities.SCRIPT_OUTPUT_REQUIRED_FIELDS
SCRIPT_OUTPUT_ALLOWED_STATUSES = remote_capabilities.SCRIPT_OUTPUT_ALLOWED_STATUSES
error_payload = remote_capabilities.error_payload
status_from_error_code = remote_capabilities.status_from_error_code
capability_result = remote_capabilities.capability_result
classify_ssh_error = remote_capabilities.classify_ssh_error
classify_kubectl_error = remote_capabilities.classify_kubectl_error
shell_candidates = remote_capabilities.shell_candidates
build_required_capabilities = remote_capabilities.build_required_capabilities
pod_name = remote_capabilities.pod_name
pod_phase = remote_capabilities.pod_phase
pod_label_text = remote_capabilities.pod_label_text
mongos_pod_score = remote_capabilities.mongos_pod_score
replicaset_pod_score = remote_capabilities.replicaset_pod_score
resolve_mongos_target_pod = remote_capabilities.resolve_mongos_target_pod
resolve_replicaset_target_pods = remote_capabilities.resolve_replicaset_target_pods
classify_pod_exec_error = remote_capabilities.classify_pod_exec_error
pod_tool_probe_script = remote_capabilities.pod_tool_probe_script
record_pod_tool_probe_summary = remote_capabilities.record_pod_tool_probe_summary


def classify_remote_error(detail: str, default_code: str) -> Dict[str, str]:
    return remote_capabilities.classify_remote_error(detail, default_code)


def validate_script_output_contract(output_path: Path, expected_script_id: str):
    return remote_capabilities.validate_script_output_contract(output_path, expected_script_id, load_config_fn=load_config)


def default_remote_transport() -> RemoteTransport:
    return FunctionRemoteTransport(run_ssh, scp_to, scp_from)


def remote_kubectl_get_pods(access: Dict[str, Any], namespace: str, transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return remote_capabilities.remote_kubectl_get_pods(access, namespace, run_ssh_fn=transport.run)


def probe_pod_tool(access: Dict[str, Any], namespace: str, pod: str, candidates: List[str], transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return remote_capabilities.probe_pod_tool(access, namespace, pod, candidates, run_ssh_fn=transport.run)


def probe_pod_container_shell(
    access: Dict[str, Any],
    namespace: str,
    pod_item: Dict[str, Any],
    mongo_exec: Dict[str, Any],
    transport: RemoteTransport | None = None,
):
    transport = transport or default_remote_transport()
    return remote_capabilities.probe_pod_container_shell(access, namespace, pod_item, mongo_exec, run_ssh_fn=transport.run)


def validate_script_capabilities(
    access: Dict[str, Any],
    namespace: str,
    script_id: str,
    context: Dict[str, Any],
    inherited_checks: List[Dict[str, str]],
    transport: RemoteTransport | None = None,
):
    transport = transport or default_remote_transport()
    return remote_capabilities.validate_script_capabilities(
        access,
        namespace,
        script_id,
        context,
        inherited_checks,
        run_ssh_fn=transport.run,
    )


def validate_executor_capabilities(access: Dict[str, Any], transport: RemoteTransport | None = None):
    transport = transport or default_remote_transport()
    return remote_capabilities.validate_executor_capabilities(access, run_ssh_fn=transport.run, which_fn=shutil.which)


def print_run_pointer(incident_id: str, namespace: str, local_dir: Path) -> None:
    print("incident_id=%s" % incident_id)
    print("selected_namespace=%s" % namespace)
    print("local_dir=%s" % local_dir)


def print_script_results(local_dir: Path, script_ids: List[str]) -> None:
    for script_id in script_ids:
        script_dir = local_dir / script_id
        result = try_load_yaml(script_dir / "remote-executor-result.yaml") if (script_dir / "remote-executor-result.yaml").exists() else {}
        output = try_load_yaml(script_dir / "output.yaml") if (script_dir / "output.yaml").exists() else {}
        exit_code = (script_dir / "exit_code.txt").read_text(encoding="utf-8") if (script_dir / "exit_code.txt").exists() else "missing"
        executor_status = str(result.get("status") or "missing")
        if output:
            print(
                "%s: executor=%s exit=%s output_status=%s summary=%s"
                % (script_id, executor_status, exit_code, output.get("status"), output.get("summary"))
            )
        elif result:
            error = result.get("error") or {}
            print(
                "%s: executor=%s exit=%s error=%s"
                % (script_id, executor_status, exit_code, (error.get("message") or "")[:200])
            )
        else:
            print("%s: executor=missing exit=%s" % (script_id, exit_code))


def finalize_run(
    local_dir: Path,
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
    return_code: int,
    script_ids: List[str],
) -> int:
    write_yaml(
        local_dir / "remote-executor-run.yaml",
        build_run_result(incident_id, plugin_name, selected_ip, namespace, started_at, capability_checks, script_results, error, warnings, status),
    )
    print_run_pointer(incident_id, namespace, local_dir)
    if script_results:
        print_script_results(local_dir, script_ids)
    return return_code


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
    script_id = str(entry["script_id"])
    remote_workspace = build_remote_workspace(remote_root, incident_id, script_id, str(entry["runtime_path"]))
    remote_context = remote_workspace["context_file"]
    remote_output = remote_workspace["output_file"]
    remote_artifacts = remote_workspace["artifact_dir"]
    local_script_dir = local_dir / script_id
    local_script_dir.mkdir(parents=True, exist_ok=True)
    request = build_executor_request(access, incident_id, entry, remote_workspace, plugin_name, build_required_capabilities(script_id))
    write_yaml(local_script_dir / "remote-executor-request.yaml", request)
    started_at = now_iso()
    process = {"exit_code": -1, "stdout_tail": "", "stderr_tail": ""}
    retrieved_files: Dict[str, str] = {}
    warnings: List[str] = []
    error = error_payload()
    status = "failed"
    output_valid = False
    script_capability_checks = list(capability_checks)

    try:
        context = build_context(incident_id, script_id, namespace, local_script_dir / "artifacts", remote_root, script_ids, context_profile, access)
        capabilities_ok, context, script_capability_checks, capability_error, capability_warnings = validate_script_capabilities(
            access, namespace, script_id, context, capability_checks, transport=transport
        )
        warnings.extend(capability_warnings)
        if not capabilities_ok:
            error = capability_error
            status = status_from_error_code(error["code"])
        context_path = local_script_dir / "context.yaml"
        write_json(context_path, context)
        if not capabilities_ok:
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)

        mkdir_proc = transport.run(access, "mkdir -p %s %s" % (shlex.quote(remote_workspace["run_root"]), shlex.quote(remote_artifacts)))
        if mkdir_proc.returncode != 0:
            process = {"exit_code": mkdir_proc.returncode, "stdout_tail": text_tail(mkdir_proc.stdout), "stderr_tail": text_tail(mkdir_proc.stderr)}
            error = classify_remote_error(mkdir_proc.stderr or mkdir_proc.stdout, "remote_workspace_unavailable")
            status = status_from_error_code(error["code"])
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)
        try:
            transport.copy_to(access, context_path, remote_context)
        except RuntimeError as exc:
            error = classify_remote_error(str(exc), "remote_workspace_unavailable")
            status = status_from_error_code(error["code"])
            return build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)

        runner = "python3" if str(entry["runtime"]) == "python" else "bash"
        command = (
            "%s %s --context-file %s --output-file %s --artifact-dir %s"
            % (runner, shlex.quote(remote_workspace["script_path"]), shlex.quote(remote_context), shlex.quote(remote_output), shlex.quote(remote_artifacts))
        )
        proc = transport.run(access, command, timeout=120)
        process = {"exit_code": proc.returncode, "stdout_tail": text_tail(proc.stdout), "stderr_tail": text_tail(proc.stderr)}
        (local_script_dir / "remote.stdout.txt").write_text(proc.stdout, encoding="utf-8")
        (local_script_dir / "remote.stderr.txt").write_text(proc.stderr, encoding="utf-8")
        (local_script_dir / "exit_code.txt").write_text(str(proc.returncode), encoding="utf-8")

        output_retrieved = False
        try:
            transport.copy_from(access, remote_output, local_script_dir / "output.yaml")
            output_retrieved = True
            retrieved_files["output_file"] = str(local_script_dir / "output.yaml")
            output_valid, _, contract_error = validate_script_output_contract(local_script_dir / "output.yaml", script_id)
            if not output_valid:
                error = error_payload("script_contract_failed", contract_error)
        except RuntimeError as exc:
            error = error_payload("output_retrieval_failed", str(exc))

        artifact_dest = local_script_dir / "artifacts"
        if artifact_dest.exists():
            shutil.rmtree(artifact_dest)
        try:
            transport.copy_from(access, remote_artifacts, artifact_dest, recursive=True)
            retrieved_files["artifact_dir"] = str(artifact_dest)
        except RuntimeError as exc:
            warnings.append(str(exc))
            (local_script_dir / "artifact_retrieval_error.txt").write_text(str(exc), encoding="utf-8")

        if proc.returncode == 0 and output_valid:
            status = "partial" if warnings else "success"
            error = error_payload()
        elif proc.returncode == 0:
            status = "failed"
            if not error["code"]:
                error = error_payload("script_contract_failed", "script did not produce a valid retrievable output.yaml")
        else:
            status = "failed"
            if output_valid:
                error = error_payload(
                    "script_contract_failed",
                    "script returned non-zero exit code %s after writing output.yaml" % proc.returncode,
                )
            elif not error["code"]:
                error = error_payload("script_runtime_failed", proc.stderr.strip() or "script exited with code %s" % proc.returncode)
    finally:
        result = build_executor_result(request, status, started_at, script_capability_checks, process, retrieved_files, error, warnings)
        write_yaml(local_script_dir / "remote-executor-result.yaml", result)
    return result


def parse_args(argv: List[str] | None = None):
    from execution.remote.cli import parse_args as cli_parse_args

    return cli_parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    from execution.remote.cli import main as cli_main

    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
