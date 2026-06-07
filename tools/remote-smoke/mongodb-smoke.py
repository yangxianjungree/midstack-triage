#!/usr/bin/env python3

import argparse
import json
import os
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_OUTPUT = ROOT / ".local" / "remote-runs"
DEFAULT_REMOTE_ROOT = "/tmp/midstack-triage"


SCRIPT_SOURCES = {
    "mongodb.collect.pods.state": "domains/mongodb/scripts/collect/collect-pods-state.sh",
    "mongodb.collect.statefulsets.yaml": "domains/mongodb/scripts/collect/collect-statefulsets-yaml.sh",
    "mongodb.collect.services.yaml": "domains/mongodb/scripts/collect/collect-services-yaml.sh",
    "mongodb.collect.nodes.state": "domains/mongodb/scripts/collect/collect-nodes-state.sh",
    "mongodb.collect.mongos.get_shard_map": "domains/mongodb/scripts/collect/collect-mongos-get-shard-map.sh",
    "mongodb.collect.replicaset.rs_status": "domains/mongodb/scripts/collect/collect-replicaset-rs-status.sh",
    "mongodb.collect.logs.current": "domains/mongodb/scripts/collect/collect-logs-current.sh",
    "mongodb.collect.logs.previous": "domains/mongodb/scripts/collect/collect-logs-previous.sh",
    "mongodb.normalize.logs.highlights": "domains/mongodb/scripts/normalize/normalize-logs-highlights.py",
    "mongodb.normalize.signals.bundle": "domains/mongodb/scripts/normalize/normalize-signals-bundle.py",
}


REMOTE_NAMES = {
    "mongodb.collect.pods.state": "collect-pods-state.sh",
    "mongodb.collect.statefulsets.yaml": "collect-statefulsets-yaml.sh",
    "mongodb.collect.services.yaml": "collect-services-yaml.sh",
    "mongodb.collect.nodes.state": "collect-nodes-state.sh",
    "mongodb.collect.mongos.get_shard_map": "collect-mongos-get-shard-map.sh",
    "mongodb.collect.replicaset.rs_status": "collect-replicaset-rs-status.sh",
    "mongodb.collect.logs.current": "collect-logs-current.sh",
    "mongodb.collect.logs.previous": "collect-logs-previous.sh",
    "mongodb.normalize.logs.highlights": "normalize-logs-highlights.py",
    "mongodb.normalize.signals.bundle": "normalize-signals-bundle.py",
}


def now_id() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


def load_config(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def ssh_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str]]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target = "%s@%s" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=8",
        "-p",
        str(access.get("port", 22)),
        target,
    ]
    return base, env


def scp_base(access: Dict[str, Any]) -> Tuple[List[str], Dict[str, str], str]:
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    target_prefix = "%s@%s:" % (access["username"], access["primary_ip"])
    base = [
        "sshpass",
        "-e",
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-P",
        str(access.get("port", 22)),
    ]
    return base, env, target_prefix


def run_ssh(access: Dict[str, Any], remote_script: str, timeout: int = 60) -> subprocess.CompletedProcess:
    base, env = ssh_base(access)
    return subprocess.run(
        base + ["bash -lc %s" % shlex.quote(remote_script)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )


def scp_to(access: Dict[str, Any], local_path: Path, remote_path: str) -> None:
    base, env, target_prefix = scp_base(access)
    proc = subprocess.run(
        base + [str(local_path), target_prefix + remote_path],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError("scp_to failed for %s: %s" % (local_path, proc.stderr.strip()))


def scp_from(access: Dict[str, Any], remote_path: str, local_path: Path, recursive: bool = False) -> None:
    base, env, target_prefix = scp_base(access)
    cmd = base[:]
    if recursive:
        cmd.append("-r")
    proc = subprocess.run(
        cmd + [target_prefix + remote_path, str(local_path)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError("scp_from failed for %s: %s" % (remote_path, proc.stderr.strip()))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def choose_namespace(access: Dict[str, Any], preferred: List[str]) -> str:
    ns_list = " ".join(shlex.quote(item) for item in preferred)
    proc = run_ssh(
        access,
        "for ns in %s; do kubectl get namespace \"$ns\" -o name >/dev/null 2>&1 && echo \"$ns\" && exit 0; done; echo default" % ns_list,
    )
    if proc.returncode != 0:
        return "default"
    return (proc.stdout.strip() or "default").splitlines()[-1]


def collect_inventory(access: Dict[str, Any], local_dir: Path) -> None:
    remote = r"""
set -o pipefail
echo "## kubectl client"
kubectl version --client=true --short 2>/dev/null || kubectl version --client=true
echo "## nodes"
kubectl get nodes -o wide
echo "## namespaces"
kubectl get namespaces
echo "## statefulsets"
kubectl get statefulsets -A
echo "## services"
kubectl get services -A | head -n 200
echo "## pods"
kubectl get pods -A -o wide | head -n 200
"""
    proc = run_ssh(access, remote, timeout=90)
    (local_dir / "inventory.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (local_dir / "inventory.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError("kubectl inventory failed: %s" % proc.stderr.strip())


def build_context(incident_id: str, script_id: str, namespace: str, local_artifact_root: Path, remote_root: str) -> Dict[str, Any]:
    run_root = "%s/runs/%s" % (remote_root, incident_id)
    return {
        "incident_id": incident_id,
        "middleware": "mongodb",
        "script_id": script_id,
        "namespace": namespace,
        "cluster_id": "remote-smoke",
        "artifact_root": str(local_artifact_root),
        "deployment_architecture": "unknown",
        "topology_type": "sharded_cluster",
        "targets": {
            "namespace": namespace,
            "statefulset_refs": [],
            "service_refs": [],
            "pod_refs": [],
            "node_refs": [],
            "mongos_pod_ref": "",
        },
        "capabilities": {
            "kubectl_available": True,
            "kubectl_exec_available": True,
            "mongosh_in_pod_available": True,
        },
        "pod_query": {"mode": "by_namespace_scan"},
        "statefulset_query": {"include_yaml": True},
        "service_query": {"include_nodeport": True, "include_yaml": True},
        "node_query": {"resolve_from_pods": True},
        "mongos_query": {
            "shell": "mongosh",
            "database": "admin",
            "command": "getShardMap",
            "username": "root",
            "password_file_env": "MONGODB_ROOT_PASSWORD_FILE",
            "auth_database": "admin",
        },
        "replicaset_query": {
            "shell": "mongosh",
            "username": "root",
            "password_file_env": "MONGODB_ROOT_PASSWORD_FILE",
            "auth_database": "admin",
        },
        "logs_query": {"tail_lines": 1000},
        "normalize_query": {"per_file_highlight_limit": 50, "total_highlight_limit": 500},
        "inputs": {
            "log_artifact_dirs": {
                "current": "%s/mongodb.collect.logs.current/artifacts" % run_root,
                "previous": "%s/mongodb.collect.logs.previous/artifacts" % run_root,
            },
            "script_output_files": {
                upstream: "%s/%s/output.yaml" % (run_root, upstream)
                for upstream in SCRIPT_SOURCES
                if upstream != "mongodb.normalize.signals.bundle"
            },
        },
    }


def run_script(
    access: Dict[str, Any],
    incident_id: str,
    script_id: str,
    remote_script_path: str,
    namespace: str,
    local_dir: Path,
    remote_root: str,
) -> None:
    remote_run_root = "%s/runs/%s/%s" % (remote_root, incident_id, script_id)
    remote_context = "%s/context.yaml" % remote_run_root
    remote_output = "%s/output.yaml" % remote_run_root
    remote_artifacts = "%s/artifacts" % remote_run_root
    local_script_dir = local_dir / script_id
    local_script_dir.mkdir(parents=True, exist_ok=True)

    context = build_context(incident_id, script_id, namespace, local_script_dir / "artifacts", remote_root)
    context_path = local_script_dir / "context.yaml"
    write_json(context_path, context)

    mkdir_proc = run_ssh(access, "mkdir -p %s %s" % (shlex.quote(remote_run_root), shlex.quote(remote_artifacts)))
    if mkdir_proc.returncode != 0:
        raise RuntimeError("remote mkdir failed: %s" % mkdir_proc.stderr.strip())
    scp_to(access, context_path, remote_context)

    runner = "python3" if remote_script_path.endswith(".py") else "bash"
    command = (
        "%s %s --context-file %s --output-file %s --artifact-dir %s"
        % (runner, shlex.quote(remote_script_path), shlex.quote(remote_context), shlex.quote(remote_output), shlex.quote(remote_artifacts))
    )
    proc = run_ssh(access, command, timeout=120)
    (local_script_dir / "remote.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (local_script_dir / "remote.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    (local_script_dir / "exit_code.txt").write_text(str(proc.returncode), encoding="utf-8")
    if proc.returncode != 0:
        return

    scp_from(access, remote_output, local_script_dir / "output.yaml")
    artifact_dest = local_script_dir / "artifacts"
    if artifact_dest.exists():
        shutil.rmtree(artifact_dest)
    try:
        scp_from(access, remote_artifacts, artifact_dest, recursive=True)
    except RuntimeError as exc:
        (local_script_dir / "artifact_retrieval_error.txt").write_text(str(exc), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MongoDB MVP scripts against a remote Kubernetes environment.")
    parser.add_argument("--config", required=True, help="Path to ignored local environment config YAML.")
    parser.add_argument("--output-dir", default=str(DEFAULT_LOCAL_OUTPUT), help="Local directory for smoke test results.")
    parser.add_argument("--remote-root", default=DEFAULT_REMOTE_ROOT, help="Remote plugin root under /tmp.")
    parser.add_argument("--namespace", default="", help="Explicit namespace. If omitted, a known MongoDB namespace is selected.")
    parser.add_argument("--namespace-candidates", default="mongo,psmdb-test,mongodb,default", help="Comma-separated namespace candidates.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(Path(args.config))
    access = cfg["access"]
    remote_root = args.remote_root
    incident_id = "mongodb-remote-smoke-%s" % now_id()
    local_dir = Path(args.output_dir) / incident_id
    local_dir.mkdir(parents=True, exist_ok=True)

    remote_mongodb_dir = "%s/assets/scripts/mongodb" % remote_root
    prep = run_ssh(access, "mkdir -p %s" % shlex.quote(remote_mongodb_dir))
    if prep.returncode != 0:
        raise RuntimeError("remote script dir create failed: %s" % prep.stderr.strip())

    remote_paths = {}
    for script_id, relpath in SCRIPT_SOURCES.items():
        local_path = ROOT / relpath
        remote_path = "%s/%s" % (remote_mongodb_dir, REMOTE_NAMES[script_id])
        remote_paths[script_id] = remote_path
        scp_to(access, local_path, remote_path)

    chmod = run_ssh(access, "chmod +x %s/*.sh" % shlex.quote(remote_mongodb_dir))
    if chmod.returncode != 0:
        raise RuntimeError("remote chmod failed: %s" % chmod.stderr.strip())

    if args.namespace:
        namespace = args.namespace
    else:
        namespace = choose_namespace(access, [item.strip() for item in args.namespace_candidates.split(",") if item.strip()])
    (local_dir / "selected_namespace.txt").write_text(namespace, encoding="utf-8")
    collect_inventory(access, local_dir)

    for script_id in SCRIPT_SOURCES:
        run_script(access, incident_id, script_id, remote_paths[script_id], namespace, local_dir, remote_root)

    print("incident_id=%s" % incident_id)
    print("selected_namespace=%s" % namespace)
    print("local_dir=%s" % local_dir)
    for script_id in SCRIPT_SOURCES:
        script_dir = local_dir / script_id
        output = script_dir / "output.yaml"
        exit_code = (script_dir / "exit_code.txt").read_text(encoding="utf-8") if (script_dir / "exit_code.txt").exists() else "missing"
        if output.exists():
            data = yaml.safe_load(output.read_text(encoding="utf-8")) or {}
            print("%s: exit=%s status=%s summary=%s" % (script_id, exit_code, data.get("status"), data.get("summary")))
        else:
            stderr = (script_dir / "remote.stderr.txt").read_text(encoding="utf-8").strip() if (script_dir / "remote.stderr.txt").exists() else ""
            print("%s: exit=%s output=missing stderr=%s" % (script_id, exit_code, stderr[:200]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
