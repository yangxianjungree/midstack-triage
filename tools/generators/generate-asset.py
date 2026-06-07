#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[2]

KIND_CONFIG = {
    "runbook": {
        "dir": ("runbooks",),
        "metadata_template": "runbook-metadata.template.yaml",
        "body_template": "runbook.template.md",
        "body_name": "runbook.md",
    },
    "command": {
        "dir": ("commands",),
        "metadata_template": "command-metadata.template.yaml",
        "body_template": "command.template.md",
        "body_name": "command.md",
    },
    "skill": {
        "dir": ("skills",),
        "metadata_template": "skill-metadata.template.yaml",
        "body_template": "skill.template.md",
        "body_name": "skill.md",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a standard midstack-triage asset skeleton.")
    parser.add_argument("--kind", choices=sorted(list(KIND_CONFIG) + ["bundle"]), required=True)
    parser.add_argument("--middleware", required=True)
    parser.add_argument("--component", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--slug", required=True, help="Directory slug for the new asset.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--command-slug", help="Bundle-only command slug. Defaults to check-<slug>.")
    parser.add_argument("--skill-slug", help="Bundle-only skill slug. Defaults to triage-<slug>.")
    parser.add_argument("--command-title", help="Bundle-only command title. Defaults to Check <title>.")
    parser.add_argument("--skill-title", help="Bundle-only skill title. Defaults to Triage <title>.")
    parser.add_argument("--runbook-ref", help="Skill required_assets runbook slug. Defaults to --slug.")
    parser.add_argument("--command-ref", help="Skill required_assets command slug. Defaults to --slug.")
    parser.add_argument("--output-root", default="domains", help="Repository-relative domain root.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing generated files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned files without writing.")
    return parser.parse_args()


def read_template(name: str) -> str:
    path = ROOT / "core" / "templates" / name
    return path.read_text(encoding="utf-8")


def replacements(args: argparse.Namespace) -> Dict[str, str]:
    asset_id = "%s-%s" % (args.middleware, args.slug)
    runbook_ref = args.runbook_ref or args.slug
    command_ref = args.command_ref or args.slug
    return {
        "<middleware>": args.middleware,
        "<component>": args.component,
        "<scenario>": args.scenario,
        "<Runbook Title>": args.title,
        "<Command Title>": args.title,
        "<Skill Title>": args.title,
        "<runbook-id>": runbook_ref,
        "<command-id>": command_ref,
        "<skill-purpose>": args.slug,
        "<command-purpose>": args.slug,
        "<one sentence summary>": "TODO: summarize this asset.",
        "<tag>": "todo",
        "<tool>": "todo",
        "<required input>": "TODO: required input",
        "<expected output>": "TODO: expected output",
        "<safety boundary>": "TODO: safety boundary",
        "<safety note or rollback boundary>": "TODO: safety note",
        "<how to verify the diagnosis result>": "TODO: verification step",
        "id: <middleware>-<component>-<scenario>": "id: %s" % asset_id,
        "id: <middleware>-<command-purpose>": "id: %s" % asset_id,
        "id: <middleware>-<skill-purpose>": "id: %s" % asset_id,
    }


def render(template: str, mapping: Dict[str, str]) -> str:
    output = template
    for key, value in mapping.items():
        output = output.replace(key, value)
    return output


def target_dir(args: argparse.Namespace) -> Path:
    config = KIND_CONFIG[args.kind]
    return ROOT / args.output_root / args.middleware / config["dir"][0] / args.component / args.slug


def single_asset_files(args: argparse.Namespace) -> List[Tuple[Path, str]]:
    config = KIND_CONFIG[args.kind]
    mapping = replacements(args)
    base = target_dir(args)
    metadata = render(read_template(config["metadata_template"]), mapping)
    body = render(read_template(config["body_template"]), mapping)
    return [
        (base / "metadata.yaml", metadata),
        (base / config["body_name"], body),
    ]


def asset_args(args: argparse.Namespace, kind: str, slug: str, title: str, runbook_ref: str, command_ref: str) -> argparse.Namespace:
    return argparse.Namespace(
        kind=kind,
        middleware=args.middleware,
        component=args.component,
        scenario=args.scenario,
        slug=slug,
        title=title,
        output_root=args.output_root,
        force=args.force,
        dry_run=args.dry_run,
        runbook_ref=runbook_ref,
        command_ref=command_ref,
    )


def planned_files(args: argparse.Namespace) -> List[Tuple[Path, str]]:
    if args.kind != "bundle":
        return single_asset_files(args)

    runbook_slug = args.slug
    command_slug = args.command_slug or "check-%s" % args.slug
    skill_slug = args.skill_slug or "triage-%s" % args.slug
    command_title = args.command_title or "Check %s" % args.title
    skill_title = args.skill_title or "Triage %s" % args.title

    files: List[Tuple[Path, str]] = []
    files.extend(single_asset_files(asset_args(args, "runbook", runbook_slug, args.title, runbook_slug, command_slug)))
    files.extend(single_asset_files(asset_args(args, "command", command_slug, command_title, runbook_slug, command_slug)))
    files.extend(single_asset_files(asset_args(args, "skill", skill_slug, skill_title, runbook_slug, command_slug)))
    return files


def validate_args(args: argparse.Namespace) -> int:
    scenario_path = ROOT / "scenarios" / args.scenario / "scenario.yaml"
    if not scenario_path.exists():
        print("ERROR: scenario does not exist: %s" % scenario_path, file=sys.stderr)
        return 1
    return 0


def write_files(files: List[Tuple[Path, str]], force: bool, dry_run: bool) -> int:
    for path, _ in files:
        if path.exists() and not force and not dry_run:
            print("ERROR: %s already exists; use --force to overwrite" % path, file=sys.stderr)
            return 1

    for path, content in files:
        if dry_run:
            suffix = " (exists)" if path.exists() else ""
            print("would write %s%s" % (path, suffix))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print("wrote %s" % path)
    return 0


def main() -> int:
    args = parse_args()
    validation_result = validate_args(args)
    if validation_result:
        return validation_result
    files = planned_files(args)
    return write_files(files, args.force, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
