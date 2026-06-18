"""Start command runtime."""

from __future__ import annotations

import secrets
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

from phases.phase1.intake import build_start_intake
from shared.workspace import adapter_output, load_yaml, now_iso, path_from_arg, write_current_incident, write_yaml


INCIDENT_ID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def rand4() -> str:
    return "".join(secrets.choice(INCIDENT_ID_ALPHABET) for _ in range(4))


def generated_incident_id(middleware: str) -> str:
    prefix = middleware or "incident"
    return "%s-%s-%s" % (prefix, datetime.now().strftime("%Y%m%d-%H%M%S"), rand4())


def unique_incident_id(middleware: str, output_root) -> str:
    for _ in range(20):
        incident_id = generated_incident_id(middleware)
        if not (output_root / incident_id).exists():
            return incident_id
    return generated_incident_id(middleware)


def _load_prior_start_values(output_dir: Path) -> Dict[str, Any]:
    values: Dict[str, Any] = {}
    input_file = output_dir / "input.yaml"
    if input_file.exists():
        input_data = load_yaml(input_file)
        values.update(
            {
                "middleware": input_data.get("middleware") or "",
                "customer_clue": input_data.get("customer_clue") or "",
                "namespace": input_data.get("namespace") or "",
                "cluster_id": input_data.get("cluster_id") or "",
                "environment_mode": input_data.get("environment_mode") or "",
                "environment_ip": input_data.get("environment_ips") or [],
                "port": input_data.get("remote_port") or None,
                "artifact_source": input_data.get("artifact_source") or "",
            }
        )
    remote_config_file = output_dir / "remote-config.yaml"
    if remote_config_file.exists():
        access = load_yaml(remote_config_file).get("access") or {}
        values.update(
            {
                "environment_ip": access.get("candidate_ips") or values.get("environment_ip") or [],
                "username": access.get("username") or "",
                "password": access.get("password") or "",
                "port": access.get("port") or values.get("port") or None,
            }
        )
    return values


def _merge_start_args(args: Any, prior_values: Dict[str, Any]) -> Any:
    merged = vars(args).copy()
    for field in ("middleware", "customer_clue", "namespace", "cluster_id", "environment_mode", "username", "password", "artifact_source"):
        if not merged.get(field) and prior_values.get(field):
            merged[field] = prior_values[field]
    if not merged.get("environment_ip") and prior_values.get("environment_ip"):
        merged["environment_ip"] = prior_values["environment_ip"]
    if merged.get("port") in (None, ""):
        merged["port"] = prior_values.get("port") or 22
    return SimpleNamespace(**merged)


def run(args, *, validate_remote_environment, discover_mongodb_inventory) -> int:
    if not hasattr(args, "middleware"):
        args.middleware = ""
    if not hasattr(args, "environment_mode"):
        args.environment_mode = ""
    if not hasattr(args, "port"):
        args.port = None
    if not hasattr(args, "artifact_source"):
        args.artifact_source = ""
    output_root = path_from_arg(args.output_root)
    prior_values: Dict[str, Any] = {}
    if args.incident_id:
        prior_values = _load_prior_start_values(output_root / args.incident_id)
        if prior_values:
            args = _merge_start_args(args, prior_values)
    if getattr(args, "port", None) is None:
        args.port = 22
    incident_id = args.incident_id or unique_incident_id(args.middleware, output_root)
    env_ips = [item for item in (args.environment_ip or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    output_dir = output_root / incident_id
    created_at = now_iso()
    prior_meta = load_yaml(output_dir / "meta.yaml") if (output_dir / "meta.yaml").exists() else {}
    original_created_at = prior_meta.get("created_at") or created_at

    intake = build_start_intake(args)
    blocking_items = list(intake["blocking_items"])
    follow_up_questions = list(intake["follow_up_questions"])

    remote_validation: Dict[str, Any] = {"status": "skipped", "checks": []}
    object_inventory: Dict[str, Any] = {"status": "skipped", "middleware": args.middleware}
    access = {
        "candidate_ips": env_ips,
        "primary_ip": primary_ip,
        "username": args.username,
        "password": args.password,
        "port": args.port,
    }
    if intake["status"] == "ready_for_validation" and intake["environment_mode"] == "remote":
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
    write_yaml(output_dir / "phase1-intake.yaml", intake)
    write_yaml(output_dir / "environment-check.yaml", {"remote_validation": remote_validation})
    write_yaml(output_dir / "object-inventory.yaml", object_inventory)
    write_yaml(
        output_dir / "meta.yaml",
        {
            "incident_id": incident_id,
            "middleware": args.middleware,
            "status": status,
            "created_at": original_created_at,
            "updated_at": created_at,
            "plugin_version": "local-cli",
            "current_command": "start",
            "namespace": args.namespace,
            "cluster_id": args.cluster_id,
            "owner": "local",
            "environment_mode": intake["environment_mode"],
            "execution_mode": intake["execution_mode"],
            "remote_validation": remote_validation,
        },
    )
    input_payload = {
        "middleware": args.middleware,
        "incident_id": incident_id,
        "namespace": args.namespace,
        "cluster_id": args.cluster_id,
        "customer_clue": args.customer_clue,
        "input_source": "local-cli",
        "environment_mode": intake["environment_mode"],
        "execution_mode": intake["execution_mode"],
        "environment_ips": env_ips,
        "remote_port": args.port,
        "received_at": created_at,
    }
    if args.artifact_source:
        input_payload["artifact_source"] = args.artifact_source
    write_yaml(output_dir / "input.yaml", input_payload)
    if primary_ip and intake["environment_mode"] == "remote":
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
    elif intake["environment_mode"] == "offline" and args.artifact_source:
        write_yaml(
            output_dir / "offline-config.yaml",
            {
                "name": "%s-offline" % incident_id,
                "purpose": "offline incident evidence source",
                "created_at": created_at,
                "artifact_source": args.artifact_source,
                "offline_artifact": intake.get("offline_artifact") or {},
            },
        )
    output = adapter_output("start", incident_id, args.middleware, status, "local incident %s is %s" % (incident_id, status), output_dir)
    if status == "ready":
        if intake["environment_mode"] == "offline":
            output["summary"] = "%s; offline artifact source ready" % output["summary"]
            output["next_actions"] = [
                "run /midstack:analyse --execution-mode offline",
                "or run /midstack:analyse %s --execution-mode offline" % incident_id,
            ]
            output["user_message"] = "%s; next run /midstack:analyse --execution-mode offline" % output["summary"]
        elif object_inventory.get("namespace_source") == "auto_discovered":
            output["summary"] = "%s; namespace auto-discovered as %s" % (output["summary"], object_inventory.get("selected_namespace"))
            output["next_actions"] = [
                "run /midstack:analyse",
                "or run /midstack:analyse %s" % incident_id,
            ]
            output["user_message"] = "%s; next run /midstack:analyse" % output["summary"]
        else:
            output["next_actions"] = [
                "run /midstack:analyse",
                "or run /midstack:analyse %s" % incident_id,
            ]
            output["user_message"] = "%s; next run /midstack:analyse" % output["summary"]
    else:
        output["blocking_items"] = blocking_items
        output["follow_up_questions"] = follow_up_questions
        output["next_actions"] = [item["question"] for item in follow_up_questions]
        output["warnings"].append("incident is blocked until required input and remote validation pass")
    write_current_incident(output_root, output_dir)
    write_yaml(output_dir / "adapter-output.yaml", output)
    print(str(output_dir))
    return 0
