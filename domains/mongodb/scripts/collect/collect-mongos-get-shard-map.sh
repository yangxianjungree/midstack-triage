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
import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

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


def blocked_output(
    output_file: str,
    script_id: str,
    started_at: str,
    summary: str,
    warnings: List[str],
    evidence_gaps: List[Dict[str, Any]],
    target: str = "mongos",
) -> None:
    finished_at = now_iso()
    payload = {
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
                    "name": "collect mongos shard map",
                    "target": target,
                    "method": "kubectl exec + mongosh getShardMap",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [],
            "blank_items": [],
            "evidence_gaps": evidence_gaps,
        },
        "warnings": warnings,
        "evidence_gaps": evidence_gaps,
    }
    write_yaml(output_file, payload)


def pod_score(pod: Dict[str, Any]) -> int:
    metadata = pod.get("metadata") or {}
    status = pod.get("status") or {}
    name = str(metadata.get("name") or "").lower()
    labels = metadata.get("labels") or {}
    label_text = " ".join([str(k).lower() + "=" + str(v).lower() for k, v in labels.items()])
    score = 0
    if status.get("phase") == "Running":
        score += 10
    if "mongos" in name:
        score += 20
    if "mongos" in label_text:
        score += 20
    return score


def resolve_mongos_pod(kubectl: str, namespace: str, target_ref: str, artifact_dir: str) -> str:
    if target_ref:
        return target_ref
    proc = subprocess.run(
        [kubectl, "get", "pods", "-n", namespace, "-o", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return ""
    raw_relpath = os.path.join("raw", "pods-for-mongos-resolution.json")
    raw_abspath = os.path.join(artifact_dir, raw_relpath)
    with open(raw_abspath, "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    payload = json.loads(proc.stdout or "{}")
    candidates = sorted(payload.get("items") or [], key=pod_score, reverse=True)
    for pod in candidates:
        if pod_score(pod) >= 20:
            return str((pod.get("metadata") or {}).get("name") or "")
    return ""


def parse_shard_map(raw: Dict[str, Any]) -> Dict[str, Any]:
    shard_records: List[Dict[str, Any]] = []
    map_obj = raw.get("map") if isinstance(raw.get("map"), dict) else {}
    for key, value in map_obj.items():
        if key in ("config", "configsvr", "configServer"):
            continue
        hosts = []
        replica_set_id = ""
        if isinstance(value, str):
            if "/" in value:
                replica_set_id, host_text = value.split("/", 1)
                hosts = [item.strip() for item in host_text.split(",") if item.strip()]
            else:
                hosts = [value]
        elif isinstance(value, list):
            hosts = [str(item) for item in value]
        elif isinstance(value, dict):
            replica_set_id = str(value.get("_id") or value.get("replicaSet") or key)
            host_value = value.get("host") or value.get("hosts") or []
            if isinstance(host_value, str):
                hosts = [item.strip() for item in host_value.split(",") if item.strip()]
            elif isinstance(host_value, list):
                hosts = [str(item) for item in host_value]
        shard_records.append(
            {
                "shard_id": str(key),
                "replica_set_id": replica_set_id or str(key),
                "component_ref": str(key),
                "host_summary": hosts,
            }
        )
    config_value = map_obj.get("config") or map_obj.get("configsvr") or map_obj.get("configServer")
    return {
        "config_server_ref": str(config_value or ""),
        "shards": shard_records,
        "raw_ok": raw.get("ok"),
    }


def extract_json(stdout: str) -> Dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict):
            return data
    raise ValueError("mongosh output did not contain a JSON object")


def read_secret_value(kubectl: str, namespace: str, secret_ref: Any) -> Tuple[str, str]:
    if not isinstance(secret_ref, dict):
        return "", "secret_ref must be an object"
    name = str(secret_ref.get("name") or "")
    key = str(secret_ref.get("key") or secret_ref.get("password_key") or "password")
    secret_namespace = str(secret_ref.get("namespace") or namespace)
    if not name:
        return "", "secret_ref.name is required"
    proc = subprocess.run(
        [kubectl, "get", "secret", "-n", secret_namespace, name, "-o", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return "", proc.stderr.strip() or "kubectl get secret returned non-zero exit code"
    try:
        payload = json.loads(proc.stdout or "{}")
        encoded = ((payload.get("data") or {}).get(key)) or ""
        if not encoded:
            return "", "secret key not found: %s" % key
        return base64.b64decode(encoded).decode("utf-8"), ""
    except Exception as exc:
        return "", "failed to decode secret value: %s" % exc


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)

    script_id = str(context.get("script_id") or "mongodb.collect.mongos.get_shard_map")
    namespace = context.get("namespace") or ((context.get("targets") or {}).get("namespace"))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(artifact_dir, exist_ok=True)
    raw_dir = os.path.join(artifact_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    capabilities = context.get("capabilities") or {}
    if not capabilities.get("kubectl_available", False):
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl is not available in current runtime",
            ["capabilities.kubectl_available is false"],
            [
                {
                    "gap": "mongos shard map not collected",
                    "related_stage": "signal_collection",
                    "why_important": "shard map is required to understand MongoDB sharded topology",
                }
            ],
        )
        return 0
    if not capabilities.get("kubectl_exec_available", False):
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl exec is not available in current runtime",
            ["capabilities.kubectl_exec_available is false"],
            [
                {
                    "gap": "mongos shard map not collected",
                    "related_stage": "signal_collection",
                    "why_important": "mongos command must be executed inside a target Pod",
                }
            ],
        )
        return 0

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl command not found in runtime environment",
            ["kubectl binary is missing"],
            [
                {
                    "gap": "mongos shard map not collected",
                    "related_stage": "signal_collection",
                    "why_important": "kubectl exec is required for mongos shard map collection",
                }
            ],
        )
        return 0

    targets = context.get("targets") or {}
    mongos_query = context.get("mongos_query") or {}
    shell = str(mongos_query.get("shell") or "mongosh")
    database = str(mongos_query.get("database") or "admin")
    username = str(mongos_query.get("username") or "")
    password = str(mongos_query.get("password") or "")
    password_env = str(mongos_query.get("password_env") or "")
    password_file_env = str(mongos_query.get("password_file_env") or "")
    secret_ref = mongos_query.get("secret_ref") or {}
    auth_database = str(mongos_query.get("auth_database") or "admin")
    target_pod = resolve_mongos_pod(kubectl, str(namespace), str(targets.get("mongos_pod_ref") or ""), artifact_dir)
    if not target_pod:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "mongos pod could not be resolved",
            ["targets.mongos_pod_ref is empty and no mongos pod was detected"],
            [
                {
                    "gap": "mongos target pod not resolved",
                    "related_stage": "signal_collection",
                    "why_important": "shard map must be collected from a mongos Pod",
                }
            ],
        )
        return 0

    js = (
        'const result = db.getSiblingDB("%s").runCommand({getShardMap: 1}); '
        'print(JSON.stringify(result));'
    ) % database
    if username and not (password or password_env or password_file_env) and secret_ref:
        password, secret_error = read_secret_value(kubectl, str(namespace), secret_ref)
        if secret_error:
            blocked_output(
                output_file,
                script_id,
                started_at,
                "MongoDB Secret password could not be resolved",
                [secret_error],
                [
                    {
                        "gap": "MongoDB authentication secret not resolved",
                        "related_stage": "signal_collection",
                        "why_important": "authenticated mongos command cannot run without a password source",
                    }
                ],
                target=target_pod,
            )
            return 0

    shell_candidates = [shell]
    if shell == "mongosh":
        shell_candidates.append("mongo")
    resolve_lines = []
    for candidate in shell_candidates:
        resolve_lines.append('command -v %s >/dev/null 2>&1 && MONGO_SHELL=$(command -v %s)' % (shlex.quote(candidate), shlex.quote(candidate)))
    resolve_shell = (
        'MONGO_SHELL=""; '
        + '; '.join(['[ -z "$MONGO_SHELL" ] && ' + line for line in resolve_lines])
        + '; [ -n "$MONGO_SHELL" ] || { echo "mongo shell not found" >&2; exit 127; }; '
    )

    if username and password_file_env:
        inner_cmd = (
            "%s MONGO_PASSWORD=$(cat \"$%s\"); "
            "\"$MONGO_SHELL\" --quiet --username %s --password \"$MONGO_PASSWORD\" --authenticationDatabase %s --eval %s"
            % (
                resolve_shell,
                password_file_env,
                shlex.quote(username),
                shlex.quote(auth_database),
                shlex.quote(js),
            )
        )
        cmd = [kubectl, "exec", "-n", str(namespace), target_pod, "--", "bash", "-c", inner_cmd]
    elif username and password_env:
        inner_cmd = (
            "%s \"$MONGO_SHELL\" --quiet --username %s --password \"$%s\" --authenticationDatabase %s --eval %s"
            % (
                resolve_shell,
                shlex.quote(username),
                password_env,
                shlex.quote(auth_database),
                shlex.quote(js),
            )
        )
        cmd = [kubectl, "exec", "-n", str(namespace), target_pod, "--", "bash", "-c", inner_cmd]
    elif username and password:
        inner_cmd = (
            "%s \"$MONGO_SHELL\" --quiet --username %s --password %s --authenticationDatabase %s --eval %s"
            % (
                resolve_shell,
                shlex.quote(username),
                shlex.quote(password),
                shlex.quote(auth_database),
                shlex.quote(js),
            )
        )
        cmd = [kubectl, "exec", "-n", str(namespace), target_pod, "--", "bash", "-c", inner_cmd]
    else:
        inner_cmd = '%s "$MONGO_SHELL" --quiet --eval %s' % (resolve_shell, shlex.quote(js))
        cmd = [kubectl, "exec", "-n", str(namespace), target_pod, "--", "bash", "-c", inner_cmd]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    stdout_relpath = os.path.join("raw", "mongos-get-shard-map.stdout")
    stderr_relpath = os.path.join("raw", "mongos-get-shard-map.stderr")
    with open(os.path.join(artifact_dir, stdout_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    with open(os.path.join(artifact_dir, stderr_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stderr)

    artifacts = [
        {
            "path": stdout_relpath,
            "kind": "raw_command_output",
            "description": "raw mongos getShardMap stdout",
        },
        {
            "path": stderr_relpath,
            "kind": "raw_command_error",
            "description": "raw mongos getShardMap stderr",
        },
    ]

    if proc.returncode != 0:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl exec mongos getShardMap failed",
            [proc.stderr.strip() or "mongos getShardMap command returned non-zero exit code"],
            [
                {
                    "gap": "mongos shard map command failed",
                    "related_stage": "signal_collection",
                    "why_important": "shard map is required to understand MongoDB sharded topology",
                }
            ],
            target=target_pod,
        )
        return 0

    try:
        raw_result = extract_json(proc.stdout)
    except ValueError as exc:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "mongos getShardMap output could not be parsed as JSON",
            [str(exc)],
            [
                {
                    "gap": "mongos shard map output not parsed",
                    "related_stage": "signal_collection",
                    "why_important": "unparsed shard map cannot be used for topology correlation",
                }
            ],
            target=target_pod,
        )
        return 0

    raw_json_relpath = os.path.join("raw", "mongos-get-shard-map.json")
    with open(os.path.join(artifact_dir, raw_json_relpath), "w", encoding="utf-8") as fh:
        json.dump(raw_result, fh, indent=2, sort_keys=False)
        fh.write("\n")
    artifacts.append(
        {
            "path": raw_json_relpath,
            "kind": "raw_command_output",
            "description": "parsed JSON result from mongos getShardMap",
        }
    )

    finished_at = now_iso()
    parsed = parse_shard_map(raw_result)
    shard_map = {
        "source_component_ref": "mongos-router",
        "source_pod_ref": target_pod,
        "source_method": "mongos getShardMap",
        "config_server_ref": parsed["config_server_ref"],
        "shards": parsed["shards"],
        "raw_ok": parsed["raw_ok"],
        "collection_status": "success",
        "collected_at": finished_at,
    }
    warnings: List[str] = []
    evidence_gaps: List[Dict[str, Any]] = []
    if not parsed["shards"]:
        warnings.append("getShardMap returned no shard entries")
        evidence_gaps.append(
            {
                "gap": "shard map has no shard entries",
                "related_stage": "signal_collection",
                "why_important": "empty shard map may indicate command incompatibility or unexpected topology",
            }
        )

    status = "partial" if evidence_gaps else "success"
    summary = "collected shard map from %s with %d shard record(s)" % (target_pod, len(parsed["shards"]))
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "shard_map": shard_map,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect mongos shard map",
                    "target": target_pod,
                    "method": "kubectl exec + mongosh getShardMap",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [
                {
                    "item": "shard_map",
                    "source": target_pod,
                    "note": "%d shard record(s)" % len(parsed["shards"]),
                }
            ],
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
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
