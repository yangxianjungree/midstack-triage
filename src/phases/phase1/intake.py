"""Phase 1 intake classification and follow-up prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from execution.modes import resolve_execution_mode


OFFLINE_REQUIRED_FILES = ["input.yaml", "structured_record.yaml", "signal_bundle.yaml", "collection_report.yaml"]
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
            "readiness": "phase2_gate_required",
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


def _environment_mode_question(local_context: Dict[str, str] | None = None) -> Dict[str, str]:
    question = "当前插件能否通过 SSH 进入目标环境？如果不能，请说明是在故障集群机器上(local)，还是只有日志/截图/命令输出(offline)。"
    if (local_context or {}).get("status") == "available":
        current_context = str((local_context or {}).get("current_context") or "")
        question = "%s 本机检测到可用 kubectl context%s；如果这就是故障集群，请改用 local，否则请补 SSH 信息。" % (
            question,
            " %s" % current_context if current_context else "",
        )
    return _follow_up(
        "environment_mode",
        question,
        "remote, local, or offline",
    )


def _local_execution_mode_question(local_context: Dict[str, str]) -> Dict[str, str]:
    question = "当前插件是否就在故障集群控制面机器上？如果是，先提供已有采集产物走 offline；否则提供 SSH 信息走 remote。"
    if local_context.get("status") == "available":
        current_context = str(local_context.get("current_context") or "")
        question = "%s 本机检测到可用 kubectl context%s，但本地采集 executor 尚未实现。" % (
            question,
            " %s" % current_context if current_context else "",
        )
    elif local_context.get("status") == "unreachable":
        current_context = str(local_context.get("current_context") or "")
        question = "%s 本机 kubectl context%s 当前不可访问，请提供完整离线证据或改走 remote。" % (
            question,
            " %s" % current_context if current_context else "",
        )
    elif local_context.get("status") == "unavailable":
        question = "%s 本机未检测到可用 kubectl，请提供完整离线证据或改走 remote。" % question
    return _follow_up("execution_mode", question, "remote or offline")


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


def _offline_artifact_status(artifact_source: str) -> Dict[str, Any]:
    if not artifact_source:
        return {
            "status": "missing",
            "source": "",
            "required_files": list(OFFLINE_REQUIRED_FILES),
            "missing_files": list(OFFLINE_REQUIRED_FILES),
        }
    path = Path(artifact_source).expanduser()
    if not path.exists() or not path.is_dir():
        return {
            "status": "not_found",
            "source": str(path),
            "required_files": list(OFFLINE_REQUIRED_FILES),
            "missing_files": list(OFFLINE_REQUIRED_FILES),
        }
    missing_files = [filename for filename in OFFLINE_REQUIRED_FILES if not (path / filename).exists()]
    return {
        "status": "ready" if not missing_files else "incomplete",
        "source": str(path),
        "required_files": list(OFFLINE_REQUIRED_FILES),
        "missing_files": missing_files,
    }


def _remote_required_items(args: Any, primary_ip: str, local_context: Dict[str, str]) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    blocking_items: List[Dict[str, str]] = []
    follow_up_questions: List[Dict[str, str]] = []
    if not primary_ip:
        follow_up_questions.append(_environment_mode_question(local_context))
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
    pasted_evidence = str(getattr(args, "pasted_evidence", "") or "")
    manual_evidence_ref = str(getattr(args, "manual_evidence_ref", "") or "")
    local_context = getattr(args, "local_context", None) or {
        "status": "not_checked",
        "reason": "",
        "current_context": "",
    }
    blocking_items: List[Dict[str, str]] = []
    follow_up_questions: List[Dict[str, str]] = []
    manual_evidence: Dict[str, str] = {
        "status": "missing",
        "kind": "",
    }
    offline_artifact: Dict[str, Any] = {
        "status": "unconfigured",
        "source": "",
        "required_files": list(OFFLINE_REQUIRED_FILES),
        "missing_files": list(OFFLINE_REQUIRED_FILES),
    }

    if not middleware:
        blocking_items.append(_blocking_item("missing_middleware", "middleware is required", "provide middleware, for example mongodb", "middleware"))
        follow_up_questions.append(_follow_up("middleware", "要排查的中间件是什么？", "middleware name, for example mongodb"))
    if pasted_evidence or manual_evidence_ref:
        manual_evidence = {
            "status": "captured",
            "kind": "pasted_text",
        }
        if manual_evidence_ref:
            manual_evidence["ref"] = manual_evidence_ref

    if mode.name == "remote":
        remote_blocks, remote_questions = _remote_required_items(args, primary_ip, local_context)
        blocking_items.extend(remote_blocks)
        follow_up_questions.extend(remote_questions)
    elif mode.name == "local":
        pass
    elif mode.name == "offline":
        artifact_source = str(getattr(args, "artifact_source", "") or "")
        offline_artifact = _offline_artifact_status(artifact_source)
        if offline_artifact["status"] == "missing":
            blocking_items.append(
                _blocking_item(
                    "offline_start_needs_artifacts",
                    "offline start mode needs existing evidence artifacts",
                    "run start again with --artifact-source pointing to an incident, fixture, or remote-run artifact directory",
                    "artifact_source",
                )
            )
            follow_up_questions.append(_offline_follow_up_question(intake_scenario))
        elif offline_artifact["status"] == "not_found":
            blocking_items.append(
                _blocking_item(
                    "offline_artifact_source_not_found",
                    "offline artifact source directory does not exist",
                    "provide an existing local artifact directory",
                    "artifact_source",
                )
            )
            follow_up_questions.append(_offline_follow_up_question(intake_scenario))
        elif offline_artifact["status"] == "incomplete":
            blocking_items.append(
                _blocking_item(
                    "offline_artifacts_incomplete",
                    "offline artifact source is missing required files: %s" % ", ".join(offline_artifact["missing_files"]),
                    "provide a complete offline artifact directory or run analyse with an explicit input source",
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
        "offline_artifact": offline_artifact,
        "manual_evidence": manual_evidence,
        "local_context": local_context,
        "blocking_items": blocking_items,
        "follow_up_questions": follow_up_questions,
    }
