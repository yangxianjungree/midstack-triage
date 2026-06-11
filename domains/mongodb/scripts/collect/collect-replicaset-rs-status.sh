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
import re
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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def blocked_output(
    output_file: str,
    script_id: str,
    started_at: str,
    summary: str,
    warnings: List[str],
    evidence_gaps: List[Dict[str, Any]],
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
                    "name": "collect replica set rs.status",
                    "target": "replicaset",
                    "method": "kubectl exec + rs.status",
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
        score += 5
    if "configsvr" in name or "shard" in name:
        score += 20
    if "mongos" in name or "operator" in name:
        score -= 50
    if "component=configsvr" in label_text or "component=shard" in label_text or "component=shardsvr" in label_text:
        score += 20
    return score


def resolve_target_pods(kubectl: str, namespace: str, target_refs: List[str], artifact_dir: str) -> List[str]:
    if target_refs:
        return target_refs
    proc = subprocess.run(
        [kubectl, "get", "pods", "-n", namespace, "-o", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return []
    raw_relpath = os.path.join("raw", "pods-for-replicaset-resolution.json")
    with open(os.path.join(artifact_dir, raw_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    payload = json.loads(proc.stdout or "{}")
    pods = sorted(payload.get("items") or [], key=pod_score, reverse=True)
    result: List[str] = []
    for pod in pods:
        if pod_score(pod) < 20:
            continue
        name = str((pod.get("metadata") or {}).get("name") or "")
        if name and name not in result:
            result.append(name)
    return result


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
    raise ValueError("rs.status output did not contain a JSON object")


def member_record(member: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": member.get("name"),
        "health": member.get("health"),
        "state": member.get("state"),
        "state_str": member.get("stateStr"),
        "uptime": member.get("uptime"),
        "optime_date": member.get("optimeDate"),
        "last_applied_wall_time": member.get("lastAppliedWallTime"),
        "last_durable_wall_time": member.get("lastDurableWallTime"),
        "sync_source_host": member.get("syncSourceHost"),
        "election_date": member.get("electionDate"),
        "config_version": member.get("configVersion"),
        "config_term": member.get("configTerm"),
        "self": bool(member.get("self")),
    }


def status_record(source_pod: str, raw: Dict[str, Any], collected_at: str) -> Dict[str, Any]:
    members = raw.get("members") or []
    self_members = [member for member in members if member.get("self")]
    self_member = self_members[0] if self_members else {}
    return {
        "replica_set_id": raw.get("set"),
        "source_pod_ref": source_pod,
        "source_method": "rs.status",
        "date": raw.get("date"),
        "my_state": raw.get("myState"),
        "term": raw.get("term"),
        "heartbeat_interval_millis": raw.get("heartbeatIntervalMillis"),
        "majority_vote_count": raw.get("majorityVoteCount"),
        "write_majority_count": raw.get("writeMajorityCount"),
        "voting_members_count": raw.get("votingMembersCount"),
        "writable_voting_members_count": raw.get("writableVotingMembersCount"),
        "self_member": member_record(self_member) if self_member else {},
        "members": [member_record(member) for member in members],
        "raw_ok": raw.get("ok"),
        "collection_status": "success",
        "collected_at": collected_at,
    }


def build_inner_command(shell: str, username: str, password: str, password_env: str, password_file_env: str, auth_database: str, js: str) -> str:
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
        return (
            "%s MONGO_PASSWORD=$(cat \"$%s\"); "
            "\"$MONGO_SHELL\" --quiet --username %s --password \"$MONGO_PASSWORD\" --authenticationDatabase %s --eval %s"
            % (resolve_shell, password_file_env, shlex.quote(username), shlex.quote(auth_database), shlex.quote(js))
        )
    if username and password_env:
        return (
            "%s \"$MONGO_SHELL\" --quiet --username %s --password \"$%s\" --authenticationDatabase %s --eval %s"
            % (resolve_shell, shlex.quote(username), password_env, shlex.quote(auth_database), shlex.quote(js))
        )
    if username and password:
        return (
            "%s \"$MONGO_SHELL\" --quiet --username %s --password %s --authenticationDatabase %s --eval %s"
            % (resolve_shell, shlex.quote(username), shlex.quote(password), shlex.quote(auth_database), shlex.quote(js))
        )
    return '%s "$MONGO_SHELL" --quiet --eval %s' % (resolve_shell, shlex.quote(js))


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

    script_id = str(context.get("script_id") or "mongodb.collect.replicaset.rs_status")
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
            [{"gap": "rs.status not collected", "related_stage": "signal_collection", "why_important": "replica member state is required for MongoDB diagnosis"}],
        )
        return 0
    if not capabilities.get("kubectl_exec_available", False):
        blocked_output(
            output_file,
            script_id,
            started_at,
            "kubectl exec is not available in current runtime",
            ["capabilities.kubectl_exec_available is false"],
            [{"gap": "rs.status not collected", "related_stage": "signal_collection", "why_important": "rs.status must be executed inside mongod Pods"}],
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
            [{"gap": "rs.status not collected", "related_stage": "signal_collection", "why_important": "kubectl exec is required for rs.status collection"}],
        )
        return 0

    targets = context.get("targets") or {}
    query = context.get("replicaset_query") or {}
    mongos_query = context.get("mongos_query") or {}
    shell = str(query.get("shell") or mongos_query.get("shell") or "mongosh")
    username = str(query.get("username") or mongos_query.get("username") or "")
    password = str(query.get("password") or mongos_query.get("password") or "")
    password_env = str(query.get("password_env") or mongos_query.get("password_env") or "")
    password_file_env = str(query.get("password_file_env") or mongos_query.get("password_file_env") or "")
    secret_ref = query.get("secret_ref") or mongos_query.get("secret_ref") or {}
    auth_database = str(query.get("auth_database") or mongos_query.get("auth_database") or "admin")
    target_pods = resolve_target_pods(kubectl, str(namespace), [str(item) for item in (targets.get("pod_refs") or [])], artifact_dir)
    if not target_pods:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "replica set member pods could not be resolved",
            ["no configsvr or shard mongod pods were detected"],
            [{"gap": "replica set target pods not resolved", "related_stage": "signal_collection", "why_important": "rs.status must be collected from mongod Pods"}],
        )
        return 0

    js = 'const result = rs.status(); print(JSON.stringify(result));'
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
                        "why_important": "authenticated rs.status command cannot run without a password source",
                    }
                ],
            )
            return 0

    statuses: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = [
        {
            "path": os.path.join("raw", "pods-for-replicaset-resolution.json"),
            "kind": "raw_command_output",
            "description": "raw kubectl get pods output used to resolve replica set member pods",
        }
    ]
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for pod in target_pods:
        inner_cmd = build_inner_command(shell, username, password, password_env, password_file_env, auth_database, js)
        cmd = [kubectl, "exec", "-n", str(namespace), pod, "--", "bash", "-c", inner_cmd]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        base = safe_name(pod)
        stdout_relpath = os.path.join("raw", "%s-rs-status.stdout" % base)
        stderr_relpath = os.path.join("raw", "%s-rs-status.stderr" % base)
        with open(os.path.join(artifact_dir, stdout_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        with open(os.path.join(artifact_dir, stderr_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
        artifacts.append({"path": stdout_relpath, "kind": "raw_command_output", "description": "raw rs.status stdout from %s" % pod})
        artifacts.append({"path": stderr_relpath, "kind": "raw_command_error", "description": "raw rs.status stderr from %s" % pod})
        if proc.returncode != 0:
            failed_items.append({"item": "pod/%s" % pod, "reason": proc.stderr.strip() or "rs.status returned non-zero exit code", "impact": "missing replica set state from this member"})
            evidence_gaps.append(
                {
                    "gap": "rs.status not collected from pod/%s" % pod,
                    "gap_type": "expected_gap",
                    "related_stage": "signal_collection",
                    "why_important": "A failed member often cannot provide its own rs.status; healthy peer fallback should be used when available.",
                    "recommended_action": "use rs.status from another healthy member in the same replica set",
                }
            )
            continue
        try:
            raw = extract_json(proc.stdout)
        except ValueError as exc:
            failed_items.append({"item": "pod/%s" % pod, "reason": str(exc), "impact": "unparsed replica set state from this member"})
            evidence_gaps.append(
                {
                    "gap": "rs.status output not parsed from pod/%s" % pod,
                    "gap_type": "expected_gap",
                    "related_stage": "signal_collection",
                    "why_important": "A single unparsed member state should not block diagnosis if another healthy peer provides replica set state.",
                    "recommended_action": "use rs.status from another healthy member in the same replica set",
                }
            )
            continue
        raw_json_relpath = os.path.join("raw", "%s-rs-status.json" % base)
        with open(os.path.join(artifact_dir, raw_json_relpath), "w", encoding="utf-8") as fh:
            json.dump(raw, fh, indent=2, sort_keys=False)
            fh.write("\n")
        artifacts.append({"path": raw_json_relpath, "kind": "raw_command_output", "description": "parsed rs.status JSON from %s" % pod})
        statuses.append(status_record(pod, raw, now_iso()))

    finished_at = now_iso()
    successful_items = [
        {
            "item": "pod/%s" % item["source_pod_ref"],
            "source": "rs.status",
            "note": "replica_set=%s self_state=%s" % (item.get("replica_set_id"), (item.get("self_member") or {}).get("state_str")),
        }
        for item in statuses
    ]
    if not statuses:
        status = "blocked"
        summary = "no rs.status result collected from replica set member pods"
    elif failed_items:
        status = "partial"
        summary = "collected %d rs.status result(s), %d failed" % (len(statuses), len(failed_items))
    else:
        status = "success"
        summary = "collected %d rs.status result(s)" % len(statuses)

    if not statuses:
        warnings.append("all rs.status collection attempts failed")
        evidence_gaps.append(
            {
                "gap": "rs.status not collected from any healthy replica set peer",
                "gap_type": "critical_gap",
                "related_stage": "signal_collection",
                "why_important": "Without any peer rs.status result, replica set internal state cannot be validated.",
                "recommended_action": "identify a healthy member Pod with mongosh/mongo access and rerun rs.status",
                "affects": ["mechanism", "root_cause"],
            }
        )

    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "replica_members": statuses,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect replica set rs.status",
                    "target": ",".join(target_pods),
                    "method": "kubectl exec + rs.status",
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": failed_items,
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
