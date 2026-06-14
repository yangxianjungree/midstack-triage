import argparse
import sys
from pathlib import Path
from typing import List, Tuple

from support.common import ROOT, write_text_files

VALID_RISK_LEVELS = {"read-only", "low-risk", "high-risk"}
KIND_CONFIG = {
    "runbook": {
        "domain_dir": "runbooks",
        "body_name": "runbook.md",
    },
    "command": {
        "domain_dir": "commands",
        "body_name": "command.md",
    },
    "skill": {
        "domain_dir": "skills",
        "body_name": "skill.md",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import an existing Markdown document as a standard asset.")
    parser.add_argument("--kind", choices=sorted(KIND_CONFIG), default="runbook")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--middleware", required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--summary", default="TODO: summarize this imported runbook.")
    parser.add_argument("--risk-level", default="read-only", choices=sorted(VALID_RISK_LEVELS))
    parser.add_argument("--output-root", default="domains")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def target_dir(args: argparse.Namespace) -> Path:
    return ROOT / args.output_root / args.middleware / KIND_CONFIG[args.kind]["domain_dir"] / args.component / args.slug


def runbook_metadata(args: argparse.Namespace) -> str:
    asset_id = "%s-%s" % (args.middleware, args.slug)
    return """id: %s
title: %s
middleware: %s
component: %s
scenario: %s
summary: %s
risk_level: %s
tags:
  - imported
required_tools:
  - TODO
applicable_env:
  - kubernetes
verification_steps:
  - TODO: add verification step
rollback_or_safety_notes:
  - TODO: add safety note
""" % (
        asset_id,
        args.title,
        args.middleware,
        args.component,
        args.scenario,
        args.summary,
        args.risk_level,
    )


def command_metadata(args: argparse.Namespace) -> str:
    asset_id = "%s-%s" % (args.middleware, args.slug)
    return """id: %s
title: %s
middleware: %s
component: %s
scenario: %s
risk_level: %s
tags:
  - imported
required_tools:
  - TODO
expected_signal:
  - TODO: add expected signal
""" % (
        asset_id,
        args.title,
        args.middleware,
        args.component,
        args.scenario,
        args.risk_level,
    )


def skill_metadata(args: argparse.Namespace) -> str:
    asset_id = "%s-%s" % (args.middleware, args.slug)
    return """id: %s
title: %s
middleware: %s
component: %s
primary_scenario: %s
inputs:
  - TODO: add required input
outputs:
  - TODO: add expected output
required_assets:
  - TODO: add required asset path
safety_constraints:
  - TODO: add safety constraint
""" % (
        asset_id,
        args.title,
        args.middleware,
        args.component,
        args.scenario,
    )


def metadata(args: argparse.Namespace) -> str:
    if args.kind == "runbook":
        return runbook_metadata(args)
    if args.kind == "command":
        return command_metadata(args)
    if args.kind == "skill":
        return skill_metadata(args)
    raise ValueError("unsupported kind: %s" % args.kind)


def body(args: argparse.Namespace) -> str:
    source_path = Path(args.source_file)
    content = source_path.read_text(encoding="utf-8")
    header = "# %s\n\n" % args.title
    note = "> Imported from `%s`. Review metadata, safety notes, and any sensitive content before publishing.\n\n" % source_path
    if content.lstrip().startswith("#"):
        return note + content
    return header + note + content


def planned_files(args: argparse.Namespace) -> List[Tuple[Path, str]]:
    base = target_dir(args)
    return [
        (base / "metadata.yaml", metadata(args)),
        (base / KIND_CONFIG[args.kind]["body_name"], body(args)),
    ]


def main() -> int:
    args = parse_args()
    source_path = Path(args.source_file)
    if not source_path.exists():
        print("ERROR: source file does not exist: %s" % source_path, file=sys.stderr)
        return 1
    files = planned_files(args)
    return write_text_files(files, args.force, args.dry_run)
