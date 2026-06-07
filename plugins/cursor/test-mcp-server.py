#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]


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


def assert_ok(response: Dict[str, Any]) -> None:
    if "error" in response:
        raise AssertionError(response["error"])


def main() -> int:
    temp_parent = Path("/home/stephen/AI")
    if not temp_parent.exists():
        temp_parent = ROOT / ".local"
        temp_parent.mkdir(parents=True, exist_ok=True)
    temp_project = Path(tempfile.mkdtemp(prefix="midstack-cursor-test-", dir=str(temp_parent)))
    env = os.environ.copy()
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(temp_project)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "plugins" / "cursor" / "mcp-server.py")],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        install = subprocess.run(
            [
                sys.executable,
                str(ROOT / "plugins" / "cursor" / "install.py"),
                "--target-dir",
                str(temp_project),
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if install.returncode != 0:
            raise AssertionError(install.stderr.strip())
        check = subprocess.run(
            [
                sys.executable,
                str(ROOT / "plugins" / "cursor" / "install.py"),
                "--target-dir",
                str(temp_project),
                "--check",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        if check.returncode != 0:
            raise AssertionError(check.stderr.strip())

        assert_ok(request(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        proc.stdin.write(encode({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}))
        proc.stdin.flush()
        tools = request(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        assert_ok(tools)
        names = {item["name"] for item in tools["result"]["tools"]}
        required = {"midstack_validate", "midstack_analyse_fixture", "midstack_analyse_remote_config", "midstack_review"}
        missing = required - names
        if missing:
            raise AssertionError("missing tools: %s" % sorted(missing))
        analyse = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "midstack_analyse_fixture",
                    "arguments": {
                        "input_dir": "tests/fixtures/mongodb/connection-failure-sample",
                        "output_dir": ".local/incidents/cursor-mcp-test",
                    },
                },
            },
        )
        assert_ok(analyse)
        if analyse["result"].get("isError"):
            raise AssertionError(analyse["result"])
        review = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "midstack_review",
                    "arguments": {"incident_dir": ".local/incidents/cursor-mcp-test"},
                },
            },
        )
        assert_ok(review)
        if review["result"].get("isError"):
            raise AssertionError(review["result"])
        expected_analysis = temp_project / ".local" / "incidents" / "cursor-mcp-test" / "analysis.yaml"
        expected_review = temp_project / ".local" / "incidents" / "cursor-mcp-test" / "review.yaml"
        if not expected_analysis.exists() or not expected_review.exists():
            raise AssertionError("expected Cursor workspace outputs were not created")
        print("ok: cursor MCP server smoke test passed")
        return 0
    finally:
        proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(temp_project, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
