"""Phase 3 collection helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.patch_merge import apply_script_output
from shared.scenario_router import infer_scenario
from shared.skill_resolver import (
    extract_script_ids,
    matched_asset_refs,
    missing_required_scripts,
    recollection_script_pool,
    resolve_skills,
    script_collection_statuses,
)
from shared.workspace import load_yaml, now_iso, resolve_path, write_yaml


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


def infer_gap_type(gap_text: str, item: Dict[str, Any]) -> str:
    explicit = str(item.get("gap_type") or item.get("type") or "").strip()
    if explicit in ("expected_gap", "critical_gap"):
        return explicit
    text = gap_text.lower()
    if "critical_gap" in text or "critical gap" in text:
        return "critical_gap"
    if "log sink" in text or "real log" in text or "true log" in text or "logs too short" in text or "file log" in text or "application log source" in text:
        return "critical_gap"
    if "script output missing" in text or "remote executor" in text or "signal bundle depends" in text:
        return "critical_gap"
    if "rs.status" in text and any(token in text for token in ("no healthy", "all", "not collected from any", "missing")):
        return "critical_gap"
    if any(token in text for token in ("affected pod", "faulty pod", "bad pod", "current pod")) and ("rs.status" in text or "fatal tail" in text):
        return "expected_gap"
    return "expected_gap"


def normalize_collection_report_gaps(collection_report: Dict[str, Any]) -> None:
    normalized: List[Any] = []
    for item in collection_report.get("evidence_gaps") or []:
        if isinstance(item, dict):
            gap = str(item.get("gap") or item)
            item = dict(item)
            item["gap_type"] = infer_gap_type(gap, item)
            if not item.get("related_stage"):
                item["related_stage"] = "signal_collection"
            if not item.get("why_important"):
                item["why_important"] = "This gap affects evidence completeness."
            normalized.append(item)
        else:
            gap = str(item)
            normalized.append(
                {
                    "gap": gap,
                    "gap_type": infer_gap_type(gap, {}),
                    "related_stage": "signal_collection",
                    "why_important": "This gap affects evidence completeness.",
                }
            )
    collection_report["evidence_gaps"] = normalized


def gap_closed_by_file_tail(gap_text: str) -> bool:
    text = gap_text.lower()
    return (
        ("file-backed" in text or "file log" in text or "log sink" in text or "application logs" in text)
        and any(token in text for token in ("kubectl logs", "collect", "not proven", "may only appear", "insufficient"))
    )


def drop_closed_evidence_gaps(structured_record: Dict[str, Any], collection_report: Dict[str, Any]) -> None:
    details = structured_record.get("details") or {}
    has_file_tail = any(isinstance(item, dict) and str(item.get("log_type") or "") == "file_tail" for item in details.get("raw_logs") or []) or bool(isinstance(details.get("processed_logs"), dict) and (details.get("processed_logs") or {}).get("file_tail_highlights"))
    if not has_file_tail:
        return
    kept: List[Any] = []
    for item in collection_report.get("evidence_gaps") or []:
        gap_text = str((item or {}).get("gap") if isinstance(item, dict) else item)
        if gap_closed_by_file_tail(gap_text):
            continue
        kept.append(item)
    collection_report["evidence_gaps"] = kept


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


def build_incident_from_remote_run(remote_run_dir: Path, output_dir: Path, args, preserve_existing_input: bool = False) -> None:
    if not remote_run_dir.exists():
        raise FileNotFoundError("remote run dir does not exist: %s" % remote_run_dir)
    context = first_context(remote_run_dir)
    run_result = load_remote_executor_run_result(remote_run_dir)
    input_file = output_dir / "input.yaml"
    if preserve_existing_input and input_file.exists():
        input_data = load_yaml(input_file)
    else:
        input_data = build_input_from_remote_run(remote_run_dir, args)
    generated_at = now_iso()
    structured_record: Dict[str, Any] = {
        "summary": {
            "middleware": input_data["middleware"],
            "topology_type": str(context.get("topology_type") or ""),
            "deployment_architecture": str(context.get("deployment_architecture") or ""),
            "namespace": input_data["namespace"],
            "cluster_id": input_data["cluster_id"],
        },
        "details": {},
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    signal_bundle: Dict[str, Any] = {
        "incident_id": input_data["incident_id"],
        "middleware": input_data["middleware"],
        "signal_overview": {"status": "unknown", "abnormal_signal_count": 0},
        "abnormal_signals": [],
        "object_signal_links": [],
        "timeline_summary": [],
        "processed_log_highlights": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    collection_report: Dict[str, Any] = {
        "collection_actions": [],
        "successful_items": [],
        "failed_items": [],
        "blank_items": [],
        "evidence_gaps": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    copy_remote_run_support_files(remote_run_dir, output_dir)

    script_outputs_dir = output_dir / "script_outputs"
    if script_outputs_dir.exists():
        shutil.rmtree(script_outputs_dir)
    item_dirs = merge_remote_script_outputs(remote_run_dir, output_dir, structured_record, signal_bundle, collection_report)
    merge_remote_executor_run_result(collection_report, run_result, bool(item_dirs))
    drop_closed_evidence_gaps(structured_record, collection_report)
    normalize_collection_report_gaps(collection_report)

    if not preserve_existing_input or not input_file.exists():
        write_yaml(input_file, input_data)
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def run_remote_collection(args, output_dir: Path, script_ids: List[str] = None) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    src_dir = str(Path(__file__).resolve().parents[2])
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = src_dir if not pythonpath else "%s%s%s" % (src_dir, os.pathsep, pythonpath)
    command = [
        sys.executable,
        "-m",
        "execution.remote.executor",
        "--config",
        str(resolve_path(args.remote_config)),
        "--output-dir",
        str(resolve_path(args.remote_output_dir)),
    ]
    if getattr(args, "object_inventory", ""):
        command.extend(["--inventory-file", str(resolve_path(args.object_inventory))])
    if args.remote_namespace:
        command.extend(["--namespace", args.remote_namespace])
    for script_id in script_ids or []:
        command.extend(["--script-id", script_id])
    try:
        proc = subprocess.run(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=900,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = ((exc.stderr or "") + "\nremote executor timed out after 900s").strip()
        returncode = 124
    (output_dir / "remote-executor.stdout.txt").write_text(stdout, encoding="utf-8")
    (output_dir / "remote-executor.stderr.txt").write_text(stderr, encoding="utf-8")
    local_dir = None
    for line in stdout.splitlines():
        if line.startswith("local_dir="):
            local_dir = resolve_path(line.split("=", 1)[1].strip())
            break
    if returncode != 0:
        if local_dir is not None and local_dir.exists():
            return local_dir
        raise RuntimeError("remote executor failed: %s" % stderr.strip())
    if local_dir is not None:
        return local_dir
    raise RuntimeError("remote executor output did not include local_dir")


def merge_remote_run_outputs(remote_run_dir: Path, output_dir: Path) -> None:
    structured_record = load_yaml(output_dir / "structured_record.yaml")
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml")
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    run_result = load_remote_executor_run_result(remote_run_dir)
    item_dirs = script_run_dirs(remote_run_dir)
    merge_remote_executor_run_result(collection_report, run_result, bool(item_dirs))
    merge_remote_script_outputs(remote_run_dir, output_dir, structured_record, signal_bundle, collection_report, item_dirs)
    if (remote_run_dir / "remote-executor-run.yaml").exists():
        shutil.copy2(remote_run_dir / "remote-executor-run.yaml", output_dir / "directed-recollection-run.yaml")
    drop_closed_evidence_gaps(structured_record, collection_report)
    normalize_collection_report_gaps(collection_report)
    timestamp = now_iso()
    structured_record["updated_at"] = timestamp
    signal_bundle["updated_at"] = timestamp
    collection_report["updated_at"] = timestamp
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)


SCRIPT_LOG_SINK_DISCOVER = "mongodb.collect.logs.discover_sink"
SCRIPT_LOG_FILE_TAIL = "mongodb.collect.logs.file_tail"
SCRIPT_LOG_NODE_FILE_TAIL = "mongodb.collect.logs.node_file_tail"
SCRIPT_DNS_COREDNS = "mongodb.collect.dns.coredns"
SCRIPT_NETWORK_OVERLAY = "mongodb.collect.network.overlay"
SCRIPT_PODS_DESCRIBE = "mongodb.collect.pods.describe"
DIRECTED_RECOLLECTION_CAP = 3


def signal_bundle_has(signal_bundle: Dict[str, Any], signal_id: str) -> bool:
    for item in signal_bundle.get("abnormal_signals") or []:
        if isinstance(item, dict) and str(item.get("signal_id") or "") == signal_id:
            return True
    return False


def has_log_sink_record(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    return bool(details.get("log_sinks"))


def has_file_backed_log_sink(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("log_sinks") or []:
        if not isinstance(item, dict):
            continue
        if item.get("path") and not bool(item.get("is_stdout_link")):
            return True
    return False


def details_has_items(structured_record: Dict[str, Any], key: str) -> bool:
    details = structured_record.get("details") or {}
    value = details.get(key)
    return bool(value)


def has_file_tail_logs(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if isinstance(item, dict) and str(item.get("log_type") or "") == "file_tail":
            return True
    processed = details.get("processed_logs") or {}
    return bool(isinstance(processed, dict) and processed.get("file_tail_highlights"))


def text_has_direct_error_terms(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("fatal", "wiredtiger", "corrupt", "journal", "bad magic number", "assertion", "unclean shutdown"))


def signal_bundle_text(signal_bundle: Dict[str, Any]) -> str:
    return json.dumps(signal_bundle, ensure_ascii=False).lower()


def incident_evidence_text(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> str:
    return json.dumps(
        {
            "structured_record": structured_record,
            "signal_bundle": signal_bundle,
            "collection_report": collection_report,
        },
        ensure_ascii=False,
    ).lower()


def signal_object_pods(signal_bundle: Dict[str, Any], signal_ids: List[str]) -> List[str]:
    wanted = set(signal_ids)
    pods: List[str] = []
    for item in signal_bundle.get("abnormal_signals") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("signal_id") or "") not in wanted:
            continue
        object_ref = str(item.get("object_ref") or "")
        if object_ref.startswith("pod/"):
            pod = object_ref.split("/", 1)[1]
            if pod and pod not in pods:
                pods.append(pod)
    return pods


def current_logs_are_short(structured_record: Dict[str, Any]) -> bool:
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("log_type") or "") != "current":
            continue
        line_count = int(item.get("line_count") or 0)
        byte_size = int(item.get("byte_size") or 0)
        if line_count <= 5 or byte_size <= 512:
            return True
    return False


def crashloop_logs_are_shallow(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    crashloop_pods = set(signal_object_pods(signal_bundle, ["pod-crashloop"]))
    if not crashloop_pods:
        return False
    highlights_text = signal_bundle_text(signal_bundle)
    if text_has_direct_error_terms(highlights_text):
        return False
    details = structured_record.get("details") or {}
    for item in details.get("raw_logs") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("log_type") or "") not in ("current", "previous"):
            continue
        if str(item.get("pod_ref") or "") not in crashloop_pods:
            continue
        line_count = int(item.get("line_count") or 0)
        byte_size = int(item.get("byte_size") or 0)
        if line_count <= 25 or byte_size <= 4096:
            return True
    return False


def collection_report_mentions_log_sink_gap(collection_report: Dict[str, Any]) -> bool:
    text = json.dumps(collection_report.get("evidence_gaps") or [], ensure_ascii=False).lower()
    return (
        "log sink" in text
        or "logs too short" in text
        or "real log" in text
        or "true log" in text
        or "file log" in text
        or "application log source" in text
    )


def evidence_mentions_dns_issue(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    text = incident_evidence_text(structured_record, signal_bundle, collection_report)
    return any(
        token in text
        for token in (
            "cannot resolve host",
            "lookup ",
            "10.96.0.10:53",
            "kube-dns",
            "coredns",
            "dns",
            "no servers could be reached",
        )
    ) and any(token in text for token in ("timed out", "timeout", "connection refused", "temporary failure", "i/o timeout"))


def should_run_log_sink_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if has_log_sink_record(structured_record):
        return False
    if collection_report_mentions_log_sink_gap(collection_report):
        return True
    if signal_bundle_has(signal_bundle, "pod-crashloop") and current_logs_are_short(structured_record):
        return True
    return crashloop_logs_are_shallow(structured_record, signal_bundle)


def should_run_log_file_tail_recollection(structured_record: Dict[str, Any], selected: List[str]) -> bool:
    if SCRIPT_LOG_SINK_DISCOVER in selected:
        return True
    if has_file_backed_log_sink(structured_record) and not has_file_tail_logs(structured_record):
        return True
    return False


def should_run_log_node_file_tail_recollection(structured_record: Dict[str, Any], selected: List[str]) -> bool:
    if has_file_tail_logs(structured_record):
        return False
    if SCRIPT_LOG_SINK_DISCOVER in selected or SCRIPT_LOG_FILE_TAIL in selected:
        return True
    if has_file_backed_log_sink(structured_record):
        return True
    return False


def should_run_dns_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "dns_checks"):
        return False
    return evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report)


def should_run_network_overlay_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any], collection_report: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "network_overlay"):
        return False
    return evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report) or signal_bundle_has(signal_bundle, "dns-resolution-failed")


def should_run_pod_describe_recollection(structured_record: Dict[str, Any], signal_bundle: Dict[str, Any]) -> bool:
    if details_has_items(structured_record, "pod_describes"):
        return False
    if details_has_items(structured_record, "pod_terminations"):
        return False
    return bool(signal_object_pods(signal_bundle, ["pod-crashloop", "pod-not-ready"]))


def select_directed_recollection_script_ids(
    structured_record: Dict[str, Any],
    signal_bundle: Dict[str, Any],
    collection_report: Dict[str, Any],
) -> List[str]:
    selected: List[str] = []

    dns_path = evidence_mentions_dns_issue(structured_record, signal_bundle, collection_report) or signal_bundle_has(signal_bundle, "dns-resolution-failed")
    if dns_path and should_run_dns_recollection(structured_record, signal_bundle, collection_report):
        selected.append(SCRIPT_DNS_COREDNS)
    if dns_path and should_run_network_overlay_recollection(structured_record, signal_bundle, collection_report):
        selected.append(SCRIPT_NETWORK_OVERLAY)
    if dns_path and signal_bundle_has(signal_bundle, "pod-crashloop") and not has_file_tail_logs(structured_record):
        selected.append(SCRIPT_LOG_NODE_FILE_TAIL)
    if not dns_path:
        if should_run_log_sink_recollection(structured_record, signal_bundle, collection_report):
            selected.append(SCRIPT_LOG_SINK_DISCOVER)
        if should_run_log_file_tail_recollection(structured_record, selected):
            selected.append(SCRIPT_LOG_FILE_TAIL)
        if should_run_log_node_file_tail_recollection(structured_record, selected):
            selected.append(SCRIPT_LOG_NODE_FILE_TAIL)
    if should_run_pod_describe_recollection(structured_record, signal_bundle):
        selected.append(SCRIPT_PODS_DESCRIBE)
    return selected[:DIRECTED_RECOLLECTION_CAP]


def filter_recollection_scripts_by_skill_pool(selected: List[str], skill_pool: Optional[set[str]]) -> tuple[List[str], bool]:
    if not skill_pool:
        return selected, False
    filtered = [script_id for script_id in selected if script_id in skill_pool]
    if filtered:
        return filtered, False
    return selected, bool(selected)


def record_recollection_skill_pool_miss(output_dir: Path) -> None:
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    collection_report.setdefault("warnings", []).append(
        "directed recollection fell back to legacy script selection because matched skill pool did not cover triggered playbooks (gap_type=skill_pool_miss)"
    )
    collection_report["updated_at"] = now_iso()
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def directed_recollection_script_ids(output_dir: Path, skill_pool: Optional[set[str]] = None) -> List[str]:
    structured_record = load_yaml(output_dir / "structured_record.yaml")
    signal_bundle = load_yaml(output_dir / "signal_bundle.yaml")
    collection_report = load_yaml(output_dir / "collection_report.yaml")
    selected = select_directed_recollection_script_ids(structured_record, signal_bundle, collection_report)
    filtered, skill_pool_miss = filter_recollection_scripts_by_skill_pool(selected, skill_pool)
    if skill_pool_miss:
        record_recollection_skill_pool_miss(output_dir)
    return filtered


def apply_scenario_routing_if_needed(output_dir: Path, args) -> Dict[str, Any]:
    input_file = output_dir / "input.yaml"
    signal_bundle_file = output_dir / "signal_bundle.yaml"
    if not input_file.exists() or not signal_bundle_file.exists():
        return load_yaml(input_file) if input_file.exists() else {}

    input_data = load_yaml(input_file)
    existing_scenario = str(input_data.get("scenario") or "unknown")
    if existing_scenario not in ("", "unknown", "baseline"):
        return input_data

    structured_record_file = output_dir / "structured_record.yaml"
    structured_record = load_yaml(structured_record_file) if structured_record_file.exists() else {}
    signal_bundle = load_yaml(signal_bundle_file)
    routing = infer_scenario(
        signal_bundle,
        structured_record=structured_record,
        customer_clue=str(input_data.get("customer_clue") or getattr(args, "customer_clue", "") or ""),
        middleware=str(input_data.get("middleware") or "mongodb"),
    )
    input_data["scenario"] = routing["scenario"]
    input_data["scenario_inference"] = routing["scenario_inference"]
    input_data["updated_at"] = now_iso()
    write_yaml(input_file, input_data)
    args.scenario = routing["scenario"]
    return input_data


def resolve_skill_runtime(input_data: Dict[str, Any], output_dir: Path, collection_report: Dict[str, Any]) -> Dict[str, Any]:
    middleware = str(input_data.get("middleware") or "mongodb")
    scenario = str(input_data.get("scenario") or "unknown")
    skills = resolve_skills(middleware, scenario)
    skill_pool = recollection_script_pool(middleware, scenario)
    required_scripts: List[str] = []
    for skill in skills:
        required_scripts.extend(extract_script_ids(skill["metadata"]))
    required_scripts = sorted(set(required_scripts))

    script_statuses = script_collection_statuses(output_dir, collection_report)
    missing_or_failed = missing_required_scripts(required_scripts, script_statuses)
    return {
        "skills": skills,
        "skill_pool": skill_pool,
        "required_scripts": required_scripts,
        "missing_or_failed": missing_or_failed,
        "script_statuses": script_statuses,
    }


def write_skill_runtime_context(
    output_dir: Path,
    input_data: Dict[str, Any],
    collection_report: Dict[str, Any],
    runtime: Dict[str, Any],
    middleware: str,
) -> None:
    skills = runtime.get("skills") or []
    skill_pool = runtime.get("skill_pool") or set()
    collection_report["skill_evidence_check"] = {
        "skill_ids": [skill["id"] for skill in skills],
        "required_scripts": runtime.get("required_scripts") or [],
        "recollection_script_pool": sorted(skill_pool),
        "script_statuses": runtime.get("script_statuses") or {},
        "missing_or_failed": runtime.get("missing_or_failed") or [],
    }
    collection_report["updated_at"] = now_iso()
    write_yaml(output_dir / "collection_report.yaml", collection_report)

    input_data["matched_skill_ids"] = [skill["id"] for skill in skills]
    input_data["matched_assets"] = matched_asset_refs(middleware, skills)
    write_yaml(output_dir / "input.yaml", input_data)


def enrich_skill_runtime_context(output_dir: Path, input_data: Dict[str, Any]) -> Dict[str, Any]:
    collection_report_file = output_dir / "collection_report.yaml"
    collection_report = load_yaml(collection_report_file) if collection_report_file.exists() else {}
    runtime = resolve_skill_runtime(input_data, output_dir, collection_report)
    middleware = str(input_data.get("middleware") or "mongodb")
    write_skill_runtime_context(output_dir, input_data, collection_report, runtime, middleware)
    return {
        "skills": runtime["skills"],
        "skill_pool": runtime["skill_pool"],
        "required_scripts": runtime["required_scripts"],
        "missing_or_failed": runtime["missing_or_failed"],
    }


def run_directed_recollection_if_needed(args, output_dir: Path, skill_pool: Optional[set[str]] = None) -> bool:
    if not args.remote_config:
        return False
    script_ids = directed_recollection_script_ids(output_dir, skill_pool=skill_pool)
    if not script_ids:
        return False
    trace_dir = output_dir / "directed-recollection"
    remote_run_dir = run_remote_collection(args, trace_dir, script_ids)
    merge_remote_run_outputs(remote_run_dir, output_dir)
    return True
