#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = Path(os.environ.get("MIDSTACK_TRIAGE_WORKSPACE", str(ROOT))).resolve()
DEBUG_LOG = os.environ.get("MIDSTACK_TRIAGE_MCP_DEBUG_LOG", "")
IO_MODE = "content-length"


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
            "required": ["middleware"],
            "properties": {
                "middleware": {"type": "string", "default": "mongodb"},
                "customer_clue": {"type": "string"},
                "environment_ips": {"type": "array", "items": {"type": "string"}, "default": []},
                "username": {"type": "string", "default": ""},
                "password": {"type": "string", "default": ""},
                "port": {"type": "integer", "default": 22},
                "namespace": {"type": "string", "default": ""},
                "cluster_id": {"type": "string", "default": ""},
                "incident_id": {"type": "string", "default": ""},
                "output_root": {"type": "string", "default": ".local/incidents"},
            },
        },
    },
    {
        "name": "midstack_analyse_incident",
        "description": "Run MongoDB triage analysis from a started incident directory containing remote-config.yaml.",
        "inputSchema": {
            "type": "object",
            "required": ["incident_dir"],
            "properties": {
                "incident_dir": {"type": "string"},
                "output_dir": {"type": "string", "default": ""},
                "scenario": {"type": "string", "default": "unknown"},
                "customer_clue": {"type": "string", "default": ""},
                "remote_namespace": {"type": "string", "default": ""},
            },
        },
    },
    {
        "name": "midstack_analyse_current",
        "description": "Run MongoDB triage analysis from the latest ready incident created by midstack_start.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output_root": {"type": "string", "default": ".local/incidents"},
                "scenario": {"type": "string", "default": "unknown"},
                "customer_clue": {"type": "string", "default": ""},
                "remote_namespace": {"type": "string", "default": ""},
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
            "properties": {
                "incident_dir": {"type": "string", "default": ""},
                "output_root": {"type": "string", "default": ".local/incidents"},
            },
        },
    },
    {
        "name": "midstack_finalize_analysis",
        "description": "Refresh adapter-output.yaml and meta.yaml after Agent reasoning finalizes analysis.yaml and report.md.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "incident_dir": {"type": "string", "default": ""},
                "output_root": {"type": "string", "default": ".local/incidents"},
            },
        },
    },
]

START_USAGE = """# Midstack Start Usage

When the user runs `/midstack:start ...`, extract fields from the user's natural language and call the `midstack_start` MCP tool directly.

Do not inspect the plugin source tree before calling the tool.
Do not manually invoke `tools/plugin/midstack-local.py` for `/midstack:start`.

Hard boundary: `/midstack:start` only creates or recovers an incident record. It must not run analysis.

Even if the MCP call times out or appears unavailable:

- Do not call `midstack_analyse_current`, `midstack_analyse_incident`, or `midstack_finalize_analysis`.
- Do not read `.cursor/commands/midstack:analyse.md`.
- Do not read, create, or edit `analysis.yaml`, `analysis.rule-draft.yaml`, `agent-reasoning-task.md`, `report.md`, `signal_bundle.yaml`, or `collection_report.yaml`.
- If an incident directory was created, only read `adapter-output.yaml`, `meta.yaml`, `input.yaml`, or `object-inventory.yaml` to report the start status.
- If the start status cannot be recovered, tell the user the start request timed out and ask them to rerun `/midstack:start`; do not continue to analyse automatically.

Field extraction rules:

- `middleware`: use `mongodb` when the user says mongo, mongodb, mongos, mongod, shard, configsvr, or MongoDB.
- `environment_ips`: extract one or more IPv4 addresses; keep the original order and use the first IP as jump host.
- `username` and `password`: extract from forms such as `root/123`, `账号密码是root/123`, or `username/password`.
- `customer_clue`: keep the user's original fault description as the incident clue when present. It is useful but optional.
- `port`: default to `22` unless the user provides another SSH port.
- `namespace`: pass it through if the user provides it; otherwise leave it empty and let `midstack_start` auto-detect a single MongoDB candidate namespace.

After `midstack_start` returns:

- If status is `ready`, tell the user the incident directory and suggest `/midstack:analyse`.
- If status is `blocked`, summarize the blocking items and ask only for the missing or invalid fields. If multiple MongoDB namespaces were detected, ask the user to choose one.
"""

ANALYSE_USAGE = """# Midstack Analyse Usage

When the user runs `/midstack:analyse` after `/midstack:start`, call `midstack_analyse_current`.

Do not manually inspect source files first. The analysis tool will collect remote Kubernetes and MongoDB signals from the current ready incident.

After the analyse tool returns `completed`:

- Open the generated incident directory.
- Read `agent-reasoning-task.md`.
- Treat `analysis.rule-draft.yaml` as a fallback draft, not the final answer.
- Read `input.yaml`, `structured_record.yaml`, `signal_bundle.yaml`, and `collection_report.yaml`.
- Update `analysis.yaml` with Agent-led multi-hypothesis phase-4 reasoning and phase-5 conclusion.
- Classify material evidence gaps as `expected_gap` or `critical_gap`, and keep root-cause confidence capped when a `critical_gap` remains unresolved.
- Distinguish current incident evidence from customer clues, historical cases, runbooks, and experience-based hypothesis sources.
- When evidence only supports phenomenon, impact, or mechanism level, keep the final conclusion at that level and use `deepest_supported_level` when useful.
- Treat DNS lookup errors and shallow bootstrap logs as hypotheses until CoreDNS/DNS probe evidence or MongoDB file-log evidence supports the deeper mechanism.
- Update `report.md` so it matches the final `analysis.yaml`.
- Call `midstack_finalize_analysis` so adapter-output.yaml and meta.yaml reflect the finalized result.

If the analyse tool returns `blocked` or `failed`, summarize the blocking items or warnings instead of inventing a diagnosis.
"""

RESOURCES = [
    {
        "uri": "midstack://commands/start",
        "name": "Midstack Start Command Guide",
        "description": "How Cursor should handle /midstack:start natural-language triage requests.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "midstack://commands/analyse",
        "name": "Midstack Analyse Command Guide",
        "description": "How Cursor should handle /midstack:analyse requests.",
        "mimeType": "text/markdown",
    },
]

RESOURCE_TEXT = {
    "midstack://commands/start": START_USAGE,
    "midstack://commands/analyse": ANALYSE_USAGE,
}

PROMPTS = [
    {
        "name": "midstack_start",
        "description": "Start a Midstack MongoDB incident from a user's natural-language report.",
        "arguments": [
            {
                "name": "user_report",
                "description": "The full user report, including middleware, IPs, credentials, and symptom clue.",
                "required": True,
            }
        ],
    },
    {
        "name": "midstack_analyse_reasoning",
        "description": "Complete Midstack phase-4/5 reasoning from an incident evidence package.",
        "arguments": [
            {
                "name": "incident_dir",
                "description": "The incident directory generated by midstack analyse.",
                "required": True,
            }
        ],
    },
]


def read_message() -> Optional[Dict[str, Any]]:
    global IO_MODE
    headers: Dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if line == b"":
            return None
        stripped = line.strip()
        if stripped.startswith(b"{"):
            IO_MODE = "ndjson"
            return json.loads(stripped.decode("utf-8"))
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
    if IO_MODE == "ndjson":
        sys.stdout.buffer.write(body + b"\n")
    else:
        sys.stdout.buffer.write(b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body)
    sys.stdout.buffer.flush()


def debug_log(message: str) -> None:
    if not DEBUG_LOG:
        return
    path = Path(DEBUG_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def adapter_output_for_stdout(stdout: str) -> str:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not lines:
        return ""
    path = Path(lines[-1])
    if not path.is_absolute():
        path = ROOT / path
    candidates = []
    if path.is_file() and path.name in ("adapter-output.yaml", "review-adapter-output.yaml"):
        candidates.append(path)
    elif path.is_dir():
        candidates.extend([path / "adapter-output.yaml", path / "review-adapter-output.yaml"])
    else:
        candidates.extend([path.parent / "adapter-output.yaml", path.parent / "review-adapter-output.yaml"])
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8").strip()
    return ""


def run_command(command: List[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=1200,
        )
        text = adapter_output_for_stdout(proc.stdout) or proc.stdout.strip()
        if proc.stderr.strip():
            text = (text + "\n" if text else "") + proc.stderr.strip()
        is_error = proc.returncode != 0
    except subprocess.TimeoutExpired as exc:
        text = ((exc.stdout or "") + "\n" + (exc.stderr or "") + "\ncommand timed out after 1200s").strip()
        is_error = True
    return {
        "content": [{"type": "text", "text": text or "(no output)"}],
        "isError": is_error,
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
        for ip in arguments.get("environment_ips") or []:
            command.extend(["--environment-ip", str(ip)])
        if arguments.get("username"):
            command.extend(["--username", str(arguments["username"])])
        if arguments.get("password"):
            command.extend(["--password", str(arguments["password"])])
        if arguments.get("port"):
            command.extend(["--port", str(arguments["port"])])
        if arguments.get("incident_id"):
            command.extend(["--incident-id", str(arguments["incident_id"])])
        return run_command(command)

    if name == "midstack_analyse_incident":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "analyse",
            "--incident-dir",
            resolve_input_path(str(arguments.get("incident_dir") or "")),
        ]
        if arguments.get("output_dir"):
            command.extend(["--output-dir", resolve_output_path(str(arguments["output_dir"]))])
        if arguments.get("scenario"):
            command.extend(["--scenario", str(arguments["scenario"])])
        if arguments.get("customer_clue"):
            command.extend(["--customer-clue", str(arguments["customer_clue"])])
        if arguments.get("remote_namespace"):
            command.extend(["--remote-namespace", str(arguments["remote_namespace"])])
        return run_command(command)

    if name == "midstack_analyse_current":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "analyse",
            "--output-root",
            resolve_output_path(str(arguments.get("output_root") or ".local/incidents")),
        ]
        if arguments.get("scenario"):
            command.extend(["--scenario", str(arguments["scenario"])])
        if arguments.get("customer_clue"):
            command.extend(["--customer-clue", str(arguments["customer_clue"])])
        if arguments.get("remote_namespace"):
            command.extend(["--remote-namespace", str(arguments["remote_namespace"])])
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
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "review",
            "--output-root",
            resolve_output_path(str(arguments.get("output_root") or ".local/incidents")),
        ]
        if arguments.get("incident_dir"):
            command.extend(["--incident-dir", resolve_input_path(str(arguments.get("incident_dir") or ""))])
        return run_command(command)

    if name == "midstack_finalize_analysis":
        command = [
            sys.executable,
            "tools/plugin/midstack-local.py",
            "finalize-analysis",
            "--output-root",
            resolve_output_path(str(arguments.get("output_root") or ".local/incidents")),
        ]
        if arguments.get("incident_dir"):
            command.extend(["--incident-dir", resolve_input_path(str(arguments.get("incident_dir") or ""))])
        return run_command(command)

    return {
        "content": [{"type": "text", "text": "unknown tool: %s" % name}],
        "isError": True,
    }


def handle(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    message_id = message.get("id")
    debug_log("method=%s id=%s" % (method, message_id))
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "midstack-triage-cursor", "version": "0.1.0"},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": message_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        result = tool_call(str(params.get("name") or ""), params.get("arguments") or {})
        return {"jsonrpc": "2.0", "id": message_id, "result": result}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"resources": RESOURCES}}
    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"resourceTemplates": []}}
    if method == "resources/read":
        params = message.get("params") or {}
        uri = str(params.get("uri") or "")
        text = RESOURCE_TEXT.get(uri)
        if text is None:
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32002, "message": "resource not found: %s" % uri},
            }
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "result": {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "text/markdown",
                        "text": text,
                    }
                ]
            },
        }
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": message_id, "result": {"prompts": PROMPTS}}
    if method == "prompts/get":
        params = message.get("params") or {}
        name = str(params.get("name") or "")
        if name == "midstack_start":
            user_report = str((params.get("arguments") or {}).get("user_report") or "")
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "description": "Start Midstack triage from a user report.",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": START_USAGE + "\n\nUser report:\n" + user_report,
                            },
                        }
                    ],
                },
            }
        if name == "midstack_analyse_reasoning":
            incident_dir = resolve_input_path(str((params.get("arguments") or {}).get("incident_dir") or ""))
            task_file = Path(incident_dir) / "agent-reasoning-task.md"
            analysis_file = Path(incident_dir) / "analysis.yaml"
            report_file = Path(incident_dir) / "report.md"
            rule_draft_file = Path(incident_dir) / "analysis.rule-draft.yaml"
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "description": "Complete Midstack phase-4/5 reasoning from incident evidence.",
                    "messages": [
                        {
                            "role": "user",
                            "content": {
                                "type": "text",
                                "text": (
                                    "Read `%s` first. Then read the referenced evidence files in `%s`, "
                                    "treat `%s` as a fallback draft only, update `%s` as the final phase-4/5 result, "
                                    "including multi-hypothesis reasoning, expected_gap/critical_gap classification, "
                                    "source-boundary handling, and conclusion-depth limits. Update `%s` so it matches "
                                    "the final analysis, and then call "
                                    "`midstack_finalize_analysis` for `%s`."
                                )
                                % (task_file, incident_dir, rule_draft_file, analysis_file, report_file, incident_dir),
                            },
                        }
                    ],
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": -32003, "message": "prompt not found: %s" % params.get("name")},
        }
    if method and method.startswith("notifications/"):
        return None
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "error": {"code": -32601, "message": "method not found: %s" % method},
    }


def main() -> int:
    debug_log("server_start root=%s workspace=%s" % (ROOT, WORKSPACE_ROOT))
    try:
        while True:
            message = read_message()
            if message is None:
                debug_log("stdin_closed")
                return 0
            response = handle(message)
            if response is not None:
                write_message(response)
    except Exception:
        debug_log("fatal_exception\n%s" % traceback.format_exc())
        raise


if __name__ == "__main__":
    raise SystemExit(main())
