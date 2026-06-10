#!/usr/bin/env python3

import argparse
import os
import json
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml


ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = ROOT / "tools" / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

from patch_merge import apply_script_output  # noqa: E402


MONGODB_DISCOVERY_HINTS = ("mongo", "mongodb", "mongos", "mongod", "configsvr", "shard", "psmdb", "percona")
INCIDENT_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"
ANALYSABLE_STATUSES = ("ready", "analysed")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML object" % path)
    return data


def write_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, allow_unicode=False)


def adapter_output(command: str, incident_id: str, middleware: str, status: str, summary: str, output_dir: Path) -> Dict[str, Any]:
    return {
        "plugin_name": "midstack-triage-local",
        "command": command,
        "incident_id": incident_id,
        "middleware": middleware,
        "status": status,
        "summary": summary,
        "user_message": summary,
        "record_refs": [
            {
                "name": "incident_dir",
                "path": str(output_dir),
                "description": "local incident directory",
            }
        ],
        "next_actions": [],
        "blocking_items": [],
        "warnings": [],
        "generated_at": now_iso(),
    }


def add_record_ref_if_exists(output: Dict[str, Any], output_dir: Path, name: str, filename: str, description: str) -> None:
    path = output_dir / filename
    if path.exists():
        output["record_refs"].append({"name": name, "path": str(path), "description": description})


def rand4() -> str:
    return "".join(secrets.choice(INCIDENT_ID_ALPHABET) for _ in range(4))


def generated_incident_id(middleware: str) -> str:
    return "%s-%s-%s" % (middleware, datetime.now().strftime("%Y%m%d-%H%M%S"), rand4())


def unique_incident_id(middleware: str, output_root: Path) -> str:
    for _ in range(20):
        incident_id = generated_incident_id(middleware)
        if not (output_root / incident_id).exists():
            return incident_id
    return generated_incident_id(middleware)


def load_incident_meta(incident_dir: Path) -> Dict[str, Any]:
    meta_file = incident_dir / "meta.yaml"
    if not meta_file.exists():
        return {}
    return load_yaml(meta_file)


def update_incident_meta(incident_dir: Path, updates: Dict[str, Any]) -> None:
    meta_file = incident_dir / "meta.yaml"
    if not meta_file.exists():
        return
    meta = load_yaml(meta_file)
    meta.update(updates)
    meta["updated_at"] = now_iso()
    write_yaml(meta_file, meta)


def write_blocked_output(
    command: str,
    incident_id: str,
    middleware: str,
    output_dir: Path,
    summary: str,
    blocking_items: List[Dict[str, Any]],
    next_actions: List[str],
    output_filename: str = "adapter-output.yaml",
) -> int:
    output = adapter_output(command, incident_id, middleware, "blocked", summary, output_dir)
    output["blocking_items"] = blocking_items
    output["next_actions"] = next_actions
    write_yaml(output_dir / output_filename, output)
    print(str(output_dir))
    return 0


def path_from_arg(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def current_incident_marker(output_root: Path) -> Path:
    return output_root / ".current-incident"


def write_current_incident(output_root: Path, incident_dir: Path) -> None:
    marker = current_incident_marker(output_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(str(incident_dir) + "\n", encoding="utf-8")


def read_current_incident(output_root: Path) -> Path:
    marker = current_incident_marker(output_root)
    if not marker.exists():
        raise FileNotFoundError("current incident marker does not exist: %s" % marker)
    value = marker.read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError("current incident marker is empty: %s" % marker)
    return resolve_path(value)


def ssh_command(access: Dict[str, Any], remote_command: str) -> List[str]:
    return [
        "sshpass",
        "-e",
        "ssh",
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
        "-p",
        str(access.get("port", 22)),
        "%s@%s" % (access["username"], access["primary_ip"]),
        "bash -lc %s" % json.dumps(remote_command),
    ]


def run_env_check(access: Dict[str, Any], remote_command: str) -> Dict[str, Any]:
    if not shutil.which("sshpass"):
        return {"status": "failed", "stdout": "", "stderr": "sshpass is not installed"}
    env = os.environ.copy()
    env["SSHPASS"] = str(access["password"])
    try:
        proc = subprocess.run(
            ssh_command(access, remote_command),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "stdout": exc.stdout or "",
            "stderr": "remote command timed out after 30s: %s" % remote_command,
            "exit_code": 124,
        }
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "exit_code": proc.returncode,
    }


def validate_remote_environment(access: Dict[str, Any]) -> Dict[str, Any]:
    checks = [
        {"check_id": "ssh", "command": "echo ok"},
        {"check_id": "kubectl-client", "command": "kubectl version --client=true >/dev/null"},
        {"check_id": "kubectl-nodes", "command": "kubectl get nodes -o name >/dev/null"},
    ]
    results = []
    for item in checks:
        result = run_env_check(access, item["command"])
        result["check_id"] = item["check_id"]
        results.append(result)
        if result["status"] != "passed":
            break
    return {"status": "passed" if all(item["status"] == "passed" for item in results) else "failed", "checks": results}


def object_matches_mongodb(obj: Dict[str, Any]) -> bool:
    text = json.dumps(obj, ensure_ascii=False).lower()
    name = object_name(obj).lower()
    data_plane_hints = ("mongos", "mongod", "configsvr", "shard", "replica", "rs", "data")
    if "operator" in name and not any(hint in text for hint in data_plane_hints):
        return False
    return any(hint in text for hint in MONGODB_DISCOVERY_HINTS)


def object_namespace(obj: Dict[str, Any]) -> str:
    metadata = obj.get("metadata") or {}
    return str(metadata.get("namespace") or "")


def object_name(obj: Dict[str, Any]) -> str:
    metadata = obj.get("metadata") or {}
    return str(metadata.get("name") or "")


def condition_summary(status: Dict[str, Any]) -> List[Dict[str, str]]:
    summary = []
    for condition in status.get("conditions") or []:
        summary.append(
            {
                "type": str(condition.get("type") or ""),
                "status": str(condition.get("status") or ""),
                "reason": str(condition.get("reason") or ""),
                "message": str(condition.get("message") or ""),
            }
        )
    return summary


def compact_k8s_object(kind: str, obj: Dict[str, Any]) -> Dict[str, Any]:
    metadata = obj.get("metadata") or {}
    spec = obj.get("spec") or {}
    status = obj.get("status") or {}
    record: Dict[str, Any] = {
        "kind": kind,
        "namespace": object_namespace(obj),
        "name": object_name(obj),
        "labels": metadata.get("labels") or {},
    }
    if kind == "Pod":
        record.update(
            {
                "phase": status.get("phase"),
                "node_name": spec.get("nodeName"),
                "restart_policy": spec.get("restartPolicy"),
            }
        )
    elif kind == "StatefulSet":
        record.update(
            {
                "replicas": spec.get("replicas"),
                "ready_replicas": status.get("readyReplicas"),
                "current_replicas": status.get("currentReplicas"),
                "updated_replicas": status.get("updatedReplicas"),
            }
        )
    elif kind == "Service":
        ports = []
        for port in spec.get("ports") or []:
            ports.append(
                {
                    "name": port.get("name"),
                    "port": port.get("port"),
                    "target_port": port.get("targetPort"),
                    "node_port": port.get("nodePort"),
                    "protocol": port.get("protocol"),
                }
            )
        record.update({"type": spec.get("type"), "ports": ports})
    elif kind == "Node":
        record.update(
            {
                "conditions": condition_summary(status),
                "capacity": status.get("capacity") or {},
                "allocatable": status.get("allocatable") or {},
            }
        )
    elif kind == "Event":
        involved = obj.get("involvedObject") or obj.get("regarding") or {}
        series = obj.get("series") or {}
        record.update(
            {
                "type": obj.get("type") or obj.get("deprecatedType") or "",
                "reason": obj.get("reason") or "",
                "message": obj.get("message") or obj.get("note") or "",
                "involved_object": {
                    "kind": involved.get("kind") or "",
                    "namespace": involved.get("namespace") or "",
                    "name": involved.get("name") or "",
                },
                "first_timestamp": obj.get("firstTimestamp") or obj.get("deprecatedFirstTimestamp") or obj.get("eventTime") or "",
                "last_timestamp": obj.get("lastTimestamp") or obj.get("deprecatedLastTimestamp") or series.get("lastObservedTime") or obj.get("eventTime") or "",
            }
        )
    return record


def mongodb_role_hints(obj: Dict[str, Any]) -> List[str]:
    text = json.dumps(obj, ensure_ascii=False).lower()
    roles = []
    for role, hints in (
        ("mongos", ("mongos",)),
        ("configsvr", ("configsvr", "config-server", "configserver")),
        ("shard", ("shard",)),
        ("replicaset", ("replicaset", "replica-set", "rs.")),
        ("operator", ("operator", "psmdb-operator")),
    ):
        if any(hint in text for hint in hints):
            roles.append(role)
    return roles or ["unknown"]


def deployment_architecture_hints(obj: Dict[str, Any]) -> List[str]:
    text = json.dumps(obj, ensure_ascii=False).lower()
    hints = []
    if "bitnami" in text:
        hints.append("bitnami")
    if "percona.com" in text or "psmdb" in text or "psmdb-operator" in text:
        hints.append("operator_crd")
    return hints


def container_specs_for_auth(kind: str, obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    if kind == "Pod":
        spec = obj.get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    if kind == "StatefulSet":
        spec = ((obj.get("spec") or {}).get("template") or {}).get("spec") or {}
        return [item for item in (spec.get("containers") or []) if isinstance(item, dict)]
    return []


def auth_secret_ref_score(env_name: str, key: str, roles: List[str], kind: str) -> int:
    score = 0
    text = ("%s %s" % (env_name, key)).lower()
    if "root" in text:
        score += 30
    if "password" in text:
        score += 20
    if "mongos" in roles or "configsvr" in roles or "shard" in roles or "replicaset" in roles:
        score += 10
    if kind == "StatefulSet":
        score += 5
    return score


def mongodb_auth_secret_refs(kind: str, obj: Dict[str, Any], roles: List[str]) -> List[Dict[str, Any]]:
    namespace = object_namespace(obj)
    source_name = object_name(obj)
    candidates = []
    for container in container_specs_for_auth(kind, obj):
        container_name = str(container.get("name") or "")
        for env in container.get("env") or []:
            if not isinstance(env, dict):
                continue
            secret_key_ref = (((env.get("valueFrom") or {}).get("secretKeyRef")) or {})
            secret_name = str(secret_key_ref.get("name") or "")
            secret_key = str(secret_key_ref.get("key") or "")
            if not secret_name or not secret_key:
                continue
            env_name = str(env.get("name") or "")
            candidates.append(
                {
                    "namespace": namespace,
                    "name": secret_name,
                    "key": secret_key,
                    "env_name": env_name,
                    "source_kind": kind,
                    "source_name": source_name,
                    "source_container": container_name,
                    "score": auth_secret_ref_score(env_name, secret_key, roles, kind),
                }
            )
    return candidates


def append_auth_secret_ref_candidate(target: List[Dict[str, Any]], candidate: Dict[str, Any]) -> None:
    key = (
        str(candidate.get("namespace") or ""),
        str(candidate.get("name") or ""),
        str(candidate.get("key") or ""),
    )
    for index, existing in enumerate(target):
        existing_key = (
            str(existing.get("namespace") or ""),
            str(existing.get("name") or ""),
            str(existing.get("key") or ""),
        )
        if existing_key == key:
            if int(candidate.get("score") or 0) > int(existing.get("score") or 0):
                target[index] = candidate
            return
    target.append(candidate)


def build_auth_hints(selected_namespace: str, auth_candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    scoped = [
        item
        for item in auth_candidates
        if str(item.get("namespace") or "") == selected_namespace
    ]
    scoped.sort(
        key=lambda item: (
            -int(item.get("score") or 0),
            str(item.get("name") or ""),
            str(item.get("key") or ""),
        )
    )
    selected_secret_ref = {}
    if scoped:
        selected_secret_ref = {
            "namespace": str(scoped[0].get("namespace") or ""),
            "name": str(scoped[0].get("name") or ""),
            "key": str(scoped[0].get("key") or ""),
        }
    return {
        "secret_ref_candidates": scoped,
        "selected_secret_ref": selected_secret_ref,
    }


def append_unique(target: List[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def inventory_scope_objects(inventory: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected_namespace = str(inventory.get("selected_namespace") or "")
    objects = [item for item in inventory.get("objects") or [] if isinstance(item, dict)]
    if not selected_namespace:
        return objects
    return [item for item in objects if str(item.get("namespace") or "") == selected_namespace]


def build_mongodb_targets(namespace: str, objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    targets: Dict[str, Any] = {
        "namespace": namespace,
        "statefulset_refs": [],
        "service_refs": [],
        "pod_refs": [],
        "node_refs": [],
        "mongos_pod_ref": "",
    }
    if not namespace:
        return targets
    for item in objects:
        name = str(item.get("name") or "")
        if not name:
            continue
        kind = item.get("kind")
        if kind == "StatefulSet":
            append_unique(targets["statefulset_refs"], name)
        elif kind == "Service":
            append_unique(targets["service_refs"], name)
        elif kind == "Pod":
            append_unique(targets["pod_refs"], name)
            node_name = str(item.get("node_name") or "")
            append_unique(targets["node_refs"], node_name)
            if not targets["mongos_pod_ref"] and "mongos" in (item.get("mongodb_role_hints") or []):
                targets["mongos_pod_ref"] = name
    for key in ("statefulset_refs", "service_refs", "pod_refs", "node_refs"):
        targets[key] = sorted(targets[key])
    return targets


def build_topology_hints(objects: List[Dict[str, Any]]) -> Dict[str, Any]:
    role_counts: Dict[str, int] = {}
    kind_counts: Dict[str, int] = {}
    for item in objects:
        kind = str(item.get("kind") or "unknown")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        for role in item.get("mongodb_role_hints") or ["unknown"]:
            role_counts[str(role)] = role_counts.get(str(role), 0) + 1
    if role_counts.get("mongos") or (role_counts.get("configsvr") and role_counts.get("shard")):
        topology_type = "sharded_cluster"
    elif role_counts.get("replicaset"):
        topology_type = "replica_set"
    else:
        topology_type = "unknown"
    return {
        "candidate_topology_type": topology_type,
        "role_counts": dict(sorted(role_counts.items())),
        "kind_counts": dict(sorted(kind_counts.items())),
    }


def deployment_architecture_candidates(objects: List[Dict[str, Any]]) -> List[str]:
    candidates: List[str] = []
    for item in objects:
        for hint in item.get("deployment_architecture_hints") or []:
            append_unique(candidates, str(hint))
    return sorted(candidates)


def related_event(event: Dict[str, Any], names: List[str]) -> bool:
    involved = event.get("involvedObject") or event.get("regarding") or {}
    return str(involved.get("name") or "") in names


def run_remote_kubectl_json(access: Dict[str, Any], resource: str, namespace: str, namespaced: bool = True) -> Dict[str, Any]:
    if namespaced:
        scope = "-n %s" % namespace if namespace else "-A"
    else:
        scope = ""
    result = run_env_check(access, "kubectl get %s %s -o json" % (resource, scope))
    if result["status"] != "passed":
        return {"status": "failed", "resource": resource, "error": result}
    try:
        payload = json.loads(result.get("stdout") or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "failed", "resource": resource, "error": {"message": str(exc), "stdout": result.get("stdout", "")[:1000]}}
    return {"status": "passed", "resource": resource, "payload": payload}


def discover_mongodb_inventory(access: Dict[str, Any], namespace: str) -> Dict[str, Any]:
    inventory: Dict[str, Any] = {
        "status": "running",
        "middleware": "mongodb",
        "requested_namespace": namespace,
        "selected_namespace": namespace,
        "namespace_source": "user" if namespace else "",
        "candidate_namespaces": [],
        "objects": [],
        "targets": {
            "namespace": namespace,
            "statefulset_refs": [],
            "service_refs": [],
            "pod_refs": [],
            "node_refs": [],
            "mongos_pod_ref": "",
        },
        "deployment_architecture_candidates": [],
        "topology_hints": {},
        "auth_hints": {"secret_ref_candidates": [], "selected_secret_ref": {}},
        "related_nodes": [],
        "related_events": [],
        "errors": [],
    }
    resources = [
        ("Pod", "pods"),
        ("StatefulSet", "statefulsets"),
        ("Service", "services"),
    ]
    candidates = set()
    auth_candidates: List[Dict[str, Any]] = []
    for kind, resource in resources:
        result = run_remote_kubectl_json(access, resource, namespace)
        if result["status"] != "passed":
            inventory["errors"].append({"resource": resource, "error": result.get("error")})
            continue
        for obj in (result.get("payload") or {}).get("items") or []:
            if not object_matches_mongodb(obj):
                continue
            roles = mongodb_role_hints(obj)
            record = compact_k8s_object(kind, obj)
            record["mongodb_role_hints"] = roles
            record["deployment_architecture_hints"] = deployment_architecture_hints(obj)
            inventory["objects"].append(record)
            for candidate in mongodb_auth_secret_refs(kind, obj, roles):
                append_auth_secret_ref_candidate(auth_candidates, candidate)
            if record.get("namespace"):
                candidates.add(str(record["namespace"]))

    inventory["candidate_namespaces"] = sorted(candidates)
    if namespace:
        inventory["status"] = "passed"
        inventory["selected_namespace"] = namespace
        inventory["namespace_source"] = "user"
    elif len(candidates) == 1:
        inventory["status"] = "passed"
        inventory["selected_namespace"] = next(iter(candidates))
        inventory["namespace_source"] = "auto_discovered"
    elif len(candidates) > 1:
        inventory["status"] = "ambiguous"
        inventory["namespace_source"] = "ambiguous"
    else:
        inventory["status"] = "not_found"
        inventory["namespace_source"] = "not_found"

    scope_objects = inventory_scope_objects(inventory)
    selected_namespace = str(inventory.get("selected_namespace") or "")
    inventory["targets"] = build_mongodb_targets(selected_namespace, scope_objects)
    inventory["deployment_architecture_candidates"] = deployment_architecture_candidates(scope_objects)
    inventory["topology_hints"] = build_topology_hints(scope_objects)
    inventory["auth_hints"] = build_auth_hints(selected_namespace, auth_candidates)

    node_names = inventory["targets"].get("node_refs") or []
    if selected_namespace and node_names:
        node_result = run_remote_kubectl_json(access, "nodes", "", namespaced=False)
        if node_result["status"] != "passed":
            inventory["errors"].append({"resource": "nodes", "error": node_result.get("error")})
        else:
            for obj in (node_result.get("payload") or {}).get("items") or []:
                if object_name(obj) in node_names:
                    inventory["related_nodes"].append(compact_k8s_object("Node", obj))

    object_names = sorted(str(item.get("name") or "") for item in scope_objects if item.get("name"))
    if selected_namespace and object_names:
        event_result = run_remote_kubectl_json(access, "events", selected_namespace)
        if event_result["status"] != "passed":
            inventory["errors"].append({"resource": "events", "error": event_result.get("error")})
        else:
            for obj in (event_result.get("payload") or {}).get("items") or []:
                if related_event(obj, object_names):
                    inventory["related_events"].append(compact_k8s_object("Event", obj))
    return inventory


def command_start(args: argparse.Namespace) -> int:
    output_root = path_from_arg(args.output_root)
    incident_id = args.incident_id or unique_incident_id(args.middleware, output_root)
    output_dir = output_root / incident_id
    created_at = now_iso()
    env_ips = [item for item in (args.environment_ip or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    blocking_items = []
    if not args.middleware:
        blocking_items.append({"code": "missing_middleware", "message": "middleware is required", "required_user_action": "provide middleware, for example mongodb"})
    if not primary_ip:
        blocking_items.append({"code": "missing_environment_ip", "message": "environment IP is required", "required_user_action": "provide at least one remote environment IP"})
    if not args.username:
        blocking_items.append({"code": "missing_username", "message": "remote username is required", "required_user_action": "provide remote username"})
    if not args.password:
        blocking_items.append({"code": "missing_password", "message": "remote password is required", "required_user_action": "provide remote password"})

    remote_validation: Dict[str, Any] = {"status": "skipped", "checks": []}
    object_inventory: Dict[str, Any] = {"status": "skipped", "middleware": args.middleware}
    access = {
        "candidate_ips": env_ips,
        "primary_ip": primary_ip,
        "username": args.username,
        "password": args.password,
        "port": args.port,
    }
    if not blocking_items:
        remote_validation = validate_remote_environment(access)
        if remote_validation["status"] != "passed":
            blocking_items.append(
                {
                    "code": "remote_environment_validation_failed",
                    "message": "remote SSH or kubectl validation failed",
                    "required_user_action": "fix remote access, install sshpass locally, or ensure kubectl can access the cluster on the jump host",
                }
            )
        elif args.middleware == "mongodb":
            object_inventory = discover_mongodb_inventory(access, args.namespace)
            if not args.namespace and object_inventory["status"] == "passed":
                args.namespace = str(object_inventory.get("selected_namespace") or "")
            elif not args.namespace and object_inventory["status"] == "ambiguous":
                blocking_items.append(
                    {
                        "code": "multiple_mongodb_namespaces_detected",
                        "message": "multiple MongoDB candidate namespaces were detected",
                        "required_user_action": "provide namespace explicitly",
                        "candidate_namespaces": object_inventory.get("candidate_namespaces") or [],
                    }
                )
            elif not args.namespace and object_inventory["status"] == "not_found":
                blocking_items.append(
                    {
                        "code": "mongodb_namespace_not_detected",
                        "message": "MongoDB namespace could not be auto-detected from pods, statefulsets, or services",
                        "required_user_action": "provide namespace explicitly",
                    }
                )

    status = "ready" if not blocking_items else "blocked"
    write_yaml(output_dir / "environment-check.yaml", {"remote_validation": remote_validation})
    write_yaml(output_dir / "object-inventory.yaml", object_inventory)
    write_yaml(
        output_dir / "meta.yaml",
        {
            "incident_id": incident_id,
            "middleware": args.middleware,
            "status": status,
            "created_at": created_at,
            "updated_at": created_at,
            "plugin_version": "local-prototype",
            "current_command": "start",
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "owner": "local",
            "remote_validation": remote_validation,
        },
    )
    write_yaml(
        output_dir / "input.yaml",
        {
            "middleware": args.middleware,
            "incident_id": incident_id,
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "customer_clue": args.customer_clue,
            "input_source": "local-cli",
            "environment_ips": env_ips,
            "remote_port": args.port,
            "received_at": created_at,
        },
    )
    if primary_ip:
        write_yaml(
            output_dir / "remote-config.yaml",
            {
                "name": "%s-remote" % incident_id,
                "purpose": "incident remote Kubernetes environment",
                "created_at": created_at,
                "access": access,
                "defaults": {
                    "jump_host_strategy": "first_ip",
                    "remote_workspace_root": "/tmp/midstack-triage",
                    "remote_script_root": "/tmp/midstack-triage/assets/scripts",
                    "remote_run_root": "/tmp/midstack-triage/runs",
                    "kubectl_required": True,
                    "kubectl_exec_required": True,
                    "middleware_tools_location": "pod_internal",
                },
            },
        )
    output = adapter_output("start", incident_id, args.middleware, status, "local incident %s is %s" % (incident_id, status), output_dir)
    if status == "ready":
        output["next_actions"] = ["run analyse with --incident-dir %s" % output_dir]
        if object_inventory.get("namespace_source") == "auto_discovered":
            output["summary"] = "%s; namespace auto-discovered as %s" % (output["summary"], object_inventory.get("selected_namespace"))
            output["user_message"] = output["summary"]
    else:
        output["blocking_items"] = blocking_items
        output["warnings"].append("incident is blocked until required input and remote validation pass")
    write_current_incident(output_root, output_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(output_dir))
    return 0


def copy_if_exists(source_dir: Path, output_dir: Path, filename: str) -> None:
    source = source_dir / filename
    if source.exists():
        target = output_dir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def first_context(remote_run_dir: Path) -> Dict[str, Any]:
    for path in sorted(remote_run_dir.glob("*/context.yaml")):
        return load_yaml(path)
    return {}


def script_run_dirs(remote_run_dir: Path) -> List[Path]:
    return sorted(
        path
        for path in remote_run_dir.iterdir()
        if path.is_dir()
        and any((path / filename).exists() for filename in ("output.yaml", "context.yaml", "remote-executor-result.yaml"))
    )


def load_remote_executor_run_result(remote_run_dir: Path) -> Dict[str, Any]:
    path = remote_run_dir / "remote-executor-run.yaml"
    return load_yaml(path) if path.exists() else {}


def copy_remote_run_support_files(remote_run_dir: Path, output_dir: Path) -> None:
    for filename in (
        "remote-executor-run.yaml",
        "capability-checks.yaml",
        "context-profile.yaml",
        "selected_namespace.txt",
        "inventory.stdout.txt",
        "inventory.stderr.txt",
    ):
        copy_if_exists(remote_run_dir, output_dir, filename)


def merge_remote_executor_run_result(collection_report: Dict[str, Any], run_result: Dict[str, Any], has_script_outputs: bool) -> None:
    if not run_result:
        return
    status = str(run_result.get("status") or "")
    if has_script_outputs and status not in ("blocked", "failed"):
        return
    selected_ip = str(run_result.get("selected_ip") or "")
    error = run_result.get("error") or {}
    capability_checks = [item for item in (run_result.get("capability_checks") or []) if isinstance(item, dict)]
    collection_report["collection_actions"].append(
        {
            "action_id": "remote-executor-run",
            "name": "remote executor batch run",
            "target": selected_ip or "remote executor",
            "method": "ssh + staged packaged scripts",
            "status": status or "unknown",
            "performed_at": str(run_result.get("finished_at") or run_result.get("started_at") or ""),
        }
    )
    if status in ("blocked", "failed"):
        collection_report["failed_items"].append(
            {
                "item": "remote-executor/run",
                "reason": str(error.get("message") or "remote executor batch run did not complete successfully"),
                "impact": "script execution evidence may be missing before per-script collection starts",
            }
        )
        note = "remote executor batch run %s" % (status or "unknown")
        if capability_checks:
            note = "%s after %s capability checks" % (note, len(capability_checks))
        collection_report["evidence_gaps"].append(
            {
                "gap": note,
                "related_stage": "signal_collection",
                "why_important": "preflight or staging failures can prevent the incident from collecting any remote evidence",
            }
        )


def remote_executor_required_user_action(code: str) -> str:
    if code == "missing_sshpass":
        return "install sshpass locally and rerun /midstack:analyse"
    if code in ("ssh_unreachable", "ssh_auth_failed"):
        return "fix remote SSH connectivity or credentials, then rerun /midstack:analyse"
    if code in ("kubectl_missing", "k8s_context_unavailable", "kubectl_exec_unavailable"):
        return "fix kubectl or Kubernetes access on the jump host, then rerun /midstack:analyse"
    return "inspect remote-executor-run.yaml and stderr output, then rerun /midstack:analyse"


def remote_executor_next_actions(code: str) -> List[str]:
    return [remote_executor_required_user_action(code)]


def merge_remote_executor_result(collection_report: Dict[str, Any], script_id: str, result: Dict[str, Any]) -> None:
    status = str(result.get("status") or "")
    selected_ip = str(result.get("selected_ip") or "")
    process = result.get("process") or {}
    error = result.get("error") or {}
    warnings = [str(item) for item in (result.get("warnings") or []) if item]
    action = {
        "action_id": "remote-executor-%s" % script_id.replace(".", "-"),
        "name": "remote executor run %s" % script_id,
        "target": selected_ip or script_id,
        "method": "ssh + staged packaged script",
        "status": status or "unknown",
        "performed_at": str(result.get("finished_at") or result.get("started_at") or ""),
    }
    collection_report["collection_actions"].append(action)

    output_ref = str(((result.get("retrieved_files") or {}).get("output_file")) or "")
    artifact_ref = str(((result.get("retrieved_files") or {}).get("artifact_dir")) or "")
    note_parts = ["status=%s" % (status or "unknown")]
    if output_ref:
        note_parts.append("output retrieved")
    if artifact_ref:
        note_parts.append("artifacts retrieved")
    if isinstance(process.get("exit_code"), int):
        note_parts.append("exit=%s" % process["exit_code"])

    if status in ("success", "partial"):
        collection_report["successful_items"].append(
            {
                "item": "remote-executor/%s" % script_id,
                "source": selected_ip or "remote executor",
                "note": ", ".join(note_parts),
            }
        )
    else:
        collection_report["failed_items"].append(
            {
                "item": "remote-executor/%s" % script_id,
                "reason": str(error.get("message") or "remote executor did not complete successfully"),
                "impact": "script execution evidence may be missing or incomplete",
            }
        )

    if status in ("partial", "blocked", "failed"):
        collection_report["evidence_gaps"].append(
            {
                "gap": "remote executor status %s for %s" % (status or "unknown", script_id),
                "related_stage": "signal_collection",
                "why_important": "missing or partial execution may hide expected script evidence",
            }
        )
    for warning in warnings:
        collection_report["evidence_gaps"].append(
            {
                "gap": "remote executor warning for %s: %s" % (script_id, warning),
                "related_stage": "signal_collection",
                "why_important": "execution warnings may indicate incomplete artifact retrieval",
            }
        )


def build_input_from_remote_run(remote_run_dir: Path, args: argparse.Namespace) -> Dict[str, Any]:
    context = first_context(remote_run_dir)
    run_result = load_remote_executor_run_result(remote_run_dir)
    incident_input = getattr(args, "incident_input", {}) or {}
    incident_id = str(
        incident_input.get("incident_id")
        or getattr(args, "incident_id_override", "")
        or context.get("incident_id")
        or run_result.get("incident_id")
        or remote_run_dir.name
    )
    return {
        "incident_id": incident_id,
        "middleware": str(incident_input.get("middleware") or context.get("middleware") or "mongodb"),
        "scenario": args.scenario or str(context.get("scenario") or "unknown"),
        "namespace": str(context.get("namespace") or run_result.get("namespace") or ""),
        "cluster_id": str(incident_input.get("cluster_id") or context.get("cluster_id") or run_result.get("cluster_id") or ""),
        "customer_clue": args.customer_clue or str(incident_input.get("customer_clue") or context.get("customer_clue") or "remote run script outputs"),
        "input_source": "incident-dir" if incident_input else "remote-run-dir",
        "remote_run_dir": str(remote_run_dir),
        "received_at": now_iso(),
    }


def build_incident_from_remote_run(remote_run_dir: Path, output_dir: Path, args: argparse.Namespace, preserve_existing_input: bool = False) -> None:
    if not remote_run_dir.exists():
        raise FileNotFoundError("remote run dir does not exist: %s" % remote_run_dir)
    context = first_context(remote_run_dir)
    run_result = load_remote_executor_run_result(remote_run_dir)
    input_file = output_dir / "input.yaml"
    if preserve_existing_input and input_file.exists():
        input_data = load_yaml(input_file)
    else:
        input_data = build_input_from_remote_run(remote_run_dir, args)
    generated_at = now_iso()
    structured_record: Dict[str, Any] = {
        "summary": {
            "middleware": input_data["middleware"],
            "topology_type": str(context.get("topology_type") or ""),
            "deployment_architecture": str(context.get("deployment_architecture") or ""),
            "namespace": input_data["namespace"],
            "cluster_id": input_data["cluster_id"],
        },
        "details": {},
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    signal_bundle: Dict[str, Any] = {
        "incident_id": input_data["incident_id"],
        "middleware": input_data["middleware"],
        "signal_overview": {"status": "unknown", "abnormal_signal_count": 0},
        "abnormal_signals": [],
        "object_signal_links": [],
        "timeline_summary": [],
        "processed_log_highlights": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    collection_report: Dict[str, Any] = {
        "collection_actions": [],
        "successful_items": [],
        "failed_items": [],
        "blank_items": [],
        "evidence_gaps": [],
        "generated_at": generated_at,
        "updated_at": generated_at,
    }
    copy_remote_run_support_files(remote_run_dir, output_dir)

    script_outputs_dir = output_dir / "script_outputs"
    if script_outputs_dir.exists():
        shutil.rmtree(script_outputs_dir)
    item_dirs = script_run_dirs(remote_run_dir)
    for item_dir in item_dirs:
        executor_result = load_yaml(item_dir / "remote-executor-result.yaml") if (item_dir / "remote-executor-result.yaml").exists() else {}
        output = load_yaml(item_dir / "output.yaml") if (item_dir / "output.yaml").exists() else {}
        script_id = str(
            output.get("script_id")
            or executor_result.get("script_id")
            or item_dir.name
        )
        if executor_result:
            merge_remote_executor_result(collection_report, script_id, executor_result)
        if output:
            apply_script_output(structured_record, signal_bundle, collection_report, output)

        target_dir = script_outputs_dir / script_id
        target_dir.mkdir(parents=True, exist_ok=True)
        for filename in (
            "output.yaml",
            "context.yaml",
            "remote-executor-request.yaml",
            "remote-executor-result.yaml",
            "remote.stdout.txt",
            "remote.stderr.txt",
            "exit_code.txt",
            "artifact_retrieval_error.txt",
        ):
            if (item_dir / filename).exists():
                shutil.copy2(item_dir / filename, target_dir / filename)
        if (item_dir / "artifacts").exists():
            shutil.copytree(item_dir / "artifacts", target_dir / "artifacts", dirs_exist_ok=True)
    merge_remote_executor_run_result(collection_report, run_result, bool(item_dirs))

    if not preserve_existing_input or not input_file.exists():
        write_yaml(input_file, input_data)
    write_yaml(output_dir / "structured_record.yaml", structured_record)
    write_yaml(output_dir / "signal_bundle.yaml", signal_bundle)
    write_yaml(output_dir / "collection_report.yaml", collection_report)


def run_remote_smoke(args: argparse.Namespace, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "tools" / "remote-executor" / "mongodb-executor.py"),
        "--config",
        str(resolve_path(args.remote_config)),
        "--output-dir",
        str(resolve_path(args.remote_output_dir)),
    ]
    if getattr(args, "object_inventory", ""):
        command.extend(["--inventory-file", str(resolve_path(args.object_inventory))])
    if args.remote_namespace:
        command.extend(["--namespace", args.remote_namespace])
    try:
        proc = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=900,
        )
        stdout = proc.stdout
        stderr = proc.stderr
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = ((exc.stderr or "") + "\nremote executor timed out after 900s").strip()
        returncode = 124
    (output_dir / "remote-executor.stdout.txt").write_text(stdout, encoding="utf-8")
    (output_dir / "remote-executor.stderr.txt").write_text(stderr, encoding="utf-8")
    local_dir = None
    for line in stdout.splitlines():
        if line.startswith("local_dir="):
            local_dir = resolve_path(line.split("=", 1)[1].strip())
            break
    if returncode != 0:
        if local_dir is not None and local_dir.exists():
            return local_dir
        raise RuntimeError("remote executor failed: %s" % stderr.strip())
    if local_dir is not None:
        return local_dir
    raise RuntimeError("remote executor output did not include local_dir")


def as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def write_report(output_dir: Path, input_data: Dict[str, Any], analysis: Dict[str, Any]) -> Path:
    conclusion = analysis.get("conclusion_summary") or {}
    report_file = output_dir / "report.md"
    lines = [
        "# Midstack Triage Report",
        "",
        "## Incident",
        "",
        "- Incident ID: `%s`" % input_data.get("incident_id", output_dir.name),
        "- Middleware: `%s`" % input_data.get("middleware", "mongodb"),
        "- Namespace: `%s`" % input_data.get("namespace", ""),
        "- Cluster: `%s`" % input_data.get("cluster_id", ""),
        "- Customer clue: %s" % input_data.get("customer_clue", ""),
        "",
        "## Conclusion",
        "",
        "- Statement: %s" % conclusion.get("statement", ""),
        "- Confidence: `%s`" % conclusion.get("confidence", ""),
        "- Primary cause category: `%s`" % conclusion.get("primary_cause_category", ""),
        "- Impact scope: %s" % conclusion.get("impact_scope", ""),
        "",
        "## Evidence",
        "",
    ]
    evidence = as_list(conclusion.get("evidence"))
    lines.extend(["- %s" % item for item in evidence] if evidence else ["- No explicit evidence recorded."])
    lines.extend(["", "## Hypotheses", ""])
    for item in as_list(analysis.get("hypotheses")):
        if not isinstance(item, dict):
            continue
        lines.append("- `%s` %s: %s" % (item.get("status", ""), item.get("hypothesis_id", ""), item.get("statement", "")))
    lines.extend(["", "## Evidence Gaps", ""])
    gaps = as_list(conclusion.get("limitations"))
    lines.extend(["- %s" % item for item in gaps] if gaps else ["- No explicit evidence gaps recorded."])
    lines.extend(["", "## Next Read-Only Actions", ""])
    actions = as_list(analysis.get("next_actions"))
    lines.extend(["- %s" % ((item or {}).get("action") if isinstance(item, dict) else item) for item in actions] if actions else ["- No next actions recorded."])
    lines.extend(["", "## Knowledge Candidates", ""])
    candidates = as_list(analysis.get("knowledge_candidates"))
    if candidates:
        for item in candidates:
            if isinstance(item, dict):
                lines.append("- `%s` %s: `%s`" % (item.get("candidate_type", ""), item.get("title", ""), item.get("asset_path", "")))
    else:
        lines.append("- No knowledge candidates recorded.")
    lines.append("")
    report_file.write_text("\n".join(lines), encoding="utf-8")
    return report_file


def command_analyse(args: argparse.Namespace) -> int:
    output_root = path_from_arg(args.output_root)
    incident_dir = None
    incident_mode = False
    previous_incident_status = ""
    remote_run_result: Dict[str, Any] = {}
    if not (args.incident_dir or args.remote_config or args.remote_run_dir or args.input_dir):
        try:
            args.incident_dir = str(read_current_incident(output_root))
        except (FileNotFoundError, ValueError) as exc:
            return write_blocked_output(
                "analyse",
                "none",
                "mongodb",
                output_root,
                "current incident is not available",
                [
                    {
                        "code": "missing_current_incident",
                        "message": str(exc),
                        "required_user_action": "run /midstack:start first or provide an explicit incident directory",
                    }
                ],
                ["run /midstack:start with remote access information"],
            )
    if args.incident_dir:
        incident_mode = True
        incident_dir = resolve_path(args.incident_dir)
        if not incident_dir.exists():
            return write_blocked_output(
                "analyse",
                incident_dir.name,
                "mongodb",
                incident_dir.parent,
                "incident directory does not exist",
                [
                    {
                        "code": "incident_dir_not_found",
                        "message": "incident dir does not exist: %s" % incident_dir,
                        "required_user_action": "provide an existing incident directory or run /midstack:start again",
                    }
                ],
                ["provide an existing incident directory"],
            )
        output_dir = resolve_path(args.output_dir) if args.output_dir else incident_dir
        meta = load_incident_meta(incident_dir)
        status = str(meta.get("status") or "")
        previous_incident_status = status
        if status not in ANALYSABLE_STATUSES:
            incident_id = str(meta.get("incident_id") or incident_dir.name)
            middleware = str(meta.get("middleware") or "mongodb")
            message = "incident status must be ready or analysed before analyse; current status is %s" % (status or "missing")
            return write_blocked_output(
                "analyse",
                incident_id,
                middleware,
                incident_dir,
                "incident is not ready for analyse",
                [
                    {
                        "code": "incident_status_not_ready",
                        "message": message,
                        "required_user_action": "finish /midstack:start successfully or choose another incident",
                    }
                ],
                ["fix the blocked start conditions or choose a ready incident"],
            )
        input_data = load_yaml(incident_dir / "input.yaml")
        args.incident_input = input_data
        args.incident_id_override = str(input_data.get("incident_id") or incident_dir.name)
        args.remote_config = str(incident_dir / "remote-config.yaml")
        object_inventory_file = incident_dir / "object-inventory.yaml"
        if object_inventory_file.exists():
            args.object_inventory = str(object_inventory_file)
        args.remote_namespace = args.remote_namespace or str(input_data.get("namespace") or "")
        args.customer_clue = args.customer_clue or str(input_data.get("customer_clue") or "")
        args.scenario = args.scenario or str(input_data.get("scenario") or "unknown")
        if not Path(args.remote_config).exists():
            return write_blocked_output(
                "analyse",
                str(input_data.get("incident_id") or incident_dir.name),
                str(input_data.get("middleware") or "mongodb"),
                incident_dir,
                "incident remote config is missing",
                [
                    {
                        "code": "missing_remote_config",
                        "message": "missing incident remote-config.yaml: %s" % args.remote_config,
                        "required_user_action": "rerun /midstack:start with remote access information",
                    }
                ],
                ["rerun /midstack:start with remote access information"],
            )
    else:
        if not args.output_dir:
            print("ERROR: --output-dir is required unless --incident-dir is used", file=sys.stderr)
            return 1
        output_dir = resolve_path(args.output_dir)
    try:
        if incident_mode and incident_dir is not None:
            update_incident_meta(incident_dir, {"status": "analysing", "current_command": "analyse"})
        if args.remote_config:
            remote_run_dir = run_remote_smoke(args, output_dir)
            remote_run_result = load_remote_executor_run_result(remote_run_dir)
            build_incident_from_remote_run(remote_run_dir, output_dir, args, preserve_existing_input=incident_mode)
        elif args.remote_run_dir:
            remote_run_dir = resolve_path(args.remote_run_dir)
            remote_run_result = load_remote_executor_run_result(remote_run_dir)
            build_incident_from_remote_run(remote_run_dir, output_dir, args)
        else:
            input_dir = resolve_path(args.input_dir)
            for filename in ("input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml", "expected_analysis.yaml"):
                copy_if_exists(input_dir, output_dir, filename)
    except Exception as exc:
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output_dir.mkdir(parents=True, exist_ok=True)
        incident_id = output_dir.name
        output = adapter_output("analyse", incident_id, "mongodb", "failed", "local analyse failed", output_dir)
        output["warnings"].append(str(exc))
        write_yaml(output_dir / "adapter-output.yaml", output)
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    input_data = load_yaml(output_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or output_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    if remote_run_result:
        run_status = str(remote_run_result.get("status") or "")
        run_error = remote_run_result.get("error") or {}
        error_code = str(run_error.get("code") or "")
        error_message = str(run_error.get("message") or "remote executor did not complete successfully")
        if run_status == "blocked":
            if incident_mode and incident_dir is not None and previous_incident_status:
                update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
            output = adapter_output("analyse", incident_id, middleware, "blocked", "remote signal collection is blocked", output_dir)
            output["blocking_items"] = [
                {
                    "code": error_code or "remote_executor_blocked",
                    "message": error_message,
                    "required_user_action": remote_executor_required_user_action(error_code),
                }
            ]
            output["next_actions"] = remote_executor_next_actions(error_code)
            add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
            add_record_ref_if_exists(output, output_dir, "remote_executor_run", "remote-executor-run.yaml", "remote executor batch result")
            write_yaml(output_dir / "adapter-output.yaml", output)
            print(str(output_dir))
            return 0
        if run_status == "failed":
            if incident_mode and incident_dir is not None and previous_incident_status:
                update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
            output = adapter_output("analyse", incident_id, middleware, "failed", "remote signal collection failed", output_dir)
            output["warnings"].append(error_message)
            output["next_actions"] = remote_executor_next_actions(error_code)
            add_record_ref_if_exists(output, output_dir, "collection_report", "collection_report.yaml", "stage-3 collection summary")
            add_record_ref_if_exists(output, output_dir, "remote_executor_run", "remote-executor-run.yaml", "remote executor batch result")
            write_yaml(output_dir / "adapter-output.yaml", output)
            print("ERROR: %s" % error_message, file=sys.stderr)
            return 1
    analysis_file = output_dir / "analysis.yaml"
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "analyse" / "mongodb-analyse.py"),
            "--input-dir",
            str(output_dir),
            "--output-file",
            str(analysis_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    status = "completed" if proc.returncode == 0 else "failed"
    output = adapter_output("analyse", incident_id, middleware, status, "local analyse %s" % status, output_dir)
    output["record_refs"].append({"name": "analysis", "path": str(analysis_file), "description": "generated analysis result"})
    if proc.returncode != 0:
        if incident_mode and incident_dir is not None and previous_incident_status:
            update_incident_meta(incident_dir, {"status": previous_incident_status, "current_command": "analyse"})
        output["warnings"].append(proc.stderr.strip())
    else:
        analysis = load_yaml(analysis_file)
        report_file = write_report(output_dir, input_data, analysis)
        output["record_refs"].append({"name": "report", "path": str(report_file), "description": "generated human-readable report"})
        if incident_mode and incident_dir is not None:
            update_incident_meta(incident_dir, {"status": "analysed", "current_command": "analyse"})
            write_current_incident(output_root, incident_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(analysis_file))
    return proc.returncode


LEVEL_VALUE = {"low": 1, "medium": 2, "high": 3}


def score_item(level: str, reason: str) -> Dict[str, str]:
    return {"level": level, "reason": reason}


def level_from_confidence(confidence: str) -> str:
    return "high" if confidence == "high" else ("medium" if confidence == "medium" else "low")


def overall_level(score: Dict[str, Dict[str, str]]) -> str:
    values = [LEVEL_VALUE.get(item.get("level", "low"), 1) for item in score.values()]
    average = sum(values) / float(len(values) or 1)
    if average >= 2.67:
        return "high"
    if average >= 1.67:
        return "medium"
    return "low"


def review_score_from_analysis(analysis: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    conclusion = analysis.get("conclusion_summary") or {}
    hypotheses = [item for item in analysis.get("hypotheses") or [] if isinstance(item, dict)]
    knowledge_candidates = [item for item in analysis.get("knowledge_candidates") or [] if isinstance(item, dict)]
    conclusion_evidence = conclusion.get("evidence") or []
    supported = [item for item in hypotheses if item.get("status") == "supported" or item.get("validation_result") == "supported"]
    refuted = [item for item in hypotheses if item.get("status") == "refuted" or item.get("validation_result") == "refuted"]
    validation_actions = []
    for item in hypotheses:
        for action in item.get("validation_actions") or []:
            validation_actions.append(action)

    if conclusion_evidence:
        evidence_score = score_item("high", "Conclusion includes explicit evidence.")
    elif supported:
        evidence_score = score_item("medium", "Hypotheses include supported results, but conclusion evidence is thin.")
    else:
        evidence_score = score_item("low", "No explicit conclusion evidence or supported hypothesis found.")

    if len(hypotheses) >= 2 and supported:
        hypothesis_score = score_item("high", "Analysis includes multiple hypotheses and at least one supported path.")
    elif hypotheses:
        hypothesis_score = score_item("medium", "Analysis includes hypotheses, but coverage is limited.")
    else:
        hypothesis_score = score_item("low", "No hypotheses generated.")

    if validation_actions:
        validation_score = score_item("high", "Analysis includes explicit validation actions.")
    elif supported or refuted:
        validation_score = score_item("medium", "Hypotheses have validation results, but no additional validation actions were executed.")
    else:
        validation_score = score_item("low", "No validation actions or decisive validation results.")

    confidence_score = score_item(
        level_from_confidence(str(conclusion.get("confidence") or "low")),
        "Derived from conclusion_summary.confidence.",
    )

    if knowledge_candidates:
        knowledge_score = score_item("high", "Analysis produced reusable knowledge candidates.")
    elif conclusion.get("primary_cause_category") == "baseline":
        knowledge_score = score_item("medium", "Baseline case is reusable for regression, not production knowledge.")
    else:
        knowledge_score = score_item("low", "No knowledge candidates generated.")

    return {
        "evidence_completeness": evidence_score,
        "hypothesis_coverage": hypothesis_score,
        "validation_depth": validation_score,
        "conclusion_confidence": confidence_score,
        "knowledge_reusability": knowledge_score,
    }


def review_suggestions(score: Dict[str, Dict[str, str]], analysis: Dict[str, Any]) -> List[str]:
    conclusion = analysis.get("conclusion_summary") or {}
    is_baseline = conclusion.get("primary_cause_category") == "baseline"
    suggestions: List[str] = []
    if score["evidence_completeness"]["level"] != "high":
        suggestions.append("Add stronger evidence extraction or evidence-to-conclusion linking.")
    if score["hypothesis_coverage"]["level"] != "high" and not is_baseline:
        suggestions.append("Add scenario-specific hypothesis rules or counter-hypotheses.")
    if score["validation_depth"]["level"] != "high":
        suggestions.append("Add explicit validation actions for supported and refuted hypotheses.")
    if score["knowledge_reusability"]["level"] != "high" and not is_baseline:
        suggestions.append("Improve knowledge candidate generation from matching assets and incident evidence.")
    return suggestions


def command_review(args: argparse.Namespace) -> int:
    output_root = path_from_arg(args.output_root)
    if args.incident_dir:
        incident_dir = resolve_path(args.incident_dir)
    else:
        try:
            incident_dir = read_current_incident(output_root)
        except (FileNotFoundError, ValueError) as exc:
            return write_blocked_output(
                "review",
                "none",
                "mongodb",
                output_root,
                "current incident is not available for review",
                [
                    {
                        "code": "missing_current_incident",
                        "message": str(exc),
                        "required_user_action": "run /midstack:analyse first or provide an explicit incident directory",
                    }
                ],
                ["run /midstack:analyse or provide an incident directory"],
                output_filename="review-adapter-output.yaml",
            )
    meta = load_incident_meta(incident_dir)
    meta_status = str(meta.get("status") or "")
    if meta_status and meta_status not in ("analysed", "reviewed", "closed"):
        return write_blocked_output(
            "review",
            str(meta.get("incident_id") or incident_dir.name),
            str(meta.get("middleware") or "mongodb"),
            incident_dir,
            "incident is not ready for review",
            [
                {
                    "code": "incident_status_not_reviewable",
                    "message": "incident status must be analysed, reviewed, or closed before review; current status is %s" % meta_status,
                    "required_user_action": "run /midstack:analyse successfully before review",
                }
            ],
            ["run /midstack:analyse successfully before review"],
            output_filename="review-adapter-output.yaml",
        )
    analysis_file = incident_dir / "analysis.yaml"
    if not analysis_file.exists():
        print("ERROR: missing analysis.yaml: %s" % analysis_file, file=sys.stderr)
        return 1
    analysis = load_yaml(analysis_file)
    score = review_score_from_analysis(analysis)
    level = overall_level(score)
    analysis["review"] = {
        "score": score,
        "overall": {"level": level, "reason": "Average of local review score dimensions."},
        "improvement_suggestions": review_suggestions(score, analysis),
        "regression_risks": [],
        "generated_at": now_iso(),
    }
    analysis["updated_at"] = now_iso()
    write_yaml(analysis_file, analysis)
    update_incident_meta(incident_dir, {"status": "reviewed", "current_command": "review"})
    input_data = load_yaml(incident_dir / "input.yaml")
    incident_id = str(input_data.get("incident_id") or incident_dir.name)
    middleware = str(input_data.get("middleware") or "mongodb")
    output = adapter_output("review", incident_id, middleware, "completed", "local review completed", incident_dir)
    output["record_refs"].append({"name": "analysis.review", "path": str(analysis_file), "description": "local review result in analysis.yaml review block"})
    review_output_file = incident_dir / "review-adapter-output.yaml"
    write_yaml(review_output_file, output)
    print(str(review_output_file))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local midstack-triage plugin command prototype.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--middleware", required=True)
    start.add_argument("--customer-clue", default="")
    start.add_argument("--namespace", default="")
    start.add_argument("--cluster-id", default="")
    start.add_argument("--incident-id")
    start.add_argument("--output-root", default=".local/incidents")
    start.add_argument("--environment-ip", action="append", default=[], help="Remote environment IP. May be repeated; the first IP is used as jump host.")
    start.add_argument("--username", default="")
    start.add_argument("--password", default="")
    start.add_argument("--port", type=int, default=22)
    start.set_defaults(func=command_start)

    analyse = subparsers.add_parser("analyse")
    input_source = analyse.add_mutually_exclusive_group(required=False)
    input_source.add_argument("--input-dir")
    input_source.add_argument("--remote-run-dir")
    input_source.add_argument("--remote-config", help="Run MongoDB remote smoke first, then analyse the generated remote run directory.")
    input_source.add_argument("--incident-dir", help="Run analyse from a started incident directory containing remote-config.yaml.")
    analyse.add_argument("--output-dir")
    analyse.add_argument("--output-root", default=".local/incidents")
    analyse.add_argument("--scenario", help="Override or supply scenario when analysing a remote run.")
    analyse.add_argument("--customer-clue", help="Override or supply customer clue when analysing a remote run.")
    analyse.add_argument("--remote-output-dir", default=".local/remote-runs")
    analyse.add_argument("--remote-namespace", default="")
    analyse.add_argument("--object-inventory", default="")
    analyse.set_defaults(func=command_analyse)

    review = subparsers.add_parser("review")
    review.add_argument("--incident-dir")
    review.add_argument("--output-root", default=".local/incidents")
    review.set_defaults(func=command_review)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
