#!/usr/bin/env python3

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]


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


def command_start(args: argparse.Namespace) -> int:
    incident_id = args.incident_id or "%s-%s" % (args.middleware, datetime.now().strftime("%Y%m%d-%H%M%S"))
    output_dir = ROOT / args.output_root / incident_id
    status = "ready" if args.middleware and args.customer_clue else "blocked"
    created_at = now_iso()
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
        },
    )
    write_yaml(
        output_dir / "input.yaml",
        {
            "middleware": args.middleware,
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "customer_clue": args.customer_clue,
            "input_source": "local-cli",
            "received_at": created_at,
        },
    )
    output = adapter_output("start", incident_id, args.middleware, status, "local incident %s is %s" % (incident_id, status), output_dir)
    if status == "ready":
        output["next_actions"] = ["run analyse with --incident-dir %s" % output_dir]
    else:
        output["blocking_items"] = [{"code": "missing_input", "message": "middleware and customer_clue are required", "required_user_action": "rerun start with required fields"}]
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


def merge_dict(target: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge_dict(target[key], value)
        else:
            target[key] = value
    return target


def append_report_patch(report: Dict[str, Any], patch: Dict[str, Any]) -> None:
    for key, value in patch.items():
        if key in ("collection_actions", "successful_items", "failed_items", "blank_items", "evidence_gaps"):
            existing = report.setdefault(key, [])
            if isinstance(existing, list) and isinstance(value, list):
                existing.extend(value)
            else:
                report[key] = value
        elif isinstance(value, dict) and isinstance(report.get(key), dict):
            merge_dict(report[key], value)
        else:
            report[key] = value


def first_context(remote_run_dir: Path) -> Dict[str, Any]:
    for path in sorted(remote_run_dir.glob("*/context.yaml")):
        return load_yaml(path)
    return {}


def script_output_dirs(remote_run_dir: Path) -> List[Path]:
    return sorted(path for path in remote_run_dir.iterdir() if path.is_dir() and (path / "output.yaml").exists())


def build_input_from_remote_run(remote_run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]:
    context = first_context(remote_run_dir)
    incident_id = str(context.get("incident_id") or remote_run_dir.name)
    return {
        "incident_id": incident_id,
        "middleware": str(context.get("middleware") or "mongodb"),
        "scenario": args.scenario or str(context.get("scenario") or "unknown"),
        "namespace": str(context.get("namespace") or ""),
        "cluster_id": str(context.get("cluster_id") or ""),
        "customer_clue": args.customer_clue or str(context.get("customer_clue") or "remote run script outputs"),
        "input_source": "remote-run-dir",
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
        if isinstance(output.get("structured_record_patch"), dict):
            merge_dict(structured_record, output["structured_record_patch"])
        if isinstance(output.get("signal_bundle_patch"), dict):
            merge_dict(signal_bundle, output["signal_bundle_patch"])
        if isinstance(output.get("collection_report_patch"), dict):
            append_report_patch(collection_report, output["collection_report_patch"])

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


def command_analyse(args: argparse.Namespace) -> int:
    output_dir = ROOT / args.output_dir
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
    start.set_defaults(func=command_start)

    analyse = subparsers.add_parser("analyse")
    input_source = analyse.add_mutually_exclusive_group(required=True)
    input_source.add_argument("--input-dir")
    input_source.add_argument("--remote-run-dir")
    input_source.add_argument("--remote-config", help="Run MongoDB remote smoke first, then analyse the generated remote run directory.")
    analyse.add_argument("--output-dir", required=True)
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
