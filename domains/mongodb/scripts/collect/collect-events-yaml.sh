#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: $0 --context-file <path> --output-file <path> --artifact-dir <path>" >&2
}

CONTEXT_FILE=""
OUTPUT_FILE=""
ARTIFACT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context-file)
      CONTEXT_FILE="${2:-}"
      shift 2
      ;;
    --output-file)
      OUTPUT_FILE="${2:-}"
      shift 2
      ;;
    --artifact-dir)
      ARTIFACT_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CONTEXT_FILE" || -z "$OUTPUT_FILE" || -z "$ARTIFACT_DIR" ]]; then
  usage
  exit 1
fi

python3 - "$CONTEXT_FILE" "$OUTPUT_FILE" "$ARTIFACT_DIR" <<'PY'
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


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


def make_action_id(script_id: str) -> str:
    return script_id.replace(".", "-")


def event_time(event: Dict[str, Any]) -> str:
    return str(
        event.get("lastTimestamp")
        or event.get("eventTime")
        or event.get("firstTimestamp")
        or ((event.get("metadata") or {}).get("creationTimestamp"))
        or ""
    )


def event_record(event: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    metadata = event.get("metadata") or {}
    involved = event.get("involvedObject") or event.get("regarding") or {}
    return {
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "type": event.get("type"),
        "reason": event.get("reason"),
        "message": event.get("message") or event.get("note"),
        "count": event.get("count") or event.get("series", {}).get("count"),
        "first_timestamp": event.get("firstTimestamp"),
        "last_timestamp": event_time(event),
        "source_component": ((event.get("source") or {}).get("component")) or ((event.get("reportingController"))),
        "involved_object": {
            "kind": involved.get("kind"),
            "name": involved.get("name"),
            "uid": involved.get("uid"),
            "api_version": involved.get("apiVersion"),
        },
        "collected_at": collected_at,
    }


def blocked_output(output_file: str, script_id: str, started_at: str, summary: str, warning: str) -> None:
    finished_at = now_iso()
    gap = {
        "gap": "kubernetes events not collected",
        "related_stage": "signal_collection",
        "why_important": "Events often contain scheduler, image pull, PVC binding and probe failure reasons",
    }
    write_yaml(
        output_file,
        {
            "script_id": script_id,
            "status": "blocked",
            "summary": summary,
            "started_at": started_at,
            "finished_at": finished_at,
            "artifacts": [],
            "structured_record_patch": {},
            "signal_bundle_patch": {},
            "collection_report_patch": {
                "collection_actions": [
                    {
                        "action_id": make_action_id(script_id),
                        "name": "collect kubernetes events",
                        "target": "events",
                        "method": "kubectl get events -o json",
                        "status": "blocked",
                        "performed_at": finished_at,
                    }
                ],
                "successful_items": [],
                "failed_items": [],
                "blank_items": [],
                "evidence_gaps": [gap],
            },
            "warnings": [warning],
            "evidence_gaps": [gap],
        },
    )


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.events.yaml")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", False):
        blocked_output(output_file, script_id, started_at, "kubectl is not available in current runtime", "capabilities.kubectl_available is false")
        return 0

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_output(output_file, script_id, started_at, "kubectl command not found in runtime environment", "kubectl binary is missing")
        return 0

    os.makedirs(artifact_dir, exist_ok=True)
    raw_dir = os.path.join(artifact_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    cmd = [kubectl, "get", "events", "-n", str(namespace), "-o", "json"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if proc.returncode != 0:
        blocked_output(output_file, script_id, started_at, "kubectl get events failed", proc.stderr.strip() or "kubectl get events returned non-zero")
        return 0

    raw_relpath = os.path.join("raw", "events-raw.json")
    with open(os.path.join(artifact_dir, raw_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)

    payload = json.loads(proc.stdout or "{}")
    finished_at = now_iso()
    records = [event_record(item, finished_at) for item in (payload.get("items") or [])]
    warning_records = [item for item in records if item.get("type") == "Warning"]

    write_yaml(
        output_file,
        {
            "script_id": script_id,
            "status": "success",
            "summary": "collected %d Kubernetes event record(s) in namespace %s" % (len(records), namespace),
            "started_at": started_at,
            "finished_at": finished_at,
            "artifacts": [
                {
                    "path": raw_relpath,
                    "kind": "raw_command_output",
                    "description": "raw kubectl get events -o json output",
                }
            ],
            "structured_record_patch": {
                "details": {
                    "events": records,
                }
            },
            "signal_bundle_patch": {},
            "collection_report_patch": {
                "collection_actions": [
                    {
                        "action_id": make_action_id(script_id),
                        "name": "collect kubernetes events",
                        "target": namespace,
                        "method": "kubectl get events -o json",
                        "status": "success",
                        "performed_at": finished_at,
                    }
                ],
                "successful_items": [
                    {
                        "item": "events",
                        "source": "kubectl get events -o json",
                        "note": "%d total event(s), %d warning event(s)" % (len(records), len(warning_records)),
                    }
                ],
                "failed_items": [],
                "blank_items": [] if records else [{"item": "events", "reason": "no events returned"}],
                "evidence_gaps": [],
            },
            "warnings": [],
            "evidence_gaps": [],
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
