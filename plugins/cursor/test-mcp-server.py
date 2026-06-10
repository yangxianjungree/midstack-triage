#!/usr/bin/env python3

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

import yaml


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


def ndjson_request(proc: subprocess.Popen, payload: Dict[str, Any]) -> Dict[str, Any]:
    proc.stdin.write((json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8"))
    proc.stdin.flush()
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("server closed stdout")
    return json.loads(line.decode("utf-8"))


def assert_ok(response: Dict[str, Any]) -> None:
    if "error" in response:
        raise AssertionError(response["error"])


def main() -> int:
    temp_parent = ROOT / ".local" / "cursor-mcp-tests"
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
        resources = request(proc, {"jsonrpc": "2.0", "id": 3, "method": "resources/list", "params": {}})
        assert_ok(resources)
        resource_uris = {item["uri"] for item in resources["result"]["resources"]}
        if "midstack://commands/start" not in resource_uris:
            raise AssertionError("missing start resource: %s" % sorted(resource_uris))
        start_resource = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "resources/read",
                "params": {"uri": "midstack://commands/start"},
            },
        )
        assert_ok(start_resource)
        start_text = start_resource["result"]["contents"][0]["text"]
        if "call the `midstack_start` MCP tool directly" not in start_text:
            raise AssertionError("start resource does not contain direct tool-call guidance")
        prompts = request(proc, {"jsonrpc": "2.0", "id": 5, "method": "prompts/list", "params": {}})
        assert_ok(prompts)
        prompt_names = {item["name"] for item in prompts["result"]["prompts"]}
        if "midstack_start" not in prompt_names:
            raise AssertionError("missing midstack_start prompt")
        analyse = request(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 6,
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
                "id": 7,
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
        if not expected_analysis.exists():
            raise AssertionError("expected Cursor workspace outputs were not created")
        analysis_data = yaml.safe_load(expected_analysis.read_text(encoding="utf-8")) or {}
        if "review" not in analysis_data:
            raise AssertionError("expected review block in analysis.yaml")
        print("ok: cursor MCP server smoke test passed")
    finally:
        proc.stdin.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(temp_project, ignore_errors=True)

    ndjson_proc = subprocess.Popen(
        [sys.executable, str(ROOT / "plugins" / "cursor" / "mcp-server.py")],
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        assert_ok(ndjson_request(ndjson_proc, {"jsonrpc": "2.0", "id": 11, "method": "initialize", "params": {}}))
        tools = ndjson_request(ndjson_proc, {"jsonrpc": "2.0", "id": 12, "method": "tools/list", "params": {}})
        assert_ok(tools)
        names = {item["name"] for item in tools["result"]["tools"]}
        if "midstack_start" not in names:
            raise AssertionError("NDJSON tools/list missing midstack_start")
        print("ok: cursor MCP server NDJSON smoke test passed")
        return 0
    finally:
        ndjson_proc.stdin.close()
        ndjson_proc.terminate()
        try:
            ndjson_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ndjson_proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
