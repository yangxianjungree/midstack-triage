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


MONGO_CONTAINER_CANDIDATES = ("mongod", "mongo", "mongodb", "mongos")


def pod_name(pod: Dict[str, Any]) -> str:
    return str(((pod.get("metadata") or {}).get("name") or ""))


def pod_is_running(pod: Dict[str, Any]) -> bool:
    return str(((pod.get("status") or {}).get("phase") or "")) == "Running"


def pod_is_ready(pod: Dict[str, Any]) -> bool:
    for item in ((pod.get("status") or {}).get("conditions") or []):
        if str(item.get("type") or "") == "Ready" and str(item.get("status") or "") == "True":
            return True
    return False


def is_mongos_pod(pod: Dict[str, Any]) -> bool:
    name = pod_name(pod).lower()
    labels = (pod.get("metadata") or {}).get("labels") or {}
    label_text = " ".join([str(k).lower() + "=" + str(v).lower() for k, v in labels.items()])
    if "operator" in name:
        return False
    return "mongos" in name or "component=mongos" in label_text


def container_names_for_pod(pod: Dict[str, Any], mongo_exec: Dict[str, Any]) -> List[str]:
    spec = pod.get("spec") or {}
    containers = spec.get("containers") or []
    names = [
        str(item.get("name") or "")
        for item in containers
        if isinstance(item, dict) and item.get("name")
    ]
    if not names:
        return []
    ordered: List[str] = []
    seen = set()

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)

    add(names[0])
    for candidate in list(mongo_exec.get("container_name_candidates") or []) + list(MONGO_CONTAINER_CANDIDATES):
        if candidate in names:
            add(candidate)
    for name in names:
        add(name)
    return ordered


def load_pod(kubectl: str, namespace: str, pod_ref: str, pod_by_name: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    if pod_ref in pod_by_name:
        return pod_by_name[pod_ref]
    proc = subprocess.run(
        [kubectl, "get", "pod", "-n", namespace, pod_ref, "-o", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return {"metadata": {"name": pod_ref}, "spec": {"containers": []}}
    try:
        payload = json.loads(proc.stdout or "{}")
    except ValueError:
        payload = {"metadata": {"name": pod_ref}, "spec": {"containers": []}}
    if isinstance(payload, dict):
        pod_by_name[pod_ref] = payload
        return payload
    return {"metadata": {"name": pod_ref}, "spec": {"containers": []}}


def load_namespace_pods(kubectl: str, namespace: str, artifact_dir: str) -> List[Dict[str, Any]]:
    proc = subprocess.run(
        [kubectl, "get", "pods", "-n", namespace, "-o", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if proc.returncode != 0:
        return []
    raw_relpath = os.path.join("raw", "pods-for-mongos-resolution.json")
    with open(os.path.join(artifact_dir, raw_relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
    payload = json.loads(proc.stdout or "{}")
    return [item for item in (payload.get("items") or []) if isinstance(item, dict)]


def resolve_mongos_pod_refs(context: Dict[str, Any], kubectl: str, namespace: str, artifact_dir: str) -> List[str]:
    targets = context.get("targets") or {}
    refs = [str(item) for item in (targets.get("mongos_pod_refs") or []) if item]
    if refs:
        return refs
    pods = load_namespace_pods(kubectl, namespace, artifact_dir)
    candidates = [pod for pod in pods if is_mongos_pod(pod) and pod_is_running(pod)]
    candidates.sort(key=lambda pod: (0 if pod_is_ready(pod) else 1, pod_name(pod)))
    result: List[str] = []
    for pod in candidates:
        name = pod_name(pod)
        if name and name not in result:
            result.append(name)
    return result


DEFAULT_SHELL_CANDIDATES = ("mongosh", "mongo")


def shell_probe_command(shell_candidates: List[str]) -> str:
    checks = [
        "(command -v %s >/dev/null 2>&1 && command -v %s)" % (shlex.quote(item), shlex.quote(item))
        for item in shell_candidates
        if item
    ]
    if not checks:
        checks = [
            "(command -v mongosh >/dev/null 2>&1 && command -v mongosh)",
            "(command -v mongo >/dev/null 2>&1 && command -v mongo)",
        ]
    return " || ".join(checks)


def resolve_pod_exec(
    kubectl: str,
    namespace: str,
    pod: Dict[str, Any],
    mongo_exec: Dict[str, Any],
) -> Tuple[str, str, str]:
    pod_ref = pod_name(pod)
    pod_targets = mongo_exec.get("pod_targets") or {}
    if isinstance(pod_targets, dict):
        existing = pod_targets.get(pod_ref) or {}
        if isinstance(existing, dict) and existing.get("shell"):
            return str(existing.get("container") or ""), str(existing["shell"]), ""
    shell_candidates = [str(item) for item in (mongo_exec.get("shell_candidates") or list(DEFAULT_SHELL_CANDIDATES)) if item]
    probe = shell_probe_command(shell_candidates)
    last_detail = ""
    container_names = container_names_for_pod(pod, mongo_exec)
    if not container_names:
        return "", "", "pod/%s has no declared containers in spec" % pod_ref
    for container in container_names:
        cmd = [kubectl, "exec", "-n", namespace, pod_ref, "-c", container, "--", "bash", "-c", probe]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        if proc.returncode == 0:
            shell = (proc.stdout or "").strip().splitlines()[-1].strip()
            if shell:
                return container, shell, ""
        last_detail = proc.stderr.strip() or proc.stdout.strip() or last_detail
    if not last_detail:
        last_detail = "mongo shell not found in pod/%s" % pod_ref
    return "", "", last_detail


def kubectl_exec_command(kubectl: str, namespace: str, pod_ref: str, container: str, inner_cmd: str) -> List[str]:
    cmd = [kubectl, "exec", "-n", namespace, pod_ref]
    if container:
        cmd.extend(["-c", container])
    cmd.extend(["--", "bash", "-c", inner_cmd])
    return cmd


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

    mongos_query = context.get("mongos_query") or {}
    mongo_exec = context.get("mongo_exec") or {
        "container_name_candidates": list(MONGO_CONTAINER_CANDIDATES),
        "shell_candidates": ["mongosh", "mongo"],
        "pod_targets": {},
    }
    shell = str(mongos_query.get("shell") or "mongosh")
    database = str(mongos_query.get("database") or "admin")
    username = str(mongos_query.get("username") or "")
    password = str(mongos_query.get("password") or "")
    password_env = str(mongos_query.get("password_env") or "")
    password_file_env = str(mongos_query.get("password_file_env") or "")
    secret_ref = mongos_query.get("secret_ref") or {}
    auth_database = str(mongos_query.get("auth_database") or "admin")
    mongos_pod_refs = resolve_mongos_pod_refs(context, kubectl, str(namespace), artifact_dir)
    if not mongos_pod_refs:
        blocked_output(
            output_file,
            script_id,
            started_at,
            "no Running mongos pods could be resolved",
            ["targets.mongos_pod_refs is empty and no Running mongos pod was detected"],
            [
                {
                    "gap": "mongos target pods not resolved",
                    "related_stage": "signal_collection",
                    "why_important": "shard map must be collected from Running mongos Pods",
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
                target=",".join(mongos_pod_refs),
            )
            return 0

    def shell_prefix(resolved_shell: str) -> str:
        return "MONGO_SHELL=%s; " % shlex.quote(resolved_shell)

    def build_inner_command(resolved_shell: str) -> str:
        resolve_shell = shell_prefix(resolved_shell)
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
    pods = load_namespace_pods(kubectl, str(namespace), artifact_dir)
    pod_by_name = {pod_name(pod): pod for pod in pods if pod_name(pod)}
    artifacts: List[Dict[str, Any]] = []
    shard_maps: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    evidence_gaps: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for target_pod in mongos_pod_refs:
        pod = load_pod(kubectl, str(namespace), target_pod, pod_by_name)
        container, resolved_shell, probe_error = resolve_pod_exec(kubectl, str(namespace), pod, mongo_exec)
        base = target_pod.replace("/", "_")
        if not resolved_shell:
            failed_items.append(
                {"item": "pod/%s" % target_pod, "reason": probe_error, "impact": "missing shard map from this mongos"}
            )
            evidence_gaps.append(
                {
                    "gap": "mongos shard map not collected from pod/%s" % target_pod,
                    "gap_type": "expected_gap",
                    "related_stage": "signal_collection",
                    "why_important": "A single mongos failure should not block shard map collection from other Running mongos Pods.",
                    "recommended_action": "collect getShardMap from another Running mongos Pod",
                }
            )
            continue
        inner_cmd = build_inner_command(resolved_shell)
        cmd = kubectl_exec_command(kubectl, str(namespace), target_pod, container, inner_cmd)
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout_relpath = os.path.join("raw", "%s-get-shard-map.stdout" % base)
        stderr_relpath = os.path.join("raw", "%s-get-shard-map.stderr" % base)
        with open(os.path.join(artifact_dir, stdout_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        with open(os.path.join(artifact_dir, stderr_relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
        artifacts.extend(
            [
                {"path": stdout_relpath, "kind": "raw_command_output", "description": "raw getShardMap stdout from %s" % target_pod},
                {"path": stderr_relpath, "kind": "raw_command_error", "description": "raw getShardMap stderr from %s" % target_pod},
            ]
        )
        if proc.returncode != 0:
            failed_items.append(
                {
                    "item": "pod/%s" % target_pod,
                    "reason": proc.stderr.strip() or "getShardMap returned non-zero exit code",
                    "impact": "missing shard map from this mongos",
                }
            )
            evidence_gaps.append(
                {
                    "gap": "mongos shard map command failed on pod/%s" % target_pod,
                    "gap_type": "expected_gap",
                    "related_stage": "signal_collection",
                    "why_important": "Other Running mongos Pods may still provide shard map evidence.",
                    "recommended_action": "collect getShardMap from another Running mongos Pod",
                }
            )
            continue
        try:
            raw_result = extract_json(proc.stdout)
        except ValueError as exc:
            failed_items.append({"item": "pod/%s" % target_pod, "reason": str(exc), "impact": "unparsed shard map from this mongos"})
            evidence_gaps.append(
                {
                    "gap": "mongos shard map output not parsed from pod/%s" % target_pod,
                    "gap_type": "expected_gap",
                    "related_stage": "signal_collection",
                    "why_important": "Other Running mongos Pods may still provide parseable shard map output.",
                    "recommended_action": "collect getShardMap from another Running mongos Pod",
                }
            )
            continue
        raw_json_relpath = os.path.join("raw", "%s-get-shard-map.json" % base)
        with open(os.path.join(artifact_dir, raw_json_relpath), "w", encoding="utf-8") as fh:
            json.dump(raw_result, fh, indent=2, sort_keys=False)
            fh.write("\n")
        artifacts.append(
            {"path": raw_json_relpath, "kind": "raw_command_output", "description": "parsed getShardMap JSON from %s" % target_pod}
        )
        parsed = parse_shard_map(raw_result)
        finished_piece = now_iso()
        shard_maps.append(
            {
                "source_component_ref": "mongos-router",
                "source_pod_ref": target_pod,
                "source_container": container,
                "source_shell": resolved_shell,
                "source_method": "mongos getShardMap",
                "config_server_ref": parsed["config_server_ref"],
                "shards": parsed["shards"],
                "raw_ok": parsed["raw_ok"],
                "collection_status": "success",
                "collected_at": finished_piece,
            }
        )
        if not parsed["shards"]:
            warnings.append("getShardMap returned no shard entries from pod/%s" % target_pod)

    finished_at = now_iso()
    successful_items = [
        {
            "item": "shard_map/pod/%s" % item["source_pod_ref"],
            "source": item["source_pod_ref"],
            "note": "%d shard record(s)" % len(item.get("shards") or []),
        }
        for item in shard_maps
    ]
    if not shard_maps:
        status = "blocked"
        summary = "no getShardMap result collected from Running mongos pods"
        evidence_gaps.append(
            {
                "gap": "mongos shard map not collected from any Running mongos Pod",
                "gap_type": "critical_gap",
                "related_stage": "signal_collection",
                "why_important": "Without any mongos getShardMap result, sharded topology cannot be validated.",
                "recommended_action": "identify a Running mongos Pod with mongosh/mongo access and rerun getShardMap",
                "affects": ["mechanism", "root_cause"],
            }
        )
    elif failed_items:
        status = "partial"
        summary = "collected %d shard map(s), %d mongos failed" % (len(shard_maps), len(failed_items))
    else:
        status = "success"
        summary = "collected %d shard map(s) from Running mongos pods" % len(shard_maps)

    shard_map = shard_maps[0] if shard_maps else {}
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
                "shard_maps": shard_maps,
            }
        },
        "signal_bundle_patch": {},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect mongos shard map",
                    "target": ",".join(mongos_pod_refs),
                    "method": "kubectl exec + getShardMap",
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
