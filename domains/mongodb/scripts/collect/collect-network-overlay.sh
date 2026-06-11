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


def pod_name(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("name")) or "")


def pod_namespace(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("namespace")) or "")


def pod_node(item: Dict[str, Any]) -> str:
    return str((item.get("spec") or {}).get("nodeName") or "")


def pod_ip(item: Dict[str, Any]) -> str:
    return str((item.get("status") or {}).get("podIP") or "")


def pod_phase(item: Dict[str, Any]) -> str:
    return str((item.get("status") or {}).get("phase") or "")


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


def is_mongodb_pod(item: Dict[str, Any]) -> bool:
    text = (pod_name(item) + " " + labels_text(item)).lower()
    return any(token in text for token in ("mongo", "mongos", "shard", "configsvr", "mongodb"))


def is_coredns_pod(item: Dict[str, Any]) -> bool:
    text = (pod_name(item) + " " + labels_text(item)).lower()
    return "coredns" in text or "kube-dns" in text


def is_flannel_pod(item: Dict[str, Any]) -> bool:
    text = (pod_name(item) + " " + labels_text(item)).lower()
    return "flannel" in text


def running_container_name(item: Dict[str, Any]) -> str:
    for status in (item.get("status") or {}).get("containerStatuses") or []:
        if (status.get("state") or {}).get("running") and status.get("name"):
            return str(status.get("name"))
    containers = (item.get("spec") or {}).get("containers") or []
    return str((containers[0] or {}).get("name") or "") if containers else ""


def container_ports(item: Dict[str, Any]) -> List[int]:
    ports: List[int] = []
    for container in (item.get("spec") or {}).get("containers") or []:
        for port in container.get("ports") or []:
            try:
                value = int(port.get("containerPort") or 0)
            except (TypeError, ValueError):
                value = 0
            if value and value not in ports:
                ports.append(value)
    return ports


def node_records(nodes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for node in nodes:
        name = str(((node.get("metadata") or {}).get("name")) or "")
        if not name:
            continue
        internal_ip = ""
        pod_cidr = str((node.get("spec") or {}).get("podCIDR") or "")
        for address in ((node.get("status") or {}).get("addresses")) or []:
            if address.get("type") == "InternalIP":
                internal_ip = str(address.get("address") or "")
                break
        result[name] = {"node_ref": name, "internal_ip": internal_ip or name, "pod_cidr": pod_cidr}
    return result


def local_addresses() -> List[str]:
    addresses = {socket.gethostname(), socket.gethostname().split(".")[0]}
    proc = run(["sh", "-lc", "hostname -I 2>/dev/null || true"], timeout=5)
    for item in (proc.stdout or "").split():
        addresses.add(item)
    return [item for item in addresses if item]


def node_command(access: Dict[str, Any], node_host: str, node_name: str, shell: str, timeout: int = 30) -> subprocess.CompletedProcess:
    if node_host in local_addresses() or node_name in local_addresses():
        return run(["bash", "-lc", shell], timeout=timeout)
    username = str(access.get("username") or "root")
    port = str(access.get("port") or 22)
    password = str(access.get("password") or "")
    if password and shutil.which("sshpass"):
        env = os.environ.copy()
        env["SSHPASS"] = password
        cmd = ["sshpass", "-e", "ssh", *SSH_OPTIONS, "-p", port, "%s@%s" % (username, node_host), "bash -lc %s" % shlex.quote(shell)]
        return run(cmd, timeout=timeout, env=env)
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=8", "-p", port, "%s@%s" % (username, node_host), "bash -lc %s" % shlex.quote(shell)]
    return run(cmd, timeout=timeout)


def flannel_link_line(text: str) -> str:
    for line in (text or "").splitlines():
        if "flannel.1:" in line and "<" in line:
            return line
    return ""


def flannel_flags(text: str) -> str:
    match = re.search(r"<([^>]+)>", flannel_link_line(text))
    return match.group(1) if match else ""


def flannel_state(text: str) -> str:
    match = re.search(r"\bstate\s+([A-Z]+)\b", flannel_link_line(text))
    return match.group(1) if match else ""


def has_flannel_up(link_text: str) -> bool:
    flags = flannel_flags(link_text).split(",")
    state = flannel_state(link_text)
    return "UP" in flags and state != "DOWN"


def route_count(text: str) -> int:
    return sum(1 for line in (text or "").splitlines() if "10.244." in line)


def fdb_count(text: str) -> int:
    return sum(1 for line in (text or "").splitlines() if line.strip())


def coredns_endpoints(endpoints: List[Dict[str, Any]], pod_by_ip: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for item in endpoints:
        meta = item.get("metadata") or {}
        if str(meta.get("namespace") or "") != "kube-system":
            continue
        if str(meta.get("name") or "") not in ("kube-dns", "coredns"):
            continue
        for subset in item.get("subsets") or []:
            for address in subset.get("addresses") or []:
                ip = str(address.get("ip") or "")
                pod = pod_by_ip.get(ip, {})
                target = address.get("targetRef") or {}
                result.append(
                    {
                        "service_ref": "%s/%s" % (meta.get("namespace"), meta.get("name")),
                        "ip": ip,
                        "pod_ref": str(target.get("name") or pod_name(pod)),
                        "namespace": str(target.get("namespace") or pod_namespace(pod)),
                        "node_ref": str(address.get("nodeName") or pod_node(pod)),
                        "ready": True,
                    }
                )
            for address in subset.get("notReadyAddresses") or []:
                ip = str(address.get("ip") or "")
                pod = pod_by_ip.get(ip, {})
                target = address.get("targetRef") or {}
                result.append(
                    {
                        "service_ref": "%s/%s" % (meta.get("namespace"), meta.get("name")),
                        "ip": ip,
                        "pod_ref": str(target.get("name") or pod_name(pod)),
                        "namespace": str(target.get("namespace") or pod_namespace(pod)),
                        "node_ref": str(address.get("nodeName") or pod_node(pod)),
                        "ready": False,
                    }
                )
    return result


def select_source_pods(pods: List[Dict[str, Any]], namespace: str) -> List[Dict[str, Any]]:
    candidates = [pod for pod in pods if pod_phase(pod) == "Running" and running_container_name(pod)]
    preferred = [pod for pod in candidates if pod_namespace(pod) == namespace and (is_mongodb_pod(pod) or pod_ready(pod))]
    if not preferred:
        preferred = [pod for pod in candidates if pod_ready(pod)]
    selected: List[Dict[str, Any]] = []
    seen_nodes = set()
    for pod in sorted(preferred, key=lambda item: (is_mongodb_pod(item), pod_ready(item), -restart_count(item)), reverse=True):
        node = pod_node(pod)
        if not node or node in seen_nodes:
            continue
        selected.append(pod)
        seen_nodes.add(node)
        if len(selected) >= 3:
            break
    return selected


def select_targets(pods: List[Dict[str, Any]], dns_endpoints: List[Dict[str, Any]], namespace: str) -> List[Dict[str, Any]]:
    targets: List[Dict[str, Any]] = []
    for endpoint in dns_endpoints:
        if endpoint.get("ip"):
            targets.append({"ip": endpoint["ip"], "port": 9153, "node_ref": endpoint.get("node_ref", ""), "target_ref": "dns/%s" % endpoint.get("pod_ref", endpoint["ip"])})
    for pod in pods:
        if pod_namespace(pod) != namespace or not pod_ip(pod) or not is_mongodb_pod(pod) or not pod_ready(pod):
            continue
        ports = container_ports(pod)
        port = 27017 if 27017 in ports or any(token in pod_name(pod).lower() for token in ("mongo", "shard", "configsvr")) else (ports[0] if ports else 0)
        if port:
            targets.append({"ip": pod_ip(pod), "port": port, "node_ref": pod_node(pod), "target_ref": "pod/%s" % pod_name(pod)})
    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in targets:
        key = (item.get("ip"), item.get("port"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:10]


def probe_command(ip: str, port: int) -> str:
    return (
        "if command -v timeout >/dev/null 2>&1; then T='timeout 4'; else T=''; fi; "
        "if command -v nc >/dev/null 2>&1; then $T nc -vz -w 2 %s %s; "
        "elif command -v bash >/dev/null 2>&1; then $T bash -lc %s; "
        "else echo 'connect probe tool unavailable: nc/bash not found' >&2; exit 127; fi"
        % (shlex.quote(ip), int(port), shlex.quote("</dev/tcp/%s/%s" % (ip, port)))
    )


def run_connectivity_probes(kubectl: str, pods: List[Dict[str, Any]], targets: List[Dict[str, Any]], namespace: str, artifact_dir: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    checks: List[Dict[str, Any]] = []
    artifacts: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    count = 0
    for source in select_source_pods(pods, namespace):
        source_node = pod_node(source)
        source_pod = pod_name(source)
        container = running_container_name(source)
        for target in targets:
            if count >= 12:
                return checks, artifacts, failed_items
            if not target.get("ip") or not target.get("port"):
                continue
            if target.get("node_ref") == source_node:
                continue
            command = [kubectl, "exec", "-n", pod_namespace(source), source_pod]
            if container:
                command.extend(["-c", container])
            command.extend(["--", "sh", "-lc", probe_command(str(target["ip"]), int(target["port"]))])
            try:
                proc = run(command, timeout=7)
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                proc = subprocess.CompletedProcess(command, 124, stdout, (stderr + "\nconnectivity probe timed out").strip())
            relpath = os.path.join("raw", "overlay-probe-%s-to-%s-%s.txt" % (safe_name(source_pod), safe_name(str(target["ip"])), target["port"]))
            output = (proc.stdout or "") + ("\n# stderr\n" + proc.stderr if proc.stderr else "")
            with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
                fh.write(output)
            artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "connectivity probe from pod/%s to %s:%s" % (source_pod, target["ip"], target["port"])})
            status = "success" if proc.returncode == 0 else ("blocked" if proc.returncode == 127 else "failed")
            check = {
                "source_pod_ref": source_pod,
                "source_namespace": pod_namespace(source),
                "source_node_ref": source_node,
                "target_ref": target.get("target_ref", ""),
                "target_ip": target.get("ip"),
                "target_node_ref": target.get("node_ref", ""),
                "target_port": target.get("port"),
                "status": status,
                "exit_code": proc.returncode,
                "artifact_path": relpath,
                "sample": output.strip()[:500],
                "collected_at": now_iso(),
            }
            checks.append(check)
            if status != "success":
                failed_items.append({"item": "overlay_probe/%s->%s:%s" % (source_pod, target["ip"], target["port"]), "reason": output.strip()[:500] or "probe failed", "impact": "pod-to-pod or service-backend reachability may be impaired"})
            count += 1
    return checks, artifacts, failed_items


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, gap: str) -> None:
    finished_at = now_iso()
    evidence_gap = {
        "gap": gap,
        "gap_type": "critical_gap",
        "related_stage": "directed_recollection",
        "why_important": "DNS timeout evidence cannot be promoted to an overlay root cause without Service endpoint and node network evidence.",
        "recommended_action": "collect kube-dns endpoints, flannel.1 state, PodCIDR routes, and flannel logs",
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
                    "name": "collect Kubernetes overlay network evidence",
                    "target": "kube-dns endpoints and flannel nodes",
                    "method": "kubectl get + node SSH read-only network commands",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "network/overlay", "reason": summary, "impact": "overlay root-cause evidence remains missing"}],
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
    script_id = str(context.get("script_id") or "mongodb.collect.network.overlay")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")
    access = context.get("access") or {}
    os.makedirs(os.path.join(artifact_dir, "raw"), exist_ok=True)

    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(output_file, script_id, started_at, "kubectl command not found", "overlay evidence not collected")
        return 0

    artifacts: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    failed_items: List[Dict[str, Any]] = []
    blank_items: List[Dict[str, Any]] = []
    warnings: List[str] = []
    signals: List[Dict[str, Any]] = []

    raw_commands = {
        "pods-all-for-overlay.json": [kubectl, "get", "pods", "-A", "-o", "json"],
        "nodes-for-overlay.json": [kubectl, "get", "nodes", "-o", "json"],
        "endpoints-all-for-overlay.json": [kubectl, "get", "endpoints", "-A", "-o", "json"],
    }
    raw_payloads: Dict[str, Dict[str, Any]] = {}
    for filename, command in raw_commands.items():
        proc = run(command, timeout=45)
        relpath = os.path.join("raw", filename)
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
            if proc.stderr:
                fh.write("\n# stderr\n")
                fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "overlay evidence source: %s" % " ".join(command[1:])})
        if proc.returncode != 0:
            blocked_payload(output_file, script_id, started_at, "%s failed" % " ".join(command), "overlay input %s not collected" % filename)
            return 0
        raw_payloads[filename] = json.loads(proc.stdout or "{}")

    pods = [item for item in raw_payloads["pods-all-for-overlay.json"].get("items") or [] if isinstance(item, dict)]
    nodes = [item for item in raw_payloads["nodes-for-overlay.json"].get("items") or [] if isinstance(item, dict)]
    endpoints = [item for item in raw_payloads["endpoints-all-for-overlay.json"].get("items") or [] if isinstance(item, dict)]
    node_map = node_records(nodes)
    pod_by_ip = {pod_ip(item): item for item in pods if pod_ip(item)}
    dns_endpoints = coredns_endpoints(endpoints, pod_by_ip)
    if dns_endpoints:
        successful_items.append({"item": "kube-dns/endpoints", "source": "kubectl get endpoints -A", "note": "%d endpoint(s)" % len(dns_endpoints)})
    else:
        failed_items.append({"item": "kube-dns/endpoints", "reason": "no kube-dns/coredns endpoints detected", "impact": "DNS backend distribution remains unknown"})

    flannel_pods_by_node: Dict[str, Dict[str, Any]] = {}
    for pod in pods:
        if is_flannel_pod(pod) and pod_node(pod):
            flannel_pods_by_node[pod_node(pod)] = pod

    overlay_nodes: List[Dict[str, Any]] = []
    for node_name, node in sorted(node_map.items()):
        node_host = str(node.get("internal_ip") or node_name)
        shell = "\n".join(
            [
                "echo '## ip -d link show flannel.1'",
                "ip -d link show flannel.1 2>&1 || true",
                "echo '## ip -o addr show dev flannel.1'",
                "ip -o addr show dev flannel.1 2>&1 || true",
                "echo '## ip route 10.244'",
                "ip route 2>&1 | grep '10.244' || true",
                "echo '## bridge fdb show dev flannel.1'",
                "bridge fdb show dev flannel.1 2>&1 || true",
                "echo '## ip neigh show dev flannel.1'",
                "ip neigh show dev flannel.1 2>&1 || true",
                "echo '## ip -s link show flannel.1'",
                "ip -s link show flannel.1 2>&1 || true",
            ]
        )
        proc = node_command(access, node_host, node_name, shell, timeout=35)
        relpath = os.path.join("raw", "overlay-node-%s.txt" % safe_name(node_name))
        with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
            fh.write(proc.stdout)
            if proc.stderr:
                fh.write("\n# stderr\n")
                fh.write(proc.stderr)
        artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "node overlay state for %s" % node_name})
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        link_section = output.split("## ip -o addr show dev flannel.1", 1)[0]
        routes_section = output.split("## ip route 10.244", 1)[-1].split("## bridge fdb", 1)[0] if "## ip route 10.244" in output else ""
        fdb_section = output.split("## bridge fdb show dev flannel.1", 1)[-1].split("## ip neigh", 1)[0] if "## bridge fdb show dev flannel.1" in output else ""
        record = {
            "node_ref": node_name,
            "internal_ip": node_host,
            "pod_cidr": node.get("pod_cidr", ""),
            "status": "success" if proc.returncode == 0 else "blocked",
            "flannel_state": flannel_state(link_section),
            "flannel_flags": flannel_flags(link_section),
            "flannel_up": has_flannel_up(link_section),
            "podcidr_route_count": route_count(routes_section),
            "fdb_entry_count": fdb_count(fdb_section),
            "artifact_path": relpath,
            "collected_at": now_iso(),
        }
        if proc.returncode != 0:
            failed_items.append({"item": "node/%s overlay_state" % node_name, "reason": proc.stderr.strip() or "node command failed", "impact": "node overlay state unavailable"})
        overlay_nodes.append(record)

        flannel_pod = flannel_pods_by_node.get(node_name, {})
        if flannel_pod:
            log_proc = run([kubectl, "logs", "-n", pod_namespace(flannel_pod), pod_name(flannel_pod), "--tail=250", "--timestamps"], timeout=45)
            log_relpath = os.path.join("raw", "flannel-logs-%s.log" % safe_name(node_name))
            with open(os.path.join(artifact_dir, log_relpath), "w", encoding="utf-8") as fh:
                fh.write(log_proc.stdout)
                if log_proc.stderr:
                    fh.write("\n# stderr\n")
                    fh.write(log_proc.stderr)
            artifacts.append({"path": log_relpath, "kind": "raw_log", "description": "flannel logs for node/%s" % node_name})
            log_text = (log_proc.stdout or "") + ("\n" + log_proc.stderr if log_proc.stderr else "")
            record["flannel_log_artifact_path"] = log_relpath
            record["flannel_log_has_network_down"] = bool(re.search(r"network is down|failed to add vxlanRoute", log_text, re.I))
            if record["flannel_log_has_network_down"]:
                signals.append(
                    {
                        "signal_id": "flannel-route-install-failed",
                        "severity": "high",
                        "object_ref": "node/%s" % node_name,
                        "detail": "flannel logs on node/%s contain network-is-down or failed-to-add-vxlanRoute errors." % node_name,
                    }
                )
        if record["status"] == "success" and not record["flannel_up"]:
            signals.append(
                {
                    "signal_id": "flannel-vxlan-down",
                    "severity": "critical",
                    "object_ref": "node/%s" % node_name,
                    "detail": "flannel.1 is not UP on node/%s: state=%s flags=%s pod_cidr=%s"
                    % (node_name, record.get("flannel_state") or "unknown", record.get("flannel_flags") or "unknown", record.get("pod_cidr") or ""),
                }
            )

    bad_overlay_nodes = {item["node_ref"] for item in overlay_nodes if item.get("status") == "success" and not item.get("flannel_up")}
    for endpoint in dns_endpoints:
        if endpoint.get("node_ref") in bad_overlay_nodes:
            signals.append(
                {
                    "signal_id": "kube-dns-backend-on-overlay-partition",
                    "severity": "high",
                    "object_ref": "endpoint/%s" % endpoint.get("ip"),
                    "detail": "kube-dns endpoint %s is on node/%s where flannel.1 is not UP." % (endpoint.get("ip"), endpoint.get("node_ref")),
                }
            )

    targets = select_targets(pods, dns_endpoints, namespace)
    checks, probe_artifacts, probe_failed_items = run_connectivity_probes(kubectl, pods, targets, namespace, artifact_dir)
    artifacts.extend(probe_artifacts)
    failed_items.extend(probe_failed_items)
    failed_by_target_node: Dict[str, int] = {}
    for check in checks:
        if check.get("status") == "failed" and check.get("target_node_ref"):
            failed_by_target_node[str(check["target_node_ref"])] = failed_by_target_node.get(str(check["target_node_ref"]), 0) + 1
    for node_name, count in failed_by_target_node.items():
        if count >= 2 and node_name in bad_overlay_nodes:
            signals.append(
                {
                    "signal_id": "pod-subnet-isolated",
                    "severity": "high",
                    "object_ref": "node/%s" % node_name,
                    "detail": "multiple cross-node pod connectivity probes to node/%s failed (%d failures)." % (node_name, count),
                }
            )

    if overlay_nodes:
        successful_items.append({"item": "network/overlay_nodes", "source": "node SSH read-only commands", "note": "%d node(s) inspected" % len(overlay_nodes)})
    coredns_pods = [
        {
            "name": pod_name(item),
            "namespace": pod_namespace(item),
            "node_ref": pod_node(item),
            "phase": pod_phase(item),
            "ready": pod_ready(item),
            "restart_count": restart_count(item),
        }
        for item in pods
        if is_coredns_pod(item)
    ]
    finished_at = now_iso()
    evidence_gaps: List[Dict[str, Any]] = []
    if not overlay_nodes:
        evidence_gaps.append(
            {
                "gap": "overlay node state was not collected",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "DNS timeout root cause cannot be attributed to flannel overlay without node overlay state.",
                "recommended_action": "collect flannel.1 state and PodCIDR routes from each node",
                "affects": ["root_cause"],
            }
        )
    if dns_endpoints and not checks:
        evidence_gaps.append(
            {
                "gap": "pod connectivity probes were not completed",
                "gap_type": "expected_gap",
                "related_stage": "directed_recollection",
                "why_important": "Flannel state and logs may still support overlay root cause, but connectivity probes help define impact radius.",
                "recommended_action": "run read-only pod-to-pod probes from stable workload pods",
            }
        )

    status = "blocked" if not overlay_nodes else ("partial" if failed_items or evidence_gaps else "success")
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": "collected Kubernetes overlay evidence for %d node(s)" % len(overlay_nodes),
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "coredns_pods": coredns_pods,
                "kube_dns_endpoints": dns_endpoints,
                "network_overlay": {
                    "nodes": overlay_nodes,
                    "pod_connectivity_checks": checks,
                    "collected_at": finished_at,
                },
            }
        },
        "signal_bundle_patch": {"abnormal_signals": signals},
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect Kubernetes overlay network evidence",
                    "target": "kube-dns endpoints and flannel nodes",
                    "method": "kubectl get + node SSH read-only network commands",
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
