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
import shutil
import shlex
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
        data = yaml.safe_load(fh) if yaml is not None else json.load(fh)
    if not isinstance(data or {}, dict):
        raise ValueError("context-file must contain a YAML object")
    return data or {}


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


def run(cmd: List[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=timeout)


def run_probe(cmd: List[str], timeout: int = 7) -> subprocess.CompletedProcess:
    try:
        return run(cmd, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        message = "DNS probe timed out after %ss" % timeout
        stderr = (stderr + "\n" + message).strip() if stderr else message
        return subprocess.CompletedProcess(cmd, 124, stdout, stderr)


def pod_name(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("name")) or "")


def pod_namespace(item: Dict[str, Any]) -> str:
    return str(((item.get("metadata") or {}).get("namespace")) or "")


def pod_ready(item: Dict[str, Any]) -> bool:
    for condition in (item.get("status") or {}).get("conditions") or []:
        if condition.get("type") == "Ready":
            return condition.get("status") == "True"
    return False


def pod_phase(item: Dict[str, Any]) -> str:
    return str(((item.get("status") or {}).get("phase")) or "")


def restart_count(item: Dict[str, Any]) -> int:
    return sum(int(status.get("restartCount") or 0) for status in (item.get("status") or {}).get("containerStatuses") or [])


def container_names(item: Dict[str, Any]) -> List[str]:
    return [str(container.get("name") or "") for container in (item.get("spec") or {}).get("containers") or [] if container.get("name")]


def running_container_names(item: Dict[str, Any]) -> List[str]:
    result: List[str] = []
    for status in (item.get("status") or {}).get("containerStatuses") or []:
        if (status.get("state") or {}).get("running") and status.get("name"):
            result.append(str(status.get("name")))
    return result


def exec_container_name(item: Dict[str, Any]) -> str:
    running = running_container_names(item)
    if running:
        return running[0]
    names = container_names(item)
    return names[0] if names else ""


def labels_text(item: Dict[str, Any]) -> str:
    labels = ((item.get("metadata") or {}).get("labels")) or {}
    return " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in labels.items())


def is_mongodb_pod(item: Dict[str, Any]) -> bool:
    name = pod_name(item).lower()
    text = labels_text(item)
    return any(token in name or token in text for token in ("mongo", "mongos", "shard", "configsvr", "mongodb"))


def is_coredns_pod(item: Dict[str, Any]) -> bool:
    name = pod_name(item).lower()
    text = labels_text(item)
    return "coredns" in name or "kube-dns" in name or "coredns" in text or "kube-dns" in text


def probe_pod_score(item: Dict[str, Any], target_refs: List[str]) -> int:
    score = 0
    if pod_name(item) in set(target_refs):
        score += 40
    if is_mongodb_pod(item):
        score += 20
    if pod_phase(item) == "Running":
        score += 20
    if not pod_ready(item):
        score += 15
    score += min(restart_count(item), 20)
    if "operator" in pod_name(item).lower():
        score -= 30
    return score


def select_probe_pods(pods: List[Dict[str, Any]], namespace: str, target_refs: List[str]) -> List[Dict[str, Any]]:
    candidates = [item for item in pods if pod_namespace(item) == namespace and is_mongodb_pod(item) and pod_phase(item) == "Running"]
    unhealthy = [item for item in candidates if not pod_ready(item) or restart_count(item) > 0 or pod_name(item) in set(target_refs)]
    healthy = [item for item in candidates if pod_ready(item)]
    selected: List[Dict[str, Any]] = []
    for group in (unhealthy, healthy):
        for item in sorted(group, key=lambda pod: probe_pod_score(pod, target_refs), reverse=True):
            if not exec_container_name(item):
                continue
            if pod_name(item) in {pod_name(existing) for existing in selected}:
                continue
            selected.append(item)
            break
    if selected:
        return selected[:2]
    return [item for item in sorted(candidates, key=lambda pod: probe_pod_score(pod, target_refs), reverse=True) if exec_container_name(item)][:2]


def is_exec_unavailable(text: str) -> bool:
    lowered = text.lower()
    return "unable to upgrade connection" in lowered or "container not found" in lowered or "container not running" in lowered


def is_probe_tool_unavailable(text: str) -> bool:
    lowered = text.lower()
    return (
        "dns probe tool unavailable" in lowered
        or "getent/nslookup/busybox not found" in lowered
        or "failed to run command 'nslookup'" in lowered
        or "failed to run command 'busybox'" in lowered
    )


def service_hostnames(services: List[Dict[str, Any]], namespace: str) -> List[str]:
    names: List[str] = ["kubernetes.default.svc.cluster.local"]
    for item in services:
        meta = item.get("metadata") or {}
        if str(meta.get("namespace") or "") != namespace:
            continue
        name = str(meta.get("name") or "")
        if not name:
            continue
        labels = " ".join("%s=%s" % (str(k).lower(), str(v).lower()) for k, v in (meta.get("labels") or {}).items())
        if "mongo" not in name.lower() and "mongo" not in labels:
            continue
        names.append(name)
        names.append("%s.%s.svc.cluster.local" % (name, namespace))
    result: List[str] = []
    for item in names:
        if item not in result:
            result.append(item)
    return result[:4]


def blocked_payload(output_file: str, script_id: str, started_at: str, summary: str, gap: str) -> None:
    finished_at = now_iso()
    evidence_gap = {
        "gap": gap,
        "gap_type": "critical_gap",
        "related_stage": "directed_recollection",
        "why_important": "DNS startup errors require current CoreDNS and in-cluster lookup evidence before they can support a mechanism-level conclusion.",
        "affects": ["mechanism", "root_cause"],
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
                    "name": "collect CoreDNS and DNS probe evidence",
                    "target": "dns",
                    "method": "kubectl get pods/services/endpoints + kubectl exec DNS probe",
                    "status": "blocked",
                    "performed_at": finished_at,
                }
            ],
            "successful_items": [],
            "failed_items": [{"item": "dns", "reason": summary, "impact": "DNS mechanism remains unvalidated"}],
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
    script_id = str(context.get("script_id") or "mongodb.collect.dns.coredns")
    namespace = str(context.get("namespace") or ((context.get("targets") or {}).get("namespace") or ""))
    if not namespace:
        raise ValueError("context-file missing namespace")

    os.makedirs(os.path.join(artifact_dir, "raw"), exist_ok=True)
    kubectl = shutil.which("kubectl")
    if not kubectl:
        blocked_payload(output_file, script_id, started_at, "kubectl command not found", "DNS evidence not collected")
        return 0

    artifacts: List[Dict[str, Any]] = []
    warnings: List[str] = []
    failed_items: List[Dict[str, Any]] = []
    successful_items: List[Dict[str, Any]] = []
    signals: List[Dict[str, Any]] = []

    pods_proc = run([kubectl, "get", "pods", "-A", "-o", "json"], timeout=45)
    pods_relpath = os.path.join("raw", "pods-all-for-dns.json")
    with open(os.path.join(artifact_dir, pods_relpath), "w", encoding="utf-8") as fh:
        fh.write(pods_proc.stdout)
        if pods_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(pods_proc.stderr)
    artifacts.append({"path": pods_relpath, "kind": "raw_command_output", "description": "all pods used to inspect CoreDNS and choose DNS probe pod"})
    if pods_proc.returncode != 0:
        blocked_payload(output_file, script_id, started_at, "kubectl get pods -A failed", "CoreDNS pod state not collected")
        return 0
    pods_payload = json.loads(pods_proc.stdout or "{}")
    pods = [item for item in pods_payload.get("items") or [] if isinstance(item, dict)]

    services_proc = run([kubectl, "get", "services", "-A", "-o", "json"], timeout=30)
    services_relpath = os.path.join("raw", "services-all-for-dns.json")
    with open(os.path.join(artifact_dir, services_relpath), "w", encoding="utf-8") as fh:
        fh.write(services_proc.stdout)
        if services_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(services_proc.stderr)
    artifacts.append({"path": services_relpath, "kind": "raw_command_output", "description": "all services used to select DNS probe hostnames"})
    services = []
    if services_proc.returncode == 0:
        services = [item for item in (json.loads(services_proc.stdout or "{}").get("items") or []) if isinstance(item, dict)]
    else:
        failed_items.append({"item": "services", "reason": services_proc.stderr.strip() or "kubectl get services failed", "impact": "DNS hostname selection may be incomplete"})

    endpoints_proc = run([kubectl, "get", "endpoints", "-A", "-o", "json"], timeout=30)
    endpoints_relpath = os.path.join("raw", "endpoints-all-for-dns.json")
    with open(os.path.join(artifact_dir, endpoints_relpath), "w", encoding="utf-8") as fh:
        fh.write(endpoints_proc.stdout)
        if endpoints_proc.stderr:
            fh.write("\n# stderr\n")
            fh.write(endpoints_proc.stderr)
    artifacts.append({"path": endpoints_relpath, "kind": "raw_command_output", "description": "all endpoints used to validate kube-dns endpoints"})
    if endpoints_proc.returncode != 0:
        failed_items.append({"item": "endpoints", "reason": endpoints_proc.stderr.strip() or "kubectl get endpoints failed", "impact": "kube-dns endpoints may remain unvalidated"})

    coredns_pods = [
        {
            "name": pod_name(item),
            "namespace": pod_namespace(item),
            "phase": pod_phase(item),
            "ready": pod_ready(item),
            "restart_count": restart_count(item),
            "node_ref": (item.get("spec") or {}).get("nodeName"),
            "collected_at": now_iso(),
        }
        for item in pods
        if is_coredns_pod(item)
    ]
    if coredns_pods:
        successful_items.append({"item": "coredns_pods", "source": "kubectl get pods -A", "note": "%d CoreDNS/kube-dns pod(s)" % len(coredns_pods)})
    else:
        failed_items.append({"item": "coredns_pods", "reason": "no CoreDNS/kube-dns pods detected", "impact": "DNS control-plane health not established"})

    for item in coredns_pods:
        if item.get("phase") != "Running" or item.get("ready") is not True:
            signals.append(
                {
                    "signal_id": "dns-control-plane-unhealthy",
                    "severity": "high",
                    "object_ref": "pod/%s" % item.get("name"),
                    "detail": "CoreDNS/kube-dns pod phase=%s ready=%s restart_count=%s node=%s"
                    % (item.get("phase"), item.get("ready"), item.get("restart_count"), item.get("node_ref")),
                }
            )

    target_refs = [str(item) for item in ((context.get("targets") or {}).get("pod_refs") or []) if item]
    probe_pods = select_probe_pods(pods, namespace, target_refs)
    if not probe_pods:
        failed_items.append({"item": "dns_probe", "reason": "no running MongoDB pod available for DNS probe", "impact": "in-cluster DNS behavior remains unvalidated"})

    hostnames = service_hostnames(services, namespace)
    dns_checks: List[Dict[str, Any]] = []
    for pod in probe_pods:
        pod_ref = pod_name(pod)
        container_name = exec_container_name(pod)
        for hostname in hostnames:
            quoted_hostname = shlex.quote(hostname)
            probe = (
                "run_dns_tool() { "
                "tool=\"$1\"; shift; "
                "if command -v timeout >/dev/null 2>&1; then timeout 5 \"$tool\" \"$@\"; else \"$tool\" \"$@\"; fi; "
                "rc=\"$?\"; "
                "if [ \"$rc\" -eq 124 ]; then echo \"DNS probe timed out while running $tool for " + quoted_hostname + "\" >&2; fi; "
                "exit \"$rc\"; "
                "}; "
                "if command -v getent >/dev/null 2>&1; then "
                "run_dns_tool getent hosts " + quoted_hostname + "; "
                "elif command -v nslookup >/dev/null 2>&1; then "
                "run_dns_tool nslookup " + quoted_hostname + "; "
                "elif command -v busybox >/dev/null 2>&1; then "
                "run_dns_tool busybox nslookup " + quoted_hostname + "; "
                "else "
                "echo 'DNS probe tool unavailable: getent/nslookup/busybox not found' >&2; "
                "exit 127; "
                "fi"
            )
            command = [kubectl, "exec", "-n", namespace, pod_ref]
            if container_name:
                command.extend(["-c", container_name])
            command.extend(["--", "sh", "-lc", probe])
            proc = run_probe(command, timeout=7)
            relpath = os.path.join("raw", "dns-probe-%s-%s.txt" % (safe_name(pod_ref), safe_name(hostname)))
            output = (proc.stdout or "") + ("\n# stderr\n" + proc.stderr if proc.stderr else "")
            with open(os.path.join(artifact_dir, relpath), "w", encoding="utf-8") as fh:
                fh.write(output)
            artifacts.append({"path": relpath, "kind": "raw_command_output", "description": "DNS probe from pod/%s for %s" % (pod_ref, hostname)})
            text = output.lower()
            exec_unavailable = is_exec_unavailable(text)
            probe_tool_unavailable = is_probe_tool_unavailable(text)
            dns_failure_tokens = ("timed out", "timeout", "connection refused", "no servers could be reached", "server can't find", "temporary failure")
            dns_failure_text = any(token in text for token in dns_failure_tokens)
            ambiguous_timeout = proc.returncode == 124 and not dns_failure_text
            failed = (not exec_unavailable) and (not probe_tool_unavailable) and (not ambiguous_timeout) and (
                proc.returncode != 0 or dns_failure_text
            )
            status = "blocked" if exec_unavailable or probe_tool_unavailable or ambiguous_timeout else ("failed" if failed else "success")
            check = {
                "check_id": "%s:%s" % (pod_ref, hostname),
                "source_pod_ref": pod_ref,
                "namespace": namespace,
                "container_name": container_name,
                "hostname": hostname,
                "status": status,
                "exit_code": proc.returncode,
                "artifact_path": relpath,
                "sample": output.strip()[:500],
                "collected_at": now_iso(),
            }
            dns_checks.append(check)
            if exec_unavailable:
                failed_items.append({"item": "dns/%s from pod/%s" % (hostname, pod_ref), "reason": output.strip()[:500] or "kubectl exec unavailable", "impact": "DNS probe could not run from this Pod"})
            elif probe_tool_unavailable:
                failed_items.append({"item": "dns/%s from pod/%s" % (hostname, pod_ref), "reason": output.strip()[:500] or "DNS probe tool unavailable", "impact": "DNS probe command is unavailable inside this Pod; DNS mechanism remains unvalidated"})
            elif ambiguous_timeout:
                failed_items.append({"item": "dns/%s from pod/%s" % (hostname, pod_ref), "reason": output.strip()[:500] or "DNS probe timed out without DNS-layer error text", "impact": "DNS probe result is ambiguous and should not be treated as DNS resolution failure"})
            elif failed:
                signals.append(
                    {
                        "signal_id": "dns-resolution-failed",
                        "severity": "high",
                        "object_ref": "pod/%s" % pod_ref,
                        "detail": "DNS probe failed for %s from pod/%s: %s" % (hostname, pod_ref, output.strip()[:500]),
                    }
                )
            else:
                successful_items.append({"item": "dns/%s" % hostname, "source": "pod/%s" % pod_ref, "note": "lookup succeeded"})

    finished_at = now_iso()
    evidence_gaps: List[Dict[str, Any]] = []
    if not dns_checks:
        evidence_gaps.append(
            {
                "gap": "DNS probe did not run from any MongoDB pod",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "DNS startup errors cannot be promoted beyond a hypothesis without a current in-cluster DNS check.",
                "recommended_action": "run a read-only DNS probe from a healthy workload pod or inspect CoreDNS logs",
                "affects": ["mechanism", "root_cause"],
            }
        )
    elif not any(item.get("status") in ("success", "failed") for item in dns_checks):
        evidence_gaps.append(
            {
                "gap": "DNS probe command was blocked in selected MongoDB pod(s)",
                "gap_type": "critical_gap",
                "related_stage": "directed_recollection",
                "why_important": "DNS lookup errors in startup logs require a runnable in-cluster probe or equivalent CoreDNS evidence before promoting DNS to a supported mechanism.",
                "recommended_action": "run DNS lookup from a diagnostic pod or inspect CoreDNS logs/endpoints with read-only kubectl commands",
                "affects": ["mechanism", "root_cause"],
            }
        )

    status = "partial" if failed_items or evidence_gaps else "success"
    payload = {
        "script_id": script_id,
        "status": status,
        "summary": "collected CoreDNS state and %d DNS probe result(s)" % len(dns_checks),
        "started_at": started_at,
        "finished_at": finished_at,
        "artifacts": artifacts,
        "structured_record_patch": {
            "details": {
                "coredns_pods": coredns_pods,
                "dns_checks": dns_checks,
            }
        },
        "signal_bundle_patch": {
            "abnormal_signals": signals,
        },
        "collection_report_patch": {
            "collection_actions": [
                {
                    "action_id": make_action_id(script_id),
                    "name": "collect CoreDNS and DNS probe evidence",
                    "target": namespace,
                    "method": "kubectl get pods/services/endpoints + kubectl exec DNS probe",
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
    except (ValueError, IndexError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
PY
