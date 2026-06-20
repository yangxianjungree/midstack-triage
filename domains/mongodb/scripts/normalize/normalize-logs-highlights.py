#!/usr/bin/env python3

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


PATTERNS = [
    ("fatal", re.compile(r"\b(fatal|panic|segmentation fault)\b", re.I)),
    ("error", re.compile(r"\b(error|exception|failed|failure)\b", re.I)),
    ("warning", re.compile(r"\b(warn|warning)\b", re.I)),
    ("timeout", re.compile(r"\b(timeout|timed out|deadline)\b", re.I)),
    ("connection", re.compile(r"\b(connection|network|socket|refused|reset)\b", re.I)),
    ("auth", re.compile(r"\b(auth|authentication|authorized|unauthorized|permission)\b", re.I)),
    ("election", re.compile(r"\b(election|primary|secondary|stepdown|term)\b", re.I)),
    ("replication", re.compile(r"\b(replication|oplog|sync source|rollback)\b", re.I)),
    ("resource", re.compile(r"\b(oom|killed|memory|disk|no space|too many open files)\b", re.I)),
]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        if yaml is not None:
            data = yaml.safe_load(fh) or {}
        else:
            data = json.load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("context-file must contain a YAML object")
    return data


def ensure_parent(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def write_yaml(path: str, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as fh:
        if yaml is not None:
            yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)
        else:
            json.dump(payload, fh, indent=2, sort_keys=False)
            fh.write("\n")


def parse_args(argv: List[str]) -> Tuple[str, str, str]:
    context_file = ""
    output_file = ""
    artifact_dir = ""
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--context-file":
            context_file = argv[index + 1]
            index += 2
        elif arg == "--output-file":
            output_file = argv[index + 1]
            index += 2
        elif arg == "--artifact-dir":
            artifact_dir = argv[index + 1]
            index += 2
        elif arg in ("-h", "--help"):
            print("Usage: normalize-logs-highlights.py --context-file <path> --output-file <path> --artifact-dir <path>")
            raise SystemExit(0)
        else:
            raise ValueError("unknown argument: %s" % arg)
    if not context_file or not output_file or not artifact_dir:
        raise ValueError("missing required arguments")
    return context_file, output_file, artifact_dir


def make_action_id(script_id: str) -> str:
    return script_id.replace(".", "-")


def artifact_dirs(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def iter_log_files(inputs: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    result: List[Tuple[str, str, str]] = []
    dirs = ((inputs.get("log_artifact_dirs") or {}) if isinstance(inputs.get("log_artifact_dirs") or {}, dict) else {})
    for log_type, configured_dirs in dirs.items():
        for artifact_dir in artifact_dirs(configured_dirs):
            raw_dir = os.path.join(artifact_dir, "raw", "logs-%s" % log_type)
            if not os.path.isdir(raw_dir):
                continue
            for name in sorted(os.listdir(raw_dir)):
                if not name.endswith(".log"):
                    continue
                pod_ref = name[:-4]
                result.append((str(log_type), pod_ref, os.path.join(raw_dir, name)))
    return result


def classify(line: str) -> str:
    for label, pattern in PATTERNS:
        if pattern.search(line):
            return label
    return ""


def clean_line(line: str) -> str:
    return ANSI_RE.sub("", line).rstrip("\n")


def scan_file(log_type: str, pod_ref: str, path: str, per_file_limit: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    stats = {
        "pod_ref": pod_ref,
        "log_type": log_type,
        "path": path,
        "line_count": 0,
        "highlight_count": 0,
    }
    highlights: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            stats["line_count"] += 1
            message = clean_line(line)
            category = classify(message)
            if not category:
                continue
            stats["highlight_count"] += 1
            if len(highlights) >= per_file_limit:
                continue
            highlights.append(
                {
                    "pod_ref": pod_ref,
                    "log_type": log_type,
                    "line_no": line_no,
                    "category": category,
                    "message": message[:1000],
                }
            )
    return stats, highlights


def main() -> int:
    context_file, output_file, artifact_dir = parse_args(sys.argv[1:])
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.normalize.logs.highlights")
    inputs = context.get("inputs") or {}
    normalize_query = context.get("normalize_query") or {}
    per_file_limit = int(normalize_query.get("per_file_highlight_limit", 50) or 50)
    total_limit = int(normalize_query.get("total_highlight_limit", 500) or 500)

    os.makedirs(artifact_dir, exist_ok=True)
    processed_dir = os.path.join(artifact_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    log_files = iter_log_files(inputs)
    warnings: List[str] = []
    evidence_gaps: List[Dict[str, Any]] = []
    if not log_files:
        evidence_gaps.append(
            {
                "gap": "no raw log artifact directories found",
                "related_stage": "signal_governance",
                "why_important": "log highlights require current or previous raw logs",
            }
        )

    stats: List[Dict[str, Any]] = []
    highlights: List[Dict[str, Any]] = []
    for log_type, pod_ref, path in log_files:
        file_stats, file_highlights = scan_file(log_type, pod_ref, path, per_file_limit)
        stats.append(file_stats)
        highlights.extend(file_highlights)
    highlights = highlights[:total_limit]

    processed_relpath = os.path.join("processed", "log-highlights.json")
    with open(os.path.join(artifact_dir, processed_relpath), "w", encoding="utf-8") as fh:
        json.dump({"stats": stats, "highlights": highlights}, fh, indent=2, sort_keys=False)
        fh.write("\n")

    finished_at = now_iso()
    status = "blocked" if not log_files else "success"
    summary = "extracted %d log highlight(s) from %d log file(s)" % (len(highlights), len(log_files))
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": [
            {
                "path": processed_relpath,
                "kind": "processed_log_summary",
                "description": "log highlight summary extracted from current and previous raw logs",
            }
        ],
        "structured_record_patch": {
            "details": {
                "processed_logs": {
                    "stats": stats,
                    "highlights": highlights,
                    "highlight_count": len(highlights),
                    "source_log_file_count": len(log_files),
                    "collected_at": finished_at,
                }
            }
        },
        "signal_bundle_patch": {
            "log_highlights": highlights,
        },
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "normalize log highlights",
                    "target": "raw_logs",
                    "method": "pattern classification over raw log artifacts",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [
                {
                    "item": "log_highlights",
                    "source": "%d log file(s)" % len(log_files),
                    "note": "%d highlight(s)" % len(highlights),
                }
            ] if log_files else [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": warnings,
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, IndexError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
