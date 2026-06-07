#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("MIDSTACK_TRIAGE_WORKSPACE", str(ROOT))).resolve()


TOOLS = [
    {
        "name": "midstack_validate",
        "description": "Run the Midstack Triage local validation suite.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skip_replay": {"type": "boolean", "default": False},
                "skip_score": {"type": "boolean", "default": False},
                "score_min_level": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
            },
        },
    },
    {
        "name": "midstack_start",
        "description": "Create a local Midstack Triage incident record.",
        "inputSchema": {
            "type": "object",
            "required": ["middleware", "customer_clue"],
            "properties": {
                "middleware": {"type": "string", "default": "mongodb"},
                "customer_clue": {"type": "string"},
                "namespace": {"type": "string", "default": ""},
                "cluster_id": {"type": "string", "default": ""},
                "incident_id": {"type": "string", "default": ""},
                "output_root": {"type": "string", "default": ".local/incidents"},
            },
        },
    },
    {
        "name": "midstack_analyse_fixture",
        "description": "Run local analyse from a replay fixture or existing incident-like input directory.",
        "inputSchema": {
            "type": "object",
            "required": ["input_dir", "output_dir"],
            "properties": {
                "input_dir": {"type": "string"},
                "output_dir": {"type": "string"},
            },
        },
    },
    {
        "name": "midstack_analyse_remote_run",
        "description": "Run local analyse from an already completed MongoDB remote smoke result directory.",
        "inputSchema": {
            "type": "object",
            "required": ["remote_run_dir", "output_dir"],
            "properties": {
                "remote_run_dir": {"type": "string"},
                "output_dir": {"type": "string"},
                "scenario": {"type": "string", "default": "baseline"},
                "customer_clue": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "midstack_analyse_remote_config",
        "description": "Run MongoDB remote smoke through a local ignored environment config, then analyse the generated result.",
        "inputSchema": {
            "type": "object",
            "required": ["remote_config", "output_dir"],
            "properties": {
                "remote_config": {"type": "string"},
                "output_dir": {"type": "string"},
                "scenario": {"type": "string", "default": "baseline"},
                "customer_clue": {"type": "string", "default": ""},
                "remote_namespace": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "midstack_review",
        "description": "Generate local review scores from a completed Midstack Triage incident directory.",
        "inputSchema": {
            "type": "object",
            "required": ["incident_dir"],
            "properties": {
                "incident_dir": {"type": "string"},
            },
        },
    },
]


def read_message() -> Optional[Dict[str, Any]]:
    headers: Dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if line == b"":
            return None
        if line in (b"\r\n", b"\n"):
            break
        text = line.decode("ascii").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    payload = sys.stdin.buffer.read(length)
    return json.loads(payload.decode("utf-8"))


def write_message(payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    sys.stdout.buffer.flush()


def run_command(command: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    text = proc.stdout.strip()
    if proc.stderr.strip():
        text = (text + "\n" if text else "") + proc.stderr.strip()
    return {
        "content": [{"type": "text", "text": text or "(no output)"}],
        "isError": proc.returncode != 0,
    }


def resolve_output_path(value: str) -> str:
    path = Path(value)
    return str(path if path.is_absolute() else WORKSPACE_ROOT / path)


def resolve_input_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path)
    workspace_path = WORKSPACE_ROOT / path
    if workspace_path.exists():
        return str(workspace_path)
    return str(ROOT / path)


def tool_call(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "midstack_validate":
        command = [sys.executable, "tools/validators/validate-repo.py", "--score-min-level", str(arguments.get("score_min_level") or "medium")]
        if arguments.get("skip_replay"):
            command.append("--skip-replay")
        if arguments.get("skip_score"):
            command.append("--skip-score")
        return run_command(command)

    if name == "midstack_start":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "start",
            "--middleware",
            str(arguments.get("middleware") or "mongodb"),
            "--customer-clue",
            str(arguments.get("customer_clue") or ""),
            "--namespace",
            str(arguments.get("namespace") or ""),
            "--cluster-id",
            str(arguments.get("cluster_id") or ""),
            "--output-root",
            resolve_output_path(str(arguments.get("output_root") or ".local/incidents")),
        ]
        if arguments.get("incident_id"):
            command.extend(["--incident-id", str(arguments["incident_id"])])
        return run_command(command)

    if name == "midstack_analyse_fixture":
        return run_command(
            [
                sys.executable,
                "tools/plugin/midstack-local.py",
                "analyse",
                "--input-dir",
                resolve_input_path(str(arguments.get("input_dir") or "")),
                "--output-dir",
                resolve_output_path(str(arguments.get("output_dir") or "")),
            ]
        )

    if name == "midstack_analyse_remote_run":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "analyse",
            "--remote-run-dir",
            resolve_input_path(str(arguments.get("remote_run_dir") or "")),
            "--output-dir",
            resolve_output_path(str(arguments.get("output_dir") or "")),
            "--scenario",
            str(arguments.get("scenario") or "baseline"),
        ]
        if arguments.get("customer_clue"):
            command.extend(["--customer-clue", str(arguments["customer_clue"])])
        return run_command(command)

    if name == "midstack_analyse_remote_config":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "analyse",
            "--remote-config",
            resolve_input_path(str(arguments.get("remote_config") or "")),
            "--output-dir",
            resolve_output_path(str(arguments.get("output_dir") or "")),
            "--scenario",
            str(arguments.get("scenario") or "baseline"),
        ]
        if arguments.get("customer_clue"):
            command.extend(["--customer-clue", str(arguments["customer_clue"])])
        if arguments.get("remote_namespace"):
            command.extend(["--remote-namespace", str(arguments["remote_namespace"])])
        return run_command(command)

    if name == "midstack_review":
        return run_command(
            [
                sys.executable,
                "tools/plugin/midstack-local.py",
                "review",
                "--incident-dir",
                resolve_input_path(str(arguments.get("incident_dir") or "")),
            ]
        )

    return {
        "content": [{"type": "text", "text": "unknown tool: %s" % name}],
        "isError": True,
    }


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "midstack-triage-cursor", "version": "0.1.0"},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        result = tool_call(str(params.get("name") or ""), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": message_id, "result": result}
    if method and method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": -32601, "message": "method not found: %s" % method},
    }


def main() -> int:
    while True:
        message = read_message()
        if message is None:
            return 0
        response = handle(message)
        if response is not None:
            write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())
