#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = Path(__file__).resolve().parent
SERVER_NAME = "midstack-triage"
REQUIRED_COMMANDS = [
    "midstack:start.md",
    "midstack:analyse.md",
    "midstack:review.md",
    "midstack:validate.md",
]
REMOVED_COMMANDS = [
    "midstack-start.md",
    "midstack-analyse.md",
    "midstack-review.md",
    "midstack-validate.md",
]


def config_payload(target_root: Path) -> Dict[str, Any]:
    return {
        "command": "python3",
        "args": [str(PLUGIN_DIR / "mcp-server.py")],
        "env": {"MIDSTACK_TRIAGE_WORKSPACE": str(target_root)},
    }


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or verify the Midstack Triage Cursor MCP configuration.")
    parser.add_argument("--target-dir", required=True, help="Cursor workspace/project directory to install into.")
    parser.add_argument("--check", action="store_true", help="Only verify .cursor/mcp.json, do not modify files.")
    return parser.parse_args()


def sync_cursor_files(target_root: Path) -> None:
    command_dir = target_root / ".cursor" / "commands"
    command_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_COMMANDS:
        source = PLUGIN_DIR / "commands" / name
        target = command_dir / name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    rule_dir = target_root / ".cursor" / "rules"
    rule_dir.mkdir(parents=True, exist_ok=True)
    source_rule = PLUGIN_DIR / "rules" / "midstack-triage.mdc"
    target_rule = rule_dir / "midstack-triage.mdc"
    target_rule.write_text(source_rule.read_text(encoding="utf-8"), encoding="utf-8")

    for name in REMOVED_COMMANDS:
        stale = command_dir / name
        if stale.exists():
            stale.unlink()


def main() -> int:
    args = parse_args()
    target_root = Path(args.target_dir).expanduser().resolve()
    config_path = target_root / ".cursor" / "mcp.json"
    config = load_json(config_path)
    servers = config.setdefault("mcpServers", {})
    expected = config_payload(target_root)

    if args.check:
        actual = servers.get(SERVER_NAME)
        if actual != expected:
            print("ERROR: Cursor MCP config is not installed or differs from expected payload", file=sys.stderr)
            print(json.dumps({"expected": expected, "actual": actual}, indent=2, sort_keys=False), file=sys.stderr)
            return 1
        command_dir = target_root / ".cursor" / "commands"
        missing = [name for name in REQUIRED_COMMANDS if not (command_dir / name).exists()]
        stale = [name for name in REMOVED_COMMANDS if (command_dir / name).exists()]
        drift = []
        for name in REQUIRED_COMMANDS:
            source = PLUGIN_DIR / "commands" / name
            target = command_dir / name
            if target.exists() and source.exists() and target.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
                drift.append(name)
        rule_source = PLUGIN_DIR / "rules" / "midstack-triage.mdc"
        rule_target = target_root / ".cursor" / "rules" / "midstack-triage.mdc"
        if rule_target.exists() and rule_source.exists() and rule_target.read_text(encoding="utf-8") != rule_source.read_text(encoding="utf-8"):
            drift.append("rules/midstack-triage.mdc")
        if missing or stale or drift:
            print("ERROR: Cursor command files are not in expected /midstack:* form", file=sys.stderr)
            print(json.dumps({"missing": missing, "stale": stale, "drift": drift}, indent=2, sort_keys=False), file=sys.stderr)
            return 1
        print("ok: Cursor MCP config installed")
        return 0

    sync_cursor_files(target_root)
    servers[SERVER_NAME] = expected
    write_json(config_path, config)
    print(str(config_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
