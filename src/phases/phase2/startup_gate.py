"""Phase 2 startup readiness gate."""

from __future__ import annotations

from typing import Any, Dict


def _follow_up(field: str, question: str, expected_answer: str) -> Dict[str, str]:
    return {
        "field": field,
        "question": question,
        "expected_answer": expected_answer,
    }


def _remote_access_follow_up() -> Dict[str, str]:
    return _follow_up(
        "remote_access",
        "远程接入或 kubectl 校验失败。请确认环境 IP、端口、用户名、密码，以及远端 kubectl 是否能访问目标集群。",
        "corrected remote access fields or confirmation that kubectl works on the remote host",
    )


def _namespace_ambiguous_follow_up(candidate_namespaces: Any) -> Dict[str, str]:
    candidates = ", ".join(str(item) for item in (candidate_namespaces or []))
    question = "检测到多个 MongoDB namespace，请指定要排查的 namespace。"
    if candidates:
        question = "%s候选：%s" % (question, candidates)
    return _follow_up("namespace", question, "one namespace from the candidate list")


def _namespace_not_found_follow_up() -> Dict[str, str]:
    return _follow_up(
        "namespace",
        "未能自动发现 MongoDB 对象。请提供目标 namespace，或确认 middleware 和远程集群是否正确。",
        "target namespace or corrected middleware/remote cluster information",
    )


def _access_from_args(args: Any) -> Dict[str, Any]:
    env_ips = [item for item in (getattr(args, "environment_ip", []) or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    return {
        "candidate_ips": env_ips,
        "primary_ip": primary_ip,
        "username": getattr(args, "username", ""),
        "password": getattr(args, "password", ""),
        "port": getattr(args, "port", 22),
    }


def evaluate_startup_readiness(
    args: Any,
    intake: Dict[str, Any],
    *,
    validate_remote_environment,
    discover_mongodb_inventory,
    probe_local_context,
) -> Dict[str, Any]:
    blocking_items = list(intake.get("blocking_items") or [])
    follow_up_questions = list(intake.get("follow_up_questions") or [])
    remote_validation: Dict[str, Any] = {"status": "skipped", "checks": []}
    object_inventory: Dict[str, Any] = {"status": "skipped", "middleware": getattr(args, "middleware", "")}
    local_context = intake.get("local_context") or {
        "status": "not_checked",
        "reason": "",
        "current_context": "",
    }
    if intake.get("environment_mode") == "local":
        local_context = probe_local_context()

    if intake.get("status") == "ready_for_validation" and intake.get("environment_mode") == "remote":
        access = _access_from_args(args)
        remote_validation = validate_remote_environment(access)
        if remote_validation["status"] != "passed":
            blocking_items.append(
                {
                    "code": "remote_environment_validation_failed",
                    "message": "remote SSH or kubectl validation failed",
                    "required_user_action": "fix remote access, install sshpass locally, or ensure kubectl can access the cluster on the jump host",
                }
            )
            follow_up_questions.append(_remote_access_follow_up())
        elif getattr(args, "middleware", "") == "mongodb":
            object_inventory = discover_mongodb_inventory(access, getattr(args, "namespace", ""))
            if not getattr(args, "namespace", "") and object_inventory["status"] == "passed":
                args.namespace = str(object_inventory.get("selected_namespace") or "")
            elif not getattr(args, "namespace", "") and object_inventory["status"] == "ambiguous":
                candidate_namespaces = object_inventory.get("candidate_namespaces") or []
                blocking_items.append(
                    {
                        "code": "multiple_mongodb_namespaces_detected",
                        "message": "multiple MongoDB candidate namespaces were detected",
                        "required_user_action": "provide namespace explicitly",
                        "candidate_namespaces": candidate_namespaces,
                    }
                )
                follow_up_questions.append(_namespace_ambiguous_follow_up(candidate_namespaces))
            elif not getattr(args, "namespace", "") and object_inventory["status"] == "not_found":
                blocking_items.append(
                    {
                        "code": "mongodb_namespace_not_detected",
                        "message": "MongoDB namespace could not be auto-detected from pods, statefulsets, or services",
                        "required_user_action": "provide namespace explicitly",
                    }
                )
                follow_up_questions.append(_namespace_not_found_follow_up())

    status = "ready" if intake.get("status") == "ready_for_validation" and not blocking_items else "blocked"
    return {
        "status": status,
        "blocking_items": blocking_items,
        "follow_up_questions": follow_up_questions,
        "remote_validation": remote_validation,
        "object_inventory": object_inventory,
        "local_context": local_context,
    }
