#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the repository validation suite.")
    parser.add_argument("--skip-replay", action="store_true", help="Skip fixture replay.")
    parser.add_argument("--skip-score", action="store_true", help="Skip replay score gate.")
    parser.add_argument("--skip-cursor", action="store_true", help="Skip Cursor agent-cli plugin smoke test.")
    parser.add_argument("--score-min-level", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args()


def run_check(check_id: str, command: List[str]) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return {
        "check_id": check_id,
        "command": command,
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def checks(args: argparse.Namespace) -> List[Dict[str, Any]]:
    plan = [
        {
            "check_id": "mongodb-assets",
            "command": [sys.executable, "tools/validators/validate-mongodb-scripts.py"],
        },
        {
            "check_id": "pulsar-assets",
            "command": [sys.executable, "tools/validators/validate-pulsar-scripts.py"],
        },
        {
            "check_id": "golden-paths",
            "command": [sys.executable, "tools/validators/validate-golden-paths.py", "--all"],
        },
        {
            "check_id": "patch-merge",
            "command": [sys.executable, "tools/validators/validate-patch-merge.py"],
        },
        {
            "check_id": "fixture-hygiene",
            "command": [sys.executable, "tools/validators/validate-fixture-hygiene.py"],
        },
        {
            "check_id": "runtime-classification",
            "command": [sys.executable, "tools/validators/validate-runtime-classification.py"],
        },
        {
            "check_id": "scenario-routing",
            "command": [sys.executable, "tools/validators/validate-scenario-routing.py"],
        },
        {
            "check_id": "remote-smoke",
            "command": [sys.executable, "tools/validators/validate-remote-smoke.py"],
        },
    ]
    if not args.skip_replay:
        plan.append(
            {
                "check_id": "mongodb-replay",
                "command": [sys.executable, "tools/replay/mongodb-replay.py", "--run-analyse"],
            }
        )
    if not args.skip_score:
        plan.append(
            {
                "check_id": "mongodb-score-gate",
                "command": [
                    sys.executable,
                    "tools/replay/mongodb-score.py",
                    "--run-analyse",
                    "--min-level",
                    args.score_min_level,
                ],
            }
        )
    if not args.skip_cursor:
        plan.append(
            {
                "check_id": "cursor-agent-cli-smoke",
                "command": [sys.executable, "plugins/cursor/test-agent-cli.py"],
            }
        )
    return plan


def main() -> int:
    args = parse_args()
    results = [run_check(item["check_id"], item["command"]) for item in checks(args)]
    failed = [item for item in results if item["status"] != "passed"]

    if args.format == "json":
        print(json.dumps({"status": "failed" if failed else "passed", "results": results}, indent=2, sort_keys=False))
    else:
        for item in results:
            print("%s: %s" % (item["check_id"], item["status"]))
            if item["stdout"]:
                print(item["stdout"])
            if item["stderr"]:
                print(item["stderr"], file=sys.stderr)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
