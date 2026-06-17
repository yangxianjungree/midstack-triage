#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from support.common import ROOT, run_command  # noqa: E402


DEFAULT_SANDBOX = ROOT.parent / "midstack-sandbox"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run installed Claude/Cursor adapter sandbox regression checks.")
    parser.add_argument(
        "--sandbox",
        default=str(DEFAULT_SANDBOX),
        help="Target sandbox workspace. Defaults to sibling ../midstack-sandbox.",
    )
    parser.add_argument("--skip-claude", action="store_true", help="Skip Claude plugin install/check/smoke.")
    parser.add_argument("--skip-cursor", action="store_true", help="Skip Cursor plugin install/check/smoke.")
    parser.add_argument(
        "--skip-claude-prompt",
        action="store_true",
        help="Skip `claude -p /midstack:validate`; still runs Claude installer check.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def run_check(check_id: str, command: List[str], cwd: Path = ROOT) -> Dict[str, Any]:
    proc = run_command(command, cwd=cwd)
    return {
        "check_id": check_id,
        "command": command,
        "cwd": str(cwd),
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def checks(args: argparse.Namespace, sandbox: Path) -> List[Dict[str, Any]]:
    plan: List[Dict[str, Any]] = []
    if not args.skip_cursor:
        plan.extend(
            [
                {
                    "check_id": "cursor-install",
                    "command": [
                        sys.executable,
                        "plugins/cursor/plugin-install.py",
                        "--upgrade",
                        "--workspace-init",
                        str(sandbox),
                    ],
                    "cwd": ROOT,
                },
                {
                    "check_id": "cursor-check-workspace",
                    "command": [
                        sys.executable,
                        "plugins/cursor/plugin-install.py",
                        "--check-workspace",
                        str(sandbox),
                    ],
                    "cwd": ROOT,
                },
                {
                    "check_id": "cursor-agent-cli-smoke",
                    "command": [sys.executable, "plugins/cursor/test-agent-cli.py"],
                    "cwd": ROOT,
                },
                {
                    "check_id": "cursor-sandbox-smoke",
                    "command": [sys.executable, "plugins/cursor/test-sandbox.py", str(sandbox)],
                    "cwd": ROOT,
                },
            ]
        )
    if not args.skip_claude:
        plan.extend(
            [
                {
                    "check_id": "claude-install",
                    "command": [
                        sys.executable,
                        "plugins/claude/plugin-install.py",
                        "install",
                        "--workspace",
                        str(sandbox),
                    ],
                    "cwd": ROOT,
                },
                {
                    "check_id": "claude-check",
                    "command": [
                        sys.executable,
                        "plugins/claude/plugin-install.py",
                        "check",
                        "--workspace",
                        str(sandbox),
                    ],
                    "cwd": ROOT,
                },
            ]
        )
        if not args.skip_claude_prompt:
            plan.append(
                {
                    "check_id": "claude-installed-validate",
                    "command": ["claude", "-p", "/midstack:validate", "--allowedTools", "Bash(python3 *)"],
                    "cwd": sandbox,
                }
            )
    return [run_check(item["check_id"], item["command"], item["cwd"]) for item in plan]


def print_text(results: List[Dict[str, Any]]) -> None:
    for item in results:
        print("%s: %s" % (item["check_id"], item["status"]))
        if item["stdout"]:
            print(item["stdout"])
        if item["stderr"]:
            print(item["stderr"], file=sys.stderr)


def main() -> int:
    args = parse_args()
    sandbox = Path(args.sandbox).expanduser().resolve()
    sandbox.mkdir(parents=True, exist_ok=True)

    results = checks(args, sandbox)
    failed = [item for item in results if item["status"] != "passed"]

    if args.format == "json":
        print(json.dumps({"status": "failed" if failed else "passed", "sandbox": str(sandbox), "results": results}, indent=2))
    else:
        print("sandbox: %s" % sandbox)
        print_text(results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
