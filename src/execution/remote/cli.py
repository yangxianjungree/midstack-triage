"""Command-line orchestration for the remote executor."""

from __future__ import annotations

import argparse
import posixpath
import shlex
from pathlib import Path
from typing import Any, Dict, List

from execution.remote.context import (
    choose_namespace,
    collect_inventory,
    context_profile_from_inventory,
)
from execution.remote.contracts import (
    aggregate_run_status,
    build_script_result_summary,
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
    write_yaml,
)
from execution.remote.script_runner import (
    classify_remote_error,
    default_remote_transport,
    error_payload,
    finalize_run,
    run_script,
    status_from_error_code,
    validate_executor_capabilities,
)


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MongoDB MVP scripts against a remote Kubernetes environment.")
    parser.add_argument("--config", required=True, help="Path to ignored local environment config YAML.")
    parser.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT), help="Local directory for remote collection run outputs.")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT, help="Remote plugin root under /tmp.")
    parser.add_argument("--plugin-name", default=DEFAULT_PLUGIN_NAME, help="Plugin name used for remote executor workspace layout.")
    parser.add_argument("--runtime-map", default=str(DEFAULT_RUNTIME_MAP), help="Runtime map used to resolve packaged script paths.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Manifest used to resolve source script paths.")
    parser.add_argument("--script-id", action="append", default=[], help="Run only the selected script id. May be repeated.")
    parser.add_argument("--namespace", default="", help="Explicit namespace. If omitted, a known MongoDB namespace is selected.")
    parser.add_argument("--namespace-candidates", default="mongo,psmdb-test,mongodb,default", help="Comma-separated namespace candidates.")
    parser.add_argument("--inventory-file", default="", help="Optional object-inventory.yaml from /start for topology and target hints.")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = now_iso()
    incident_id = "mongodb-remote-run-%s" % now_id()
    local_dir = Path(args.output_dir) / incident_id
    local_dir.mkdir(parents=True, exist_ok=True)
    namespace = str(args.namespace or "")
    plugin_name = str(args.plugin_name or DEFAULT_PLUGIN_NAME)
    selected_ip = ""
    capability_checks: List[Dict[str, str]] = []
    script_results: List[Dict[str, str]] = []
    warnings: List[str] = []
    script_ids: List[str] = []
    error = error_payload()
    remote_root = args.remote_root.rstrip("/")
    try:
        cfg = load_config(Path(args.config))
        access = cfg["access"]
        transport = default_remote_transport()
        selected_ip = str(access.get("primary_ip") or "")
        script_entries = load_script_entries(Path(args.manifest), Path(args.runtime_map), [str(item) for item in (args.script_id or []) if item])
        script_ids = [str(item["script_id"]) for item in script_entries]
        capabilities_ok, capability_checks, capability_error = validate_executor_capabilities(access, transport=transport)
        write_yaml(local_dir / "capability-checks.yaml", {"checks": capability_checks, "error": capability_error})
        if not capabilities_ok:
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                capability_error,
                warnings,
                "blocked",
                2,
                script_ids,
            )

        remote_script_roots = sorted({posixpath.dirname(remote_path(remote_root, str(item["runtime_path"]))) for item in script_entries})
        prep = transport.run(access, "mkdir -p %s" % " ".join(shlex.quote(item) for item in remote_script_roots))
        if prep.returncode != 0:
            error = classify_remote_error(prep.stderr or prep.stdout, "remote_workspace_unavailable")
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                error,
                warnings,
                status_from_error_code(error["code"]),
                2 if status_from_error_code(error["code"]) == "blocked" else 1,
                script_ids,
            )

        for entry in script_entries:
            try:
                transport.copy_to(access, Path(entry["source_path"]), remote_path(remote_root, str(entry["runtime_path"])))
            except RuntimeError as exc:
                error = classify_remote_error(str(exc), "script_stage_failed")
                return finalize_run(
                    local_dir,
                    incident_id,
                    plugin_name,
                    selected_ip,
                    namespace,
                    started_at,
                    capability_checks,
                    script_results,
                    error,
                    warnings,
                    status_from_error_code(error["code"]),
                    2 if status_from_error_code(error["code"]) == "blocked" else 1,
                    script_ids,
                )

        remote_shell_paths = [remote_path(remote_root, str(item["runtime_path"])) for item in script_entries if str(item["runtime"]) == "shell"]
        if remote_shell_paths:
            chmod = transport.run(access, "chmod +x %s" % " ".join(shlex.quote(item) for item in remote_shell_paths))
            if chmod.returncode != 0:
                error = classify_remote_error(chmod.stderr or chmod.stdout, "script_stage_failed")
                return finalize_run(
                    local_dir,
                    incident_id,
                    plugin_name,
                    selected_ip,
                    namespace,
                    started_at,
                    capability_checks,
                    script_results,
                    error,
                    warnings,
                    status_from_error_code(error["code"]),
                    2 if status_from_error_code(error["code"]) == "blocked" else 1,
                    script_ids,
                )

        if not namespace:
            namespace = choose_namespace(access, [item.strip() for item in args.namespace_candidates.split(",") if item.strip()], run_ssh_fn=transport.run)
        (local_dir / "selected_namespace.txt").write_text(namespace, encoding="utf-8")
        inventory_proc = collect_inventory(access, local_dir, run_ssh_fn=transport.run)
        if inventory_proc.returncode != 0:
            error = classify_remote_error(inventory_proc.stderr or inventory_proc.stdout, "inventory_collection_failed")
            return finalize_run(
                local_dir,
                incident_id,
                plugin_name,
                selected_ip,
                namespace,
                started_at,
                capability_checks,
                script_results,
                error,
                warnings,
                status_from_error_code(error["code"]),
                2 if status_from_error_code(error["code"]) == "blocked" else 1,
                script_ids,
            )

        context_profile = context_profile_from_inventory(args.inventory_file, namespace)
        write_yaml(local_dir / "context-profile.yaml", context_profile)

        for entry in script_entries:
            result = run_script(access, incident_id, entry, namespace, local_dir, remote_root, script_ids, context_profile, plugin_name, capability_checks, transport=transport)
            output = try_load_yaml(local_dir / str(entry["script_id"]) / "output.yaml")
            script_results.append(build_script_result_summary(result, output))

        return finalize_run(
            local_dir,
            incident_id,
            plugin_name,
            selected_ip,
            namespace,
            started_at,
            capability_checks,
            script_results,
            error,
            warnings,
            aggregate_run_status(script_results),
            0,
            script_ids,
        )
    except Exception as exc:
        error = error_payload("remote_executor_failed", str(exc))
        return finalize_run(
            local_dir,
            incident_id,
            plugin_name,
            selected_ip,
            namespace,
            started_at,
            capability_checks,
            script_results,
            error,
            warnings,
            "failed",
            1,
            script_ids,
        )


if __name__ == "__main__":
    raise SystemExit(main())
