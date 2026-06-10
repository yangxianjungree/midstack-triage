#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = Path("/home/stephen/AI/midstack-cursor-sandbox")


def encode(payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n\r\n" + body


def read_message(proc: subprocess.Popen) -> Dict[str, Any]:
    headers = {}
    while True:
        line = proc.stdout.readline()
        if line in (b"\r\n", b"\n"):
            break
        if not line:
            raise RuntimeError("server closed stdout")
        text = line.decode("ascii").strip()
        if ":" in text:
            key, value = text.split(":", 1)
            headers[key.lower()] = value.strip()
    length = int(headers["content-length"])
    return json.loads(proc.stdout.read(length).decode("utf-8"))


def request(proc: subprocess.Popen, payload: Dict[str, Any]) -> Dict[str, Any]:
    proc.stdin.write(encode(payload))
    proc.stdin.flush()
    return read_message(proc)


def main() -> int:
    sandbox = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SANDBOX
    sandbox.mkdir(parents=True, exist_ok=True)
    readme = sandbox / "README.md"
    if not readme.exists():
        readme.write_text("# Midstack Cursor Sandbox\n\nTemporary project for Cursor plugin testing.\n", encoding="utf-8")

    install = subprocess.run(
        [sys.executable, str(ROOT / "plugins" / "cursor" / "install.py"), "--target-dir", str(sandbox), "--approve"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if install.returncode != 0:
        print(install.stderr, file=sys.stderr)
        return install.returncode
    check = subprocess.run(
        [sys.executable, str(ROOT / "plugins" / "cursor" / "install.py"), "--target-dir", str(sandbox), "--check"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    if check.returncode != 0:
        print(check.stderr, file=sys.stderr)
        return check.returncode
    list_tools = subprocess.run(
        ["agent", "mcp", "list-tools", "midstack-triage"],
        cwd=str(sandbox),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=30,
    )
    if list_tools.returncode != 0:
        print(list_tools.stderr or list_tools.stdout, file=sys.stderr)
        return list_tools.returncode
    if "midstack_start" not in list_tools.stdout:
        print("ERROR: Cursor CLI did not list midstack_start", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(sandbox)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "plugins" / "cursor" / "mcp-server.py")],
        cwd=str(sandbox),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        request(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        proc.stdin.write(encode({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}))
        proc.stdin.flush()
        resources = request(proc, {"jsonrpc": "2.0", "id": 2, "method": "resources/list", "params": {}})
        if "error" in resources:
            raise RuntimeError(resources["error"])
        resource_uris = {item["uri"] for item in resources["result"]["resources"]}
        if "midstack://commands/start" not in resource_uris:
            raise RuntimeError("missing start resource: %s" % sorted(resource_uris))
        analyse = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "midstack_analyse_fixture",
                    "arguments": {
                        "input_dir": "tests/fixtures/mongodb/kubernetes-scheduling-failure-sample",
                        "output_dir": ".local/incidents/cursor-sandbox-k8s-runtime-test",
                    },
                },
            },
        )
        if analyse["result"].get("isError"):
            raise RuntimeError(analyse["result"])
        review = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "midstack_review",
                    "arguments": {"incident_dir": ".local/incidents/cursor-sandbox-k8s-runtime-test"},
                },
            },
        )
        if review["result"].get("isError"):
            raise RuntimeError(review["result"])
    finally:
        proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    analysis_file = sandbox / ".local" / "incidents" / "cursor-sandbox-k8s-runtime-test" / "analysis.yaml"
    reasoning_task_file = sandbox / ".local" / "incidents" / "cursor-sandbox-k8s-runtime-test" / "agent-reasoning-task.md"
    if not analysis_file.exists():
        print("ERROR: sandbox analysis output was not created", file=sys.stderr)
        return 1
    if not reasoning_task_file.exists():
        print("ERROR: sandbox agent reasoning task was not created", file=sys.stderr)
        return 1
    analysis = yaml.safe_load(analysis_file.read_text(encoding="utf-8")) or {}
    if "review" not in analysis:
        print("ERROR: sandbox analysis does not contain review block", file=sys.stderr)
        return 1
    if "kubernetes-scheduling" not in analysis_file.read_text(encoding="utf-8"):
        print("ERROR: sandbox analysis did not classify Kubernetes scheduling failure", file=sys.stderr)
        return 1
    print("ok: Cursor sandbox installed and smoke tested: %s" % sandbox)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
