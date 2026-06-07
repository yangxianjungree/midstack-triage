#!/usr/bin/env python3

import argparse
import os
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = ROOT / "tools" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from patch_merge import apply_script_output  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def adapter_output(command: str, incident_id: str, middleware: str, status: str, summary: str, output_dir: Path) -> Dict[str, Any]:
    return {
        "plugin_name": "midstack-triage-local",
        "command": command,
        "incident_id": incident_id,
        "middleware": middleware,
        "status": status,
        "summary": summary,
        "user_message": summary,
        "record_refs": [
            {
                "name": "incident_dir",
                "path": str(output_dir),
                "description": "local incident directory",
            }
        ],
        "next_actions": [],
        "blocking_items": [],
        "warnings": [],
        "generated_at": now_iso(),
    }


def path_from_arg(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def current_incident_marker(output_root: Path) -> Path:
    return output_root / ".current-incident"


def write_current_incident(output_root: Path, incident_dir: Path) -> None:
    marker = current_incident_marker(output_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(incident_dir) + "\n", encoding="utf-8")


def read_current_incident(output_root: Path) -> Path:
    marker = current_incident_marker(output_root)
    if not marker.exists():
        raise FileNotFoundError("current incident marker does not exist: %s" % marker)
    value = marker.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("current incident marker is empty: %s" % marker)
    return resolve_path(value)


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
        "-p",
        str(access.get("port", 22)),
        "%s@%s" % (access["username"], access["primary_ip"]),
        "bash -lc %s" % json.dumps(remote_command),
    ]


def run_env_check(access: Dict[str, Any], remote_command: str) -> Dict[str, Any]:
    if not shutil.which("sshpass"):
        return {"status": "failed", "stdout": "", "stderr": "sshpass is not installed"}
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    proc = subprocess.run(
        ssh_command(access, remote_command),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30,
    )
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


def command_start(args: argparse.Namespace) -> int:
    incident_id = args.incident_id or "%s-%s" % (args.middleware, datetime.now().strftime("%Y%m%d-%H%M%S"))
    output_dir = path_from_arg(args.output_root) / incident_id
    created_at = now_iso()
    env_ips = [item for item in (args.environment_ip or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    blocking_items = []
    if not args.middleware:
        blocking_items.append({"code": "missing_middleware", "message": "middleware is required", "required_user_action": "provide middleware, for example mongodb"})
    if not args.customer_clue:
        blocking_items.append({"code": "missing_customer_clue", "message": "customer clue is required", "required_user_action": "provide the incident clue or symptom"})
    if not primary_ip:
        blocking_items.append({"code": "missing_environment_ip", "message": "environment IP is required", "required_user_action": "provide at least one remote environment IP"})
    if not args.username:
        blocking_items.append({"code": "missing_username", "message": "remote username is required", "required_user_action": "provide remote username"})
    if not args.password:
        blocking_items.append({"code": "missing_password", "message": "remote password is required", "required_user_action": "provide remote password"})

    remote_validation: Dict[str, Any] = {"status": "skipped", "checks": []}
    access = {
        "candidate_ips": env_ips,
        "primary_ip": primary_ip,
        "username": args.username,
        "password": args.password,
        "port": args.port,
    }
    if not blocking_items:
        remote_validation = validate_remote_environment(access)
        if remote_validation["status"] != "passed":
            blocking_items.append(
                {
                    "code": "remote_environment_validation_failed",
                    "message": "remote SSH or kubectl validation failed",
                    "required_user_action": "fix remote access, install sshpass locally, or ensure kubectl can access the cluster on the jump host",
                }
            )

    status = "ready" if not blocking_items else "blocked"
    write_yaml(
        output_dir / "meta.yaml",
        {
            "incident_id": incident_id,
            "middleware": args.middleware,
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
            "plugin_version": "local-prototype",
            "current_command": "start",
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "owner": "local",
            "remote_validation": remote_validation,
        },
    )
    write_yaml(
        output_dir / "input.yaml",
        {
            "middleware": args.middleware,
            "incident_id": incident_id,
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "customer_clue": args.customer_clue,
            "input_source": "local-cli",
            "environment_ips": env_ips,
            "remote_port": args.port,
            "received_at": created_at,
        },
    )
    if primary_ip:
        write_yaml(
            output_dir / "remote-config.yaml",
            {
                "name": "%s-remote" % incident_id,
                "purpose": "incident remote Kubernetes environment",
                "created_at": created_at,
                "access": access,
                "defaults": {
                    "jump_host_strategy": "first_ip",
                    "remote_workspace_root": "/tmp/midstack-triage",
                    "remote_script_root": "/tmp/midstack-triage/assets/scripts",
                    "remote_run_root": "/tmp/midstack-triage/runs",
                    "kubectl_required": True,
                    "kubectl_exec_required": True,
                    "middleware_tools_location": "pod_internal",
                },
            },
        )
    output = adapter_output("start", incident_id, args.middleware, status, "local incident %s is %s" % (incident_id, status), output_dir)
    if status == "ready":
        output["next_actions"] = ["run analyse with --incident-dir %s" % output_dir]
        write_current_incident(path_from_arg(args.output_root), output_dir)
    else:
        output["blocking_items"] = blocking_items
        output["warnings"].append("incident is blocked until required input and remote validation pass")
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(output_dir))
    return 0 if status == "ready" else 1


def copy_if_exists(source_dir: Path, output_dir: Path, filename: str) -> None:
    source = source_dir / filename
    if source.exists():
        target = output_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def first_context(remote_run_dir: Path) -> Dict[str, Any]:
    for path in sorted(remote_run_dir.glob("*/context.yaml")):
        return load_yaml(path)
    return {}


def script_output_dirs(remote_run_dir: Path) -> List[Path]:
    return sorted(path for path in remote_run_dir.iterdir() if path.is_dir() and (path / "output.yaml").exists())


def build_input_from_remote_run(remote_run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]:
    context = first_context(remote_run_dir)
    incident_input = getattr(args, "incident_input", {}) or {}
    incident_id = str(incident_input.get("incident_id") or getattr(args, "incident_id_override", "") or context.get("incident_id") or remote_run_dir.name)
    return {
        "incident_id": incident_id,
        "middleware": str(incident_input.get("middleware") or context.get("middleware") or "mongodb"),
        "scenario": args.scenario or str(context.get("scenario") or "unknown"),
        "namespace": str(context.get("namespace") or ""),
        "cluster_id": str(incident_input.get("cluster_id") or context.get("cluster_id") or ""),
        "customer_clue": args.customer_clue or str(incident_input.get("customer_clue") or context.get("customer_clue") or "remote run script outputs"),
        "input_source": "incident-dir" if incident_input else "remote-run-dir",
        "remote_run_dir": str(remote_run_dir),
        "received_at": now_iso(),
    }


def build_incident_from_remote_run(remote_run_dir: Path, output_dir: Path, args: argparse.Namespace) -> None:
    if not remote_run_dir.exists():
        raise FileNotFoundError("remote run dir does not exist: %s" % remote_run_dir)
    context = first_context(remote_run_dir)
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

    script_outputs_dir = output_dir / "script_outputs"
    if script_outputs_dir.exists():
        shutil.rmtree(script_outputs_dir)
    for item_dir in script_output_dirs(remote_run_dir):
        output = load_yaml(item_dir / "output.yaml")
        script_id = str(output.get("script_id") or item_dir.name)
        apply_script_output(structured_record, signal_bundle, collection_report, output)

        target_dir = script_outputs_dir / script_id
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item_dir / "output.yaml", target_dir / "output.yaml")
        if (item_dir / "context.yaml").exists():
            shutil.copy2(item_dir / "context.yaml", target_dir / "context.yaml")

    write_yaml(output_dir / "input.yaml", input_data)
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def run_remote_smoke(args: argparse.Namespace, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "tools" / "remote-smoke" / "mongodb-smoke.py"),
        "--config",
        str(resolve_path(args.remote_config)),
        "--output-dir",
        str(resolve_path(args.remote_output_dir)),
    ]
    if args.remote_namespace:
        command.extend(["--namespace", args.remote_namespace])
    proc = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    (output_dir / "remote-smoke.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (output_dir / "remote-smoke.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError("remote smoke failed: %s" % proc.stderr.strip())
    for line in proc.stdout.splitlines():
        if line.startswith("local_dir="):
            return resolve_path(line.split("=", 1)[1].strip())
    raise RuntimeError("remote smoke output did not include local_dir")


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def write_report(output_dir: Path, input_data: Dict[str, Any], analysis: Dict[str, Any]) -> Path:
    conclusion = analysis.get("conclusion_summary") or {}
    report_file = output_dir / "report.md"
    lines = [
        "# Midstack Triage Report",
        "",
        "## Incident",
        "",
        "- Incident ID: `%s`" % input_data.get("incident_id", output_dir.name),
        "- Middleware: `%s`" % input_data.get("middleware", "mongodb"),
        "- Namespace: `%s`" % input_data.get("namespace", ""),
        "- Cluster: `%s`" % input_data.get("cluster_id", ""),
        "- Customer clue: %s" % input_data.get("customer_clue", ""),
        "",
        "## Conclusion",
        "",
        "- Statement: %s" % conclusion.get("statement", ""),
        "- Confidence: `%s`" % conclusion.get("confidence", ""),
        "- Primary cause category: `%s`" % conclusion.get("primary_cause_category", ""),
        "- Impact scope: %s" % conclusion.get("impact_scope", ""),
        "",
        "## Evidence",
        "",
    ]
    evidence = as_list(conclusion.get("evidence"))
    lines.extend(["- %s" % item for item in evidence] if evidence else ["- No explicit evidence recorded."])
    lines.extend(["", "## Hypotheses", ""])
    for item in as_list(analysis.get("hypotheses")):
        if not isinstance(item, dict):
            continue
        lines.append("- `%s` %s: %s" % (item.get("status", ""), item.get("hypothesis_id", ""), item.get("statement", "")))
    lines.extend(["", "## Evidence Gaps", ""])
    gaps = as_list(conclusion.get("limitations"))
    lines.extend(["- %s" % item for item in gaps] if gaps else ["- No explicit evidence gaps recorded."])
    lines.extend(["", "## Next Read-Only Actions", ""])
    actions = as_list(analysis.get("next_actions"))
    lines.extend(["- %s" % ((item or {}).get("action") if isinstance(item, dict) else item) for item in actions] if actions else ["- No next actions recorded."])
    lines.extend(["", "## Knowledge Candidates", ""])
    candidates = as_list(analysis.get("knowledge_candidates"))
    if candidates:
        for item in candidates:
            if isinstance(item, dict):
                lines.append("- `%s` %s: `%s`" % (item.get("candidate_type", ""), item.get("title", ""), item.get("asset_path", "")))
    else:
        lines.append("- No knowledge candidates recorded.")
    lines.append("")
    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file


def command_analyse(args: argparse.Namespace) -> int:
    if not (args.incident_dir or args.remote_config or args.remote_run_dir or args.input_dir):
        args.incident_dir = str(read_current_incident(path_from_arg(args.output_root)))
    if args.incident_dir:
        incident_dir = resolve_path(args.incident_dir)
        if not incident_dir.exists():
            print("ERROR: incident dir does not exist: %s" % incident_dir, file=sys.stderr)
            return 1
        output_dir = resolve_path(args.output_dir) if args.output_dir else incident_dir
        input_data = load_yaml(incident_dir / "input.yaml")
        args.incident_input = input_data
        args.incident_id_override = str(input_data.get("incident_id") or incident_dir.name)
        args.remote_config = str(incident_dir / "remote-config.yaml")
        args.remote_namespace = args.remote_namespace or str(input_data.get("namespace") or "")
        args.customer_clue = args.customer_clue or str(input_data.get("customer_clue") or "")
        args.scenario = args.scenario or str(input_data.get("scenario") or "unknown")
        if not Path(args.remote_config).exists():
            print("ERROR: missing incident remote-config.yaml: %s" % args.remote_config, file=sys.stderr)
            return 1
    else:
        if not args.output_dir:
            print("ERROR: --output-dir is required unless --incident-dir is used", file=sys.stderr)
            return 1
        output_dir = resolve_path(args.output_dir)
    try:
        if args.remote_config:
            remote_run_dir = run_remote_smoke(args, output_dir)
            build_incident_from_remote_run(remote_run_dir, output_dir, args)
        elif args.remote_run_dir:
            build_incident_from_remote_run(resolve_path(args.remote_run_dir), output_dir, args)
        else:
            input_dir = resolve_path(args.input_dir)
            for filename in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml", "expected_analysis.yaml"):
                copy_if_exists(input_dir, output_dir, filename)
    except Exception as exc:
        output_dir.mkdir(parents=True, exist_ok=True)
        incident_id = output_dir.name
        output = adapter_output("analyse", incident_id, "mongodb", "failed", "local analyse failed", output_dir)
        output["warnings"].append(str(exc))
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    input_data = load_yaml(output_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or output_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    analysis_file = output_dir / "analysis.yaml"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "analyse" / "mongodb-analyse.py"),
            "--input-dir",
            str(output_dir),
            "--output-file",
            str(analysis_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    status = "completed" if proc.returncode == 0 else "failed"
    output = adapter_output("analyse", incident_id, middleware, status, "local analyse %s" % status, output_dir)
    output["record_refs"].append({"name": "analysis", "path": str(analysis_file), "description": "generated analysis result"})
    if proc.returncode != 0:
        output["warnings"].append(proc.stderr.strip())
    else:
        analysis = load_yaml(analysis_file)
        report_file = write_report(output_dir, input_data, analysis)
        output["record_refs"].append({"name": "report", "path": str(report_file), "description": "generated human-readable report"})
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(analysis_file))
    return proc.returncode


LEVEL_VALUE = {"low": 1, "medium": 2, "high": 3}


def score_item(level: str, reason: str) -> Dict[str, str]:
    return {"level": level, "reason": reason}


def level_from_confidence(confidence: str) -> str:
    return "high" if confidence == "high" else ("medium" if confidence == "medium" else "low")


def overall_level(score: Dict[str, Dict[str, str]]) -> str:
    values = [LEVEL_VALUE.get(item.get("level", "low"), 1) for item in score.values()]
    average = sum(values) / float(len(values) or 1)
    if average >= 2.67:
        return "high"
    if average >= 1.67:
        return "medium"
    return "low"


def review_score_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    conclusion = analysis.get("conclusion_summary") or {}
    hypotheses = [item for item in analysis.get("hypotheses") or [] if isinstance(item, dict)]
    knowledge_candidates = [item for item in analysis.get("knowledge_candidates") or [] if isinstance(item, dict)]
    conclusion_evidence = conclusion.get("evidence") or []
    supported = [item for item in hypotheses if item.get("status") == "supported" or item.get("validation_result") == "supported"]
    refuted = [item for item in hypotheses if item.get("status") == "refuted" or item.get("validation_result") == "refuted"]
    validation_actions = []
    for item in hypotheses:
        for action in item.get("validation_actions") or []:
            validation_actions.append(action)

    if conclusion_evidence:
        evidence_score = score_item("high", "Conclusion includes explicit evidence.")
    elif supported:
        evidence_score = score_item("medium", "Hypotheses include supported results, but conclusion evidence is thin.")
    else:
        evidence_score = score_item("low", "No explicit conclusion evidence or supported hypothesis found.")

    if len(hypotheses) >= 2 and supported:
        hypothesis_score = score_item("high", "Analysis includes multiple hypotheses and at least one supported path.")
    elif hypotheses:
        hypothesis_score = score_item("medium", "Analysis includes hypotheses, but coverage is limited.")
    else:
        hypothesis_score = score_item("low", "No hypotheses generated.")

    if validation_actions:
        validation_score = score_item("high", "Analysis includes explicit validation actions.")
    elif supported or refuted:
        validation_score = score_item("medium", "Hypotheses have validation results, but no additional validation actions were executed.")
    else:
        validation_score = score_item("low", "No validation actions or decisive validation results.")

    confidence_score = score_item(
        level_from_confidence(str(conclusion.get("confidence") or "low")),
        "Derived from conclusion_summary.confidence.",
    )

    if knowledge_candidates:
        knowledge_score = score_item("high", "Analysis produced reusable knowledge candidates.")
    elif conclusion.get("primary_cause_category") == "baseline":
        knowledge_score = score_item("medium", "Baseline case is reusable for regression, not production knowledge.")
    else:
        knowledge_score = score_item("low", "No knowledge candidates generated.")

    return {
        "evidence_completeness": evidence_score,
        "hypothesis_coverage": hypothesis_score,
        "validation_depth": validation_score,
        "conclusion_confidence": confidence_score,
        "knowledge_reusability": knowledge_score,
    }


def review_suggestions(score: Dict[str, Dict[str, str]], analysis: Dict[str, Any]) -> List[str]:
    conclusion = analysis.get("conclusion_summary") or {}
    is_baseline = conclusion.get("primary_cause_category") == "baseline"
    suggestions: List[str] = []
    if score["evidence_completeness"]["level"] != "high":
        suggestions.append("Add stronger evidence extraction or evidence-to-conclusion linking.")
    if score["hypothesis_coverage"]["level"] != "high" and not is_baseline:
        suggestions.append("Add scenario-specific hypothesis rules or counter-hypotheses.")
    if score["validation_depth"]["level"] != "high":
        suggestions.append("Add explicit validation actions for supported and refuted hypotheses.")
    if score["knowledge_reusability"]["level"] != "high" and not is_baseline:
        suggestions.append("Improve knowledge candidate generation from matching assets and incident evidence.")
    return suggestions


def command_review(args: argparse.Namespace) -> int:
    incident_dir = ROOT / args.incident_dir
    analysis_file = incident_dir / "analysis.yaml"
    if not analysis_file.exists():
        print("ERROR: missing analysis.yaml: %s" % analysis_file, file=sys.stderr)
        return 1
    analysis = load_yaml(analysis_file)
    score = review_score_from_analysis(analysis)
    level = overall_level(score)
    review = {
        "review": {
            "score": score,
            "overall": {"level": level, "reason": "Average of local review score dimensions."},
            "improvement_suggestions": review_suggestions(score, analysis),
            "regression_risks": [],
            "generated_at": now_iso(),
        }
    }
    write_yaml(incident_dir / "review.yaml", review)
    input_data = load_yaml(incident_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    output = adapter_output("review", incident_id, middleware, "completed", "local review completed", incident_dir)
    output["record_refs"].append({"name": "review", "path": str(incident_dir / "review.yaml"), "description": "local review result"})
    write_yaml(incident_dir / "review-adapter-output.yaml", output)
    print(str(incident_dir / "review.yaml"))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local midstack-triage plugin command prototype.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--middleware", required=True)
    start.add_argument("--customer-clue", required=True)
    start.add_argument("--namespace", default="")
    start.add_argument("--cluster-id", default="")
    start.add_argument("--incident-id")
    start.add_argument("--output-root", default=".local/incidents")
    start.add_argument("--environment-ip", action="append", default=[], help="Remote environment IP. May be repeated; the first IP is used as jump host.")
    start.add_argument("--username", default="")
    start.add_argument("--password", default="")
    start.add_argument("--port", type=int, default=22)
    start.set_defaults(func=command_start)

    analyse = subparsers.add_parser("analyse")
    input_source = analyse.add_mutually_exclusive_group(required=False)
    input_source.add_argument("--input-dir")
    input_source.add_argument("--remote-run-dir")
    input_source.add_argument("--remote-config", help="Run MongoDB remote smoke first, then analyse the generated remote run directory.")
    input_source.add_argument("--incident-dir", help="Run analyse from a started incident directory containing remote-config.yaml.")
    analyse.add_argument("--output-dir")
    analyse.add_argument("--output-root", default=".local/incidents")
    analyse.add_argument("--scenario", help="Override or supply scenario when analysing a remote run.")
    analyse.add_argument("--customer-clue", help="Override or supply customer clue when analysing a remote run.")
    analyse.add_argument("--remote-output-dir", default=".local/remote-runs")
    analyse.add_argument("--remote-namespace", default="")
    analyse.set_defaults(func=command_analyse)

    review = subparsers.add_parser("review")
    review.add_argument("--incident-dir", required=True)
    review.set_defaults(func=command_review)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
