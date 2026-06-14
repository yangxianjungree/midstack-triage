"""Start command runtime."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any, Dict

from shared.workspace import adapter_output, now_iso, path_from_arg, write_current_incident, write_yaml


INCIDENT_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def rand4() -> str:
    return "".join(secrets.choice(INCIDENT_ID_ALPHABET) for _ in range(4))


def generated_incident_id(middleware: str) -> str:
    return "%s-%s-%s" % (middleware, datetime.now().strftime("%Y%m%d-%H%M%S"), rand4())


def unique_incident_id(middleware: str, output_root) -> str:
    for _ in range(20):
        incident_id = generated_incident_id(middleware)
        if not (output_root / incident_id).exists():
            return incident_id
    return generated_incident_id(middleware)


def run(args, *, validate_remote_environment, discover_mongodb_inventory) -> int:
    output_root = path_from_arg(args.output_root)
    incident_id = args.incident_id or unique_incident_id(args.middleware, output_root)
    env_ips = [item for item in (args.environment_ip or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    output_dir = output_root / incident_id
    created_at = now_iso()

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
            "plugin_version": "local-cli",
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
        if object_inventory.get("namespace_source") == "auto_discovered":
            output["summary"] = "%s; namespace auto-discovered as %s" % (output["summary"], object_inventory.get("selected_namespace"))
        output["next_actions"] = [
            "run /midstack:analyse",
            "or run /midstack:analyse %s" % incident_id,
        ]
        output["user_message"] = "%s; next run /midstack:analyse" % output["summary"]
    else:
        output["blocking_items"] = blocking_items
        output["warnings"].append("incident is blocked until required input and remote validation pass")
    write_current_incident(output_root, output_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(output_dir))
    return 0
