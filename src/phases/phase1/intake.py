"""Phase 1 intake classification and follow-up prompts."""

from __future__ import annotations

from typing import Any, Dict, List

from execution.modes import resolve_execution_mode


PRODUCTION_HINTS = ("production", "prod", "online", "线上", "生产", "告警", "监控", "sre", "incident", "alert")
DEVELOPMENT_TEST_HINTS = ("dev", "development", "test", "testing", "研发", "测试")
MANUAL_OFFLINE_HINTS = ("todesk", "remote desktop", "远程桌面", "手工", "人工", "粘贴", "截图", "命令输出", "paste", "screenshot", "command output")


def _blocking_item(code: str, message: str, required_user_action: str, field: str) -> Dict[str, str]:
    return {
        "code": code,
        "message": message,
        "required_user_action": required_user_action,
        "field": field,
    }


def _follow_up(field: str, question: str, expected_answer: str) -> Dict[str, str]:
    return {
        "field": field,
        "question": question,
        "expected_answer": expected_answer,
    }


def _has_hint(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _environment_class(customer_clue: str) -> str:
    clue = customer_clue.lower()
    if _has_hint(clue, PRODUCTION_HINTS):
        return "production"
    if _has_hint(clue, DEVELOPMENT_TEST_HINTS):
        return "development_test"
    return "unknown"


def _intake_scenario(mode_name: str, customer_clue: str) -> Dict[str, str]:
    clue = customer_clue.lower()
    environment_class = _environment_class(customer_clue)
    if mode_name == "remote":
        return {
            "id": "remote_ssh",
            "environment_class": environment_class,
            "access_pattern": "ssh_runtime",
            "evidence_source": "live_remote",
            "readiness": "supported",
        }
    if mode_name == "local":
        return {
            "id": "local_fault_cluster",
            "environment_class": environment_class,
            "access_pattern": "local_runtime",
            "evidence_source": "live_local",
            "readiness": "blocked_until_local_executor",
        }
    if _has_hint(clue, MANUAL_OFFLINE_HINTS):
        scenario_id = "manual_guided_offline"
        access_pattern = "operator_paste"
    elif environment_class == "production":
        scenario_id = "offline_production"
        access_pattern = "platform_or_artifacts"
    else:
        scenario_id = "offline_existing_artifacts"
        access_pattern = "artifact_input"
    return {
        "id": scenario_id,
        "environment_class": environment_class,
        "access_pattern": access_pattern,
        "evidence_source": "existing_artifacts",
        "readiness": "blocked_until_artifacts_supplied",
    }


def _environment_mode_question() -> Dict[str, str]:
    return _follow_up(
        "environment_mode",
        "当前插件能否通过 SSH 进入目标环境？如果不能，请说明是在故障集群机器上(local)，还是只有日志/截图/命令输出(offline)。",
        "remote, local, or offline",
    )


def _offline_follow_up_question(intake_scenario: Dict[str, str]) -> Dict[str, str]:
    scenario_id = str(intake_scenario.get("id") or "")
    if scenario_id == "offline_production":
        return _follow_up(
            "incident_reference",
            "你有告警单号、SRE 事件编号、监控链接，或者已有证据目录吗？",
            "incident id, alert id, monitoring link, or artifact path",
        )
    if scenario_id == "manual_guided_offline":
        return _follow_up(
            "manual_input",
            "请贴出命令输出、截图内容，或者给出日志文件路径。",
            "pasted command output, screenshot path, or log file path",
        )
    return _follow_up(
        "artifact_source",
        "你现在已有哪类证据？incident 目录、remote-run、日志文件，还是手工命令输出？",
        "existing artifact path or pasted command output",
    )


def _remote_required_items(args: Any, primary_ip: str) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    blocking_items: List[Dict[str, str]] = []
    follow_up_questions: List[Dict[str, str]] = []
    if not primary_ip:
        follow_up_questions.append(_environment_mode_question())
        blocking_items.append(
            _blocking_item(
                "missing_environment_ip",
                "environment IP is required for remote start",
                "provide at least one remote environment IP",
                "environment_ip",
            )
        )
        follow_up_questions.append(_follow_up("environment_ip", "目标环境或跳板机 IP 是多少？", "one or more IPv4 addresses"))
    if not getattr(args, "username", ""):
        blocking_items.append(_blocking_item("missing_username", "remote username is required", "provide remote username", "username"))
        follow_up_questions.append(_follow_up("username", "远程登录用户名是什么？", "SSH username"))
    if not getattr(args, "password", ""):
        blocking_items.append(_blocking_item("missing_password", "remote password is required", "provide remote password", "password"))
        follow_up_questions.append(_follow_up("password", "远程登录密码是什么？", "SSH password or temporary credential"))
    return blocking_items, follow_up_questions


def build_start_intake(args: Any) -> Dict[str, Any]:
    middleware = str(getattr(args, "middleware", "") or "")
    customer_clue = str(getattr(args, "customer_clue", "") or "")
    mode_name = str(getattr(args, "environment_mode", "") or "remote").strip().lower()
    mode = resolve_execution_mode(mode_name)
    intake_scenario = _intake_scenario(mode.name, customer_clue)
    env_ips = [str(item) for item in (getattr(args, "environment_ip", []) or []) if item]
    primary_ip = env_ips[0] if env_ips else ""
    blocking_items: List[Dict[str, str]] = []
    follow_up_questions: List[Dict[str, str]] = []

    if not middleware:
        blocking_items.append(_blocking_item("missing_middleware", "middleware is required", "provide middleware, for example mongodb", "middleware"))
        follow_up_questions.append(_follow_up("middleware", "要排查的中间件是什么？", "middleware name, for example mongodb"))

    if mode.name == "remote":
        remote_blocks, remote_questions = _remote_required_items(args, primary_ip)
        blocking_items.extend(remote_blocks)
        follow_up_questions.extend(remote_questions)
    elif mode.name == "local":
        blocking_items.append(
            _blocking_item(
                "local_start_not_implemented",
                "local start mode is recognized but local live collection is not implemented",
                "use remote mode with SSH access, or offline mode with existing artifacts",
                "execution_mode",
            )
        )
        follow_up_questions.append(
            _follow_up("execution_mode", "当前插件是否就在故障集群控制面机器上？如果是，先提供已有采集产物走 offline；否则提供 SSH 信息走 remote。", "remote or offline")
        )
    elif mode.name == "offline":
        blocking_items.append(
            _blocking_item(
                "offline_start_needs_artifacts",
                "offline start mode needs existing evidence artifacts",
                "run analyse with --execution-mode offline and provide an incident, fixture, remote-run, logs, or pasted command output",
                "artifact_source",
            )
        )
        follow_up_questions.append(_offline_follow_up_question(intake_scenario))

    status = "ready_for_validation" if not blocking_items else "blocked"
    return {
        "status": status,
        "environment_mode": mode.name,
        "execution_mode": mode.name,
        "intake_scenario": intake_scenario,
        "middleware": middleware,
        "environment_ips": env_ips,
        "primary_ip": primary_ip,
        "requires_remote_access": mode.requires_transport,
        "collects_live_evidence": mode.collects_live_evidence,
        "blocking_items": blocking_items,
        "follow_up_questions": follow_up_questions,
    }
