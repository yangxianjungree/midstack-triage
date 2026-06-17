"""Remote-run file contract helpers for Phase 3 collection."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.patch_merge import apply_script_output
from shared.workspace import load_yaml, now_iso


def first_context(remote_run_dir: Path) -> Dict[str, Any]:
    for path in sorted(remote_run_dir.glob("*/context.yaml")):
        return load_yaml(path)
    return {}


def script_run_dirs(remote_run_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in remote_run_dir.iterdir()
        if path.is_dir()
        and any((path / filename).exists() for filename in ("output.yaml", "context.yaml", "remote-executor-result.yaml"))
    )


def load_remote_executor_run_result(remote_run_dir: Path) -> Dict[str, Any]:
    path = remote_run_dir / "remote-executor-run.yaml"
    return load_yaml(path) if path.exists() else {}


def copy_remote_run_support_files(remote_run_dir: Path, output_dir: Path) -> None:
    for filename in (
        "remote-executor-run.yaml",
        "capability-checks.yaml",
        "context-profile.yaml",
        "selected_namespace.txt",
        "inventory.stdout.txt",
        "inventory.stderr.txt",
    ):
        source = remote_run_dir / filename
        if source.exists():
            target = output_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def copy_remote_script_output(item_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "output.yaml",
        "context.yaml",
        "remote-executor-request.yaml",
        "remote-executor-result.yaml",
        "remote.stdout.txt",
        "remote.stderr.txt",
        "exit_code.txt",
        "artifact_retrieval_error.txt",
    ):
        if (item_dir / filename).exists():
            shutil.copy2(item_dir / filename, target_dir / filename)
    if (item_dir / "artifacts").exists():
        shutil.copytree(item_dir / "artifacts", target_dir / "artifacts", dirs_exist_ok=True)


def merge_remote_executor_run_result(collection_report: Dict[str, Any], run_result: Dict[str, Any], has_script_outputs: bool) -> None:
    if not run_result:
        return
    status = str(run_result.get("status") or "")
    if has_script_outputs and status not in ("blocked", "failed"):
        return
    selected_ip = str(run_result.get("selected_ip") or "")
    error = run_result.get("error") or {}
    capability_checks = [item for item in (run_result.get("capability_checks") or []) if isinstance(item, dict)]
    collection_report["collection_actions"].append(
        {
            "action_id": "remote-executor-run",
            "name": "remote executor batch run",
            "target": selected_ip or "remote executor",
            "method": "ssh + staged packaged scripts",
            "status": status or "unknown",
            "performed_at": str(run_result.get("finished_at") or run_result.get("started_at") or ""),
        }
    )
    if status in ("blocked", "failed"):
        collection_report["failed_items"].append(
            {
                "item": "remote-executor/run",
                "reason": str(error.get("message") or "remote executor batch run did not complete successfully"),
                "impact": "script execution evidence may be missing before per-script collection starts",
            }
        )
        note = "remote executor batch run %s" % (status or "unknown")
        if capability_checks:
            note = "%s after %s capability checks" % (note, len(capability_checks))
        collection_report["evidence_gaps"].append(
            {
                "gap": note,
                "related_stage": "signal_collection",
                "why_important": "preflight or staging failures can prevent the incident from collecting any remote evidence",
            }
        )


def remote_executor_required_user_action(code: str) -> str:
    if code == "missing_sshpass":
        return "install sshpass locally and rerun /midstack:analyse"
    if code in ("ssh_unreachable", "ssh_auth_failed"):
        return "fix remote SSH connectivity or credentials, then rerun /midstack:analyse"
    if code in ("kubectl_missing", "k8s_context_unavailable", "kubectl_exec_unavailable"):
        return "fix kubectl or Kubernetes access on the jump host, then rerun /midstack:analyse"
    return "inspect remote-executor-run.yaml and stderr output, then rerun /midstack:analyse"


def remote_executor_next_actions(code: str) -> List[str]:
    return [remote_executor_required_user_action(code)]


def merge_remote_executor_result(collection_report: Dict[str, Any], script_id: str, result: Dict[str, Any]) -> None:
    status = str(result.get("status") or "")
    selected_ip = str(result.get("selected_ip") or "")
    process = result.get("process") or {}
    error = result.get("error") or {}
    warnings = [str(item) for item in (result.get("warnings") or []) if item]
    action = {
        "action_id": "remote-executor-%s" % script_id.replace(".", "-"),
        "name": "remote executor run %s" % script_id,
        "target": selected_ip or script_id,
        "method": "ssh + staged packaged script",
        "status": status or "unknown",
        "performed_at": str(result.get("finished_at") or result.get("started_at") or ""),
    }
    collection_report["collection_actions"].append(action)

    output_ref = str(((result.get("retrieved_files") or {}).get("output_file")) or "")
    artifact_ref = str(((result.get("retrieved_files") or {}).get("artifact_dir")) or "")
    note_parts = ["status=%s" % (status or "unknown")]
    if output_ref:
        note_parts.append("output retrieved")
    if artifact_ref:
        note_parts.append("artifacts retrieved")
    if isinstance(process.get("exit_code"), int):
        note_parts.append("exit=%s" % process["exit_code"])

    if status in ("success", "partial"):
        collection_report["successful_items"].append(
            {
                "item": "remote-executor/%s" % script_id,
                "source": selected_ip or "remote executor",
                "note": ", ".join(note_parts),
            }
        )
    else:
        collection_report["failed_items"].append(
            {
                "item": "remote-executor/%s" % script_id,
                "reason": str(error.get("message") or "remote executor did not complete successfully"),
                "impact": "script execution evidence may be missing or incomplete",
            }
        )

    if status in ("partial", "blocked", "failed"):
        collection_report["evidence_gaps"].append(
            {
                "gap": "remote executor status %s for %s" % (status or "unknown", script_id),
                "related_stage": "signal_collection",
                "why_important": "missing or partial execution may hide expected script evidence",
            }
        )
    for warning in warnings:
        collection_report["evidence_gaps"].append(
            {
                "gap": "remote executor warning for %s: %s" % (script_id, warning),
                "related_stage": "signal_collection",
                "why_important": "execution warnings may indicate incomplete artifact retrieval",
            }
        )


def merge_remote_script_outputs(
    remote_run_dir: Path,
    output_dir: Path,
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
    item_dirs: Optional[List[Path]] = None,
) -> List[Path]:
    script_outputs_dir = output_dir / "script_outputs"
    item_dirs = item_dirs if item_dirs is not None else script_run_dirs(remote_run_dir)
    for item_dir in item_dirs:
        executor_result = load_yaml(item_dir / "remote-executor-result.yaml") if (item_dir / "remote-executor-result.yaml").exists() else {}
        output = load_yaml(item_dir / "output.yaml") if (item_dir / "output.yaml").exists() else {}
        script_id = str(output.get("script_id") or executor_result.get("script_id") or item_dir.name)
        if executor_result:
            merge_remote_executor_result(collection_report, script_id, executor_result)
        if output:
            apply_script_output(structured_record, signal_bundle, collection_report, output)
        copy_remote_script_output(item_dir, script_outputs_dir / script_id)
    return item_dirs


def build_input_from_remote_run(remote_run_dir: Path, args) -> Dict[str, Any]:
    context = first_context(remote_run_dir)
    run_result = load_remote_executor_run_result(remote_run_dir)
    incident_input = getattr(args, "incident_input", {}) or {}
    incident_id = str(
        incident_input.get("incident_id")
        or getattr(args, "incident_id_override", "")
        or context.get("incident_id")
        or run_result.get("incident_id")
        or remote_run_dir.name
    )
    return {
        "incident_id": incident_id,
        "middleware": str(incident_input.get("middleware") or context.get("middleware") or "mongodb"),
        "scenario": args.scenario or str(context.get("scenario") or "unknown"),
        "namespace": str(context.get("namespace") or run_result.get("namespace") or ""),
        "cluster_id": str(incident_input.get("cluster_id") or context.get("cluster_id") or run_result.get("cluster_id") or ""),
        "customer_clue": args.customer_clue or str(incident_input.get("customer_clue") or context.get("customer_clue") or "remote run script outputs"),
        "input_source": "incident-dir" if incident_input else "remote-run-dir",
        "remote_run_dir": str(remote_run_dir),
        "received_at": now_iso(),
    }
