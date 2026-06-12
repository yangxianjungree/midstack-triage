#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def parse_args(argv: List[str]) -> Tuple[str, str, str]:
    context_file = ""
    output_file = ""
    artifact_dir = ""
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--context-file":
            context_file = argv[index + 1]
            index += 2
        elif token == "--output-file":
            output_file = argv[index + 1]
            index += 2
        elif token == "--artifact-dir":
            artifact_dir = argv[index + 1]
            index += 2
        else:
            raise ValueError("unknown argument: %s" % token)
    if not context_file or not output_file or not artifact_dir:
        raise ValueError("missing --context-file, --output-file, or --artifact-dir")
    return context_file, output_file, artifact_dir


def load_data(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        if yaml is not None:
            data = yaml.safe_load(fh) or {}
        else:
            data = json.load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("context-file must contain an object")
    return data


def write_data(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        if yaml is not None:
            yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)
        else:
            json.dump(payload, fh, indent=2, sort_keys=False)


def blocked_output(context: Dict[str, Any], reason: str) -> Dict[str, Any]:
    started_at = now_iso()
    return {
        "script_id": str(context.get("script_id") or "pulsar.collect.pods.state"),
        "status": "blocked",
        "summary": reason,
        "started_at": started_at,
        "finished_at": now_iso(),
        "artifacts": [],
        "structured_record_patch": {
            "summary": {"pods_collection_status": "blocked"},
            "details": {"pods": {"status": "blocked", "reason": reason}},
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "script_id": str(context.get("script_id") or "pulsar.collect.pods.state"),
                    "status": "blocked",
                    "summary": reason,
                }
            ],
            "blank_items": [str(context.get("script_id") or "pulsar.collect.pods.state")],
        },
        "warnings": [],
        "evidence_gaps": [
            {
                "gap": reason,
                "gap_type": "expected_gap",
                "related_stage": "collect",
                "why_important": "Pod state is required to map backlog symptoms to broker and bookie objects.",
            }
        ],
    }


def main() -> int:
    context_file, output_file, artifact_dir = parse_args(sys.argv[1:])
    os.makedirs(artifact_dir, exist_ok=True)
    context = load_data(context_file)
    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", True):
        write_data(output_file, blocked_output(context, "kubectl is not available in the provided context"))
        return 0
    write_data(
        output_file,
        blocked_output(context, "live kubectl collection is not implemented in the Pulsar MVP script yet"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
