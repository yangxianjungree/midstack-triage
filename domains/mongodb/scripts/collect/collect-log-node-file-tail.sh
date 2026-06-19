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
import re
import shlex
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


DISCOVER_SCRIPT_ID = "mongodb.collect.logs.discover_sink"
DEFAULT_LOG_PATHS = [
    "/opt/bitnami/mongodb/logs/mongodb.log",
    "/var/log/mongodb/mongod.log",
    "/var/log/mongodb/mongodb.log",
]
PATTERNS = [
    ("fatal", re.compile(r"\b(fatal|panic|wt_panic|segmentation fault|unclean shutdown|aborting)\b", re.I)),
    ("storage", re.compile(r"\b(wiredtiger|journal|corrupt|checksum|bad magic|try_salvage|metadata corruption|filesystem|fsync)\b", re.I)),
    ("error", re.compile(r"\b(error|exception|failed|failure|assertion)\b", re.I)),
    ("resource", re.compile(r"\b(oom|killed|memory|disk|too many open files)\b", re.I)),
    ("timeout", re.compile(r"\b(timeout|timed out|deadline)\b", re.I)),
    ("connection", re.compile(r"\b(connection|network|socket|refused|reset)\b", re.I)),
]
SSH_OPTIONS = [
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "ConnectTimeout=8",
    "-o",
    "ServerAliveInterval=5",
    "-o",
    "ServerAliveCountMax=2",
    "-o",
    "PreferredAuthentications=password,keyboard-interactive",
    "-o",
    "PubkeyAuthentication=no",
    "-o",
    "NumberOfPasswordPrompts=1",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) if yaml is not None else json.load(fh)
    return data if isinstance(data or {}, dict) else {}


def write_yaml(path: str, payload: Dict[str, Any]) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
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


def run(cmd: List[str], timeout: int = 30, env: Dict[str, str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout, env=env)


def classify(line: str) -> str:
    for label, pattern in PATTERNS:
        if pattern.search(line):
            return label
    return ""


def scan_highlights(pod_ref: str, text: str, limit: int = 80) -> List[Dict[str, Any]]:
    highlights: List[Dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        category = classify(line)
        if not category:
            continue
        highlights.append(
            {
                "pod_ref": pod_ref,
                "log_type": "file_tail",
                "source_method": "node_file_tail",
                "line_no": line_no,
                "category": category,
                "message": line[:1000],
            }
        )
        if len(highlights) >= limit:
            break
    return highlights


def discover_output_path(context: Dict[str, Any]) -> str:
    files = ((context.get("inputs") or {}).get("script_output_files")) or {}
    return str(files.get(DISCOVER_SCRIPT_ID) or "")


def log_sinks_from_discover(path: str) -> List[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return []
    output = load_yaml(path)
    sinks = (((output.get("structured_record_patch") or {}).get("details")) or {}).get("log_sinks") or []
    return [item for item in sinks if isinstance(item, dict)]


def selected_log_path(sinks: List[Dict[str, Any]]) -> str:
    for sink in sinks:
        path = str(sink.get("path") or "")
        if path and not bool(sink.get("is_stdout_link")):
            return path
    return ""


def candidate_log_paths(discovered_path: str) -> List[str]:
    result: List[str] = []
    if discovered_path:
        result.append(discovered_path)
    for path in DEFAULT_LOG_PATHS:
        if path not in result:
            result.append(path)
    return result


def pod_name(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("name")) or "")


def pod_uid(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("uid")) or "")


def pod_phase(item: Dict[str, Any]) -> str:
    return str(((item.get("status") or {}).get("phase")) or "")


def pod_ready(item: Dict[str, Any]) -> bool:
    for condition in (item.get("status") or {}).get("conditions") or []:
        if condition.get("type") == "Ready":
            return condition.get("status") == "True"
    return False


def restart_count(item: Dict[str, Any]) -> int:
    return sum(int(status.get("restartCount") or 0) for status in (item.get("status") or {}).get("containerStatuses") or [])


def labels_text(item: Dict[str, Any]) -> str:
    labels = ((item.get("metadata") or {}).get("labels")) or {}
    return " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in labels.items())


def pod_score(item: Dict[str, Any], target_refs: List[str]) -> int:
    name = pod_name(item).lower()
    label_text = labels_text(item)
    score = 0
    if pod_name(item) in set(target_refs):
        score += 50
    if not pod_ready(item):
        score += 35
    score += min(restart_count(item), 60)
    if "mongodb" in label_text or "mongod" in label_text:
        score += 10
    if any(token in name for token in ("shard", "configsvr", "mongodb", "mongo")):
        score += 25
    if "mongos" in name:
        score -= 5
    if "operator" in name:
        score -= 80
    return score


def load_node_ips(kubectl: str, artifact_dir: str) -> Tuple[Dict[str, str], str]:
    proc = run([kubectl, "get", "nodes", "-o", "json"], timeout=45)
    relpath = os.path.join("raw", "nodes-for-node-file-tail.json")
    with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
        fh.write(proc.stdout)
        if proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(proc.stderr)
    result: Dict[str, str] = {}
    if proc.returncode != 0:
        return result, relpath
    payload = json.loads(proc.stdout or "{}")
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        name = str(((item.get("metadata") or {}).get("name")) or "")
        internal_ip = ""
        for address in ((item.get("status") or {}).get("addresses")) or []:
            if address.get("type") == "InternalIP":
                internal_ip = str(address.get("address") or "")
                break
        if name:
            result[name] = internal_ip or name
    return result, relpath


def find_volume(item: Dict[str, Any], name: str) -> Dict[str, Any]:
    for volume in (item.get("spec") or {}).get("volumes") or []:
        if volume.get("name") == name:
            return volume
    return {}


def host_path_for_log(item: Dict[str, Any], log_path: str) -> Tuple[str, str]:
    uid = pod_uid(item)
    if not uid:
        return "", "pod UID is missing"
    best_mount: Dict[str, Any] = {}
    best_container = ""
    for container in (item.get("spec") or {}).get("containers") or []:
        for mount in container.get("volumeMounts") or []:
            mount_path = str(mount.get("mountPath") or "").rstrip("/")
            if not mount_path:
                continue
            if log_path == mount_path or log_path.startswith(mount_path + "/"):
                if not best_mount or len(mount_path) > len(str(best_mount.get("mountPath") or "")):
                    best_mount = mount
                    best_container = str(container.get("name") or "")
    if not best_mount:
        return "", "no volumeMount covers %s" % log_path
    volume_name = str(best_mount.get("name") or "")
    volume = find_volume(item, volume_name)
    if not volume:
        return "", "volume %s was not found in pod spec" % volume_name
    mount_path = str(best_mount.get("mountPath") or "").rstrip("/")
    rel = log_path[len(mount_path):].lstrip("/")
    sub_path = str(best_mount.get("subPath") or best_mount.get("subPathExpr") or "").strip("/")
    if "emptyDir" in volume:
        base = "/var/lib/kubelet/pods/%s/volumes/kubernetes.io~empty-dir/%s" % (uid, volume_name)
    elif "hostPath" in volume:
        base = str(((volume.get("hostPath") or {}).get("path")) or "").rstrip("/")
    else:
        return "", "volume %s for container %s is not emptyDir or hostPath" % (volume_name, best_container)
    parts = [base]
    if sub_path:
        parts.append(sub_path)
    if rel:
        parts.append(rel)
    return "/".join(part.strip("/") if idx else part.rstrip("/") for idx, part in enumerate(parts) if part), ""


def local_addresses() -> List[str]:
    addresses = {socket.gethostname(), socket.gethostname().split(".")[0]}
    proc = run(["sh", "-lc", "hostname -I 2>/dev/null || true"], timeout=5)
    for item in (proc.stdout or "").split():
        addresses.add(item)
    return [item for item in addresses if item]


def node_ssh_config(access: Dict[str, Any]) -> Dict[str, Any]:
    node_access = access.get("node_access") or {}
    if not isinstance(node_access, dict):
        node_access = {}
    ssh = node_access.get("ssh") or {}
    if not isinstance(ssh, dict):
        ssh = {}
    return ssh


def node_command(access: Dict[str, Any], node_host: str, node_name: str, shell: str, timeout: int = 30) -> subprocess.CompletedProcess:
    if node_host in local_addresses() or node_name in local_addresses():
        return run(["bash", "-lc", shell], timeout=timeout)
    ssh = node_ssh_config(access)
    if access.get("execution_mode") == "local" and not bool(ssh.get("enabled")):
        return subprocess.CompletedProcess(
            ["node_access"],
            2,
            "",
            "node SSH access is not enabled for local execution; configure access.node_access.ssh before collecting node-side file logs",
        )
    username = str(ssh.get("username") or access.get("username") or "root")
    port = str(ssh.get("port") or access.get("port") or 22)
    password = str(ssh.get("password") or access.get("password") or "")
    if password and shutil.which("sshpass"):
        env = os.environ.copy()
        env["SSHPASS"] = password
        cmd = ["sshpass", "-e", "ssh", *SSH_OPTIONS, "-p", port, "%s@%s" % (username, node_host), "bash -lc %s" % shlex.quote(shell)]
        return run(cmd, timeout=timeout, env=env)
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8", "-p", port, "%s@%s" % (username, node_host), "bash -lc %s" % shlex.quote(shell)]
    return run(cmd, timeout=timeout)


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, gap: str) -> None:
    finished_at = now_iso()
    evidence_gap = {
        "gap": gap,
        "gap_type": "critical_gap",
        "related_stage": "directed_recollection",
        "why_important": "CrashLooping MongoDB containers may exit before kubectl exec can read file-backed application logs.",
        "recommended_action": "collect MongoDB file logs from the node-side kubelet pod volume path",
        "affects": ["root_cause"],
    }
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
                    "name": "collect MongoDB node-side file log tail",
                    "target": "node-side pod volume",
                    "method": "ssh to pod node + read-only tail",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "mongodb/node_file_log", "reason": summary, "impact": "MongoDB process-internal root-cause evidence remains missing"}],
            "blank_items": [],
            "evidence_gaps": [evidence_gap],
        },
        "warnings": [summary],
        "evidence_gaps": [evidence_gap],
    }
    write_yaml(output_file, payload)


def main() -> int:
    context_file, output_file, artifact_dir = sys.argv[1:4]
    started_at = now_iso()
    context = load_yaml(context_file)
    script_id = str(context.get("script_id") or "mongodb.collect.logs.node_file_tail")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")
    access = context.get("access") or {}
    os.makedirs(os.path.join(artifact_dir, "raw", "logs-node-file-tail"), exist_ok=True)

    discover_path = discover_output_path(context)
    discovered_log_path = selected_log_path(log_sinks_from_discover(discover_path))
    log_paths = candidate_log_paths(discovered_log_path)
    fallback_log_path = not bool(discovered_log_path)

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(output_file, script_id, started_at, "kubectl command not found", "node-side file log targets not resolved")
        return 0

    pods_proc = run([kubectl, "get", "pods", "-n", namespace, "-o", "json"], timeout=45)
    pods_relpath = os.path.join("raw", "pods-for-node-file-log-tail.json")
    with open(os.path.join(artifact_dir, pods_relpath), "w", encoding="utf-8") as fh:
        fh.write(pods_proc.stdout)
        if pods_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(pods_proc.stderr)
    if pods_proc.returncode != 0:
        blocked_payload(output_file, script_id, started_at, "kubectl get pods failed", "node-side file log target pods not resolved")
        return 0

    node_ips, nodes_relpath = load_node_ips(kubectl, artifact_dir)
    pods = [item for item in (json.loads(pods_proc.stdout or "{}").get("items") or []) if isinstance(item, dict)]
    target_refs = [str(item) for item in ((context.get("targets") or {}).get("pod_refs") or []) if item]
    selected = [item for item in sorted(pods, key=lambda pod: pod_score(pod, target_refs), reverse=True) if pod_score(item, target_refs) > 0][:8]
    if not selected:
        blocked_payload(output_file, script_id, started_at, "no MongoDB pod selected for node-side file log tail", "node-side file log target pods not selected")
        return 0

    artifacts: List[Dict[str, Any]] = [
        {"path": pods_relpath, "kind": "raw_command_output", "description": "raw pod JSON used to select node-side file log tail targets"},
        {"path": nodes_relpath, "kind": "raw_command_output", "description": "raw node JSON used to resolve node InternalIP addresses"},
    ]
    raw_logs: List[Dict[str, Any]] = []
    highlights: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    blank_items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    used_log_paths: List[str] = []

    for pod in selected:
        pod_ref = pod_name(pod)
        node_name = str((pod.get("spec") or {}).get("nodeName") or "")
        node_host = node_ips.get(node_name, node_name)
        host_path = ""
        reason = ""
        log_path = ""
        for candidate_path in log_paths:
            host_path, reason = host_path_for_log(pod, candidate_path)
            if host_path:
                log_path = candidate_path
                break
        if not host_path:
            failed_items.append({"item": "pod/%s node file log" % pod_ref, "reason": reason, "impact": "cannot map container log path to node-side volume path"})
            continue
        if log_path not in used_log_paths:
            used_log_paths.append(log_path)
        shell = "test -r %s && tail -n 500 %s" % (shlex.quote(host_path), shlex.quote(host_path))
        proc = node_command(access, node_host, node_name, shell, timeout=35)
        relpath = os.path.join("raw", "logs-node-file-tail", "%s.log" % safe_name(pod_ref))
        errpath = os.path.join("raw", "logs-node-file-tail", "%s.stderr" % safe_name(pod_ref))
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
        with open(os.path.join(artifact_dir, errpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_log", "description": "node-side MongoDB file log tail from pod/%s path %s" % (pod_ref, host_path)})
        if proc.stderr:
            artifacts.append({"path": errpath, "kind": "raw_command_error", "description": "node-side file log stderr from pod/%s" % pod_ref})
        if proc.returncode != 0:
            failed_items.append({"item": "pod/%s node file log" % pod_ref, "reason": proc.stderr.strip() or "node-side file log tail failed", "impact": "missing node-side MongoDB file log for this pod"})
            continue
        line_count = len(proc.stdout.splitlines()) if proc.stdout else 0
        if line_count == 0:
            blank_items.append({"item": "pod/%s node file log" % pod_ref, "reason": "node-side file log tail returned zero lines", "impact": "file log may be empty, rotated, or not the active log source"})
        pod_highlights = scan_highlights(pod_ref, proc.stdout)
        highlights.extend(pod_highlights)
        raw_logs.append(
            {
                "pod_ref": pod_ref,
                "namespace": namespace,
                "node_ref": node_name,
                "log_type": "file_tail",
                "source_method": "node_file_tail",
                "artifact_path": relpath,
                "source_path": log_path,
                "node_source_path": host_path,
                "line_count": line_count,
                "byte_size": len(proc.stdout.encode("utf-8")),
                "tail_lines": 500,
                "highlight_count": len(pod_highlights),
                "collected_at": now_iso(),
            }
        )
        successful_items.append({"item": "pod/%s node file log" % pod_ref, "source": host_path, "note": "%d line(s), %d highlight(s)" % (line_count, len(pod_highlights))})

    finished_at = now_iso()
    evidence_gaps: List[Dict[str, Any]] = []
    if not raw_logs:
        evidence_gaps.append(
            {
                "gap": "MongoDB node-side file log tail could not be collected from selected Pods",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "Without node-side file-backed MongoDB logs, fast crash root-cause claims may remain unsupported.",
                "recommended_action": "verify node SSH access and collect the kubelet pod volume log path manually",
                "affects": ["root_cause"],
            }
        )
    elif fallback_log_path:
        evidence_gaps.append(
            {
                "gap": "MongoDB node-side file log tail used common log path fallback without discover_log_sink",
                "gap_type": "expected_gap",
                "related_stage": "directed_recollection",
                "why_important": "The fallback path is valid for common Bitnami MongoDB layouts but should be confirmed by log sink discovery when evidence remains ambiguous.",
                "recommended_action": "run discover_log_sink if node-side file logs are missing or do not match the failure window",
            }
        )
    elif not highlights:
        evidence_gaps.append(
            {
                "gap": "MongoDB node-side file log tail did not include fatal/error highlights",
                "gap_type": "expected_gap",
                "related_stage": "directed_recollection",
                "why_important": "The collected file tail may not cover the failure window or the log may have rotated.",
                "recommended_action": "extend node-side file log window or inspect rotated logs",
            }
        )

    status = "blocked" if not raw_logs else ("partial" if failed_items or evidence_gaps else "success")
    summary = "collected node-side MongoDB file log tail from %d pod(s)" % len(raw_logs)
    if not raw_logs:
        reasons = {str(item.get("reason") or "") for item in failed_items}
        if len(reasons) == 1:
            only_reason = next(iter(reasons))
            if only_reason.startswith("node SSH access is not enabled"):
                summary = only_reason
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": summary,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "raw_logs": raw_logs,
                "processed_logs": {
                    "file_tail_highlights": highlights,
                    "file_tail_highlight_count": len(highlights),
                    "collected_at": finished_at,
                },
            }
        },
        "signal_bundle_patch": {"log_highlights": highlights},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect MongoDB node-side file log tail",
                    "target": ",".join(item["pod_ref"] for item in raw_logs) or "node-side pod volume",
                    "method": "ssh to pod node + read-only tail %s" % (",".join(used_log_paths) or ",".join(log_paths)),
                    "status": status,
                    "performed_at": finished_at,
                }
            ],
            "successful_items": successful_items,
            "failed_items": failed_items,
            "blank_items": blank_items,
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
    except (ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
