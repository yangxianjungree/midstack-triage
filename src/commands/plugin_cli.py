"""Local plugin CLI adapter for Midstack slash commands."""

from __future__ import annotations

import argparse

from execution.remote.access import validate_remote_environment
from commands import analyse as analyse_command
from commands import finalize as finalize_command
from commands import review as review_command
from commands import start as start_command
from phases.phase2.inventory import discover_mongodb_inventory
from phases.phase3.collection import (
    apply_scenario_routing_if_needed,
    build_incident_from_remote_run,
    enrich_skill_runtime_context,
    load_remote_executor_run_result,
    normalize_collection_report_gaps,
    remote_executor_next_actions,
    remote_executor_required_user_action,
    run_directed_recollection_if_needed,
    run_remote_collection,
)

def command_start(args: argparse.Namespace) -> int:
    return start_command.run(
        args,
        validate_remote_environment=validate_remote_environment,
        discover_mongodb_inventory=discover_mongodb_inventory,
    )


def command_finalize_analysis(args: argparse.Namespace) -> int:
    return finalize_command.run(args, normalize_collection_report_gaps)


def command_analyse(args: argparse.Namespace) -> int:
    from phases.phase4.reasoning import run_phase4_analysis

    return analyse_command.run(
        args,
        run_remote_collection=run_remote_collection,
        load_remote_executor_run_result=load_remote_executor_run_result,
        build_incident_from_remote_run=build_incident_from_remote_run,
        apply_scenario_routing_if_needed=apply_scenario_routing_if_needed,
        enrich_skill_runtime_context=enrich_skill_runtime_context,
        run_directed_recollection_if_needed=run_directed_recollection_if_needed,
        remote_executor_required_user_action=remote_executor_required_user_action,
        remote_executor_next_actions=remote_executor_next_actions,
        normalize_collection_report_gaps=normalize_collection_report_gaps,
        run_phase4_analysis=run_phase4_analysis,
    )


def command_review(args: argparse.Namespace) -> int:
    return review_command.run(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Midstack CLI adapter for slash-command flows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("--middleware", required=True)
    start.add_argument("--customer-clue", default="")
    start.add_argument("--namespace", default="")
    start.add_argument("--cluster-id", default="")
    start.add_argument("--incident-id")
    start.add_argument("--output-root", default=".local/incidents")
    start.add_argument("--environment-ip", action="append", default=[], help="Remote environment IP. May be repeated; the first IP is used as jump host.")
    start.add_argument("--username", default="")
    start.add_argument("--password", default="")
    start.add_argument("--port", type=int, default=22)
    start.set_defaults(func=command_start)

    analyse = subparsers.add_parser("analyse")
    input_source = analyse.add_mutually_exclusive_group(required=False)
    input_source.add_argument("--input-dir")
    input_source.add_argument("--remote-run-dir")
    input_source.add_argument("--remote-config", help="Run MongoDB remote collection first, then analyse the generated remote run directory.")
    input_source.add_argument("--incident-dir", help="Run analyse from a started incident directory containing remote-config.yaml.")
    analyse.add_argument("--output-dir")
    analyse.add_argument("--output-root", default=".local/incidents")
    analyse.add_argument("--scenario", help="Override or supply scenario when analysing a remote run.")
    analyse.add_argument("--customer-clue", help="Override or supply customer clue when analysing a remote run.")
    analyse.add_argument("--remote-output-dir", default=".local/remote-runs")
    analyse.add_argument("--remote-namespace", default="")
    analyse.add_argument("--object-inventory", default="")
    analyse.set_defaults(func=command_analyse)

    review = subparsers.add_parser("review")
    review.add_argument("--incident-dir")
    review.add_argument("--output-root", default=".local/incidents")
    review.set_defaults(func=command_review)

    finalize = subparsers.add_parser("finalize-analysis")
    finalize.add_argument("--incident-dir")
    finalize.add_argument("--output-root", default=".local/incidents")
    finalize.set_defaults(func=command_finalize_analysis)

    return parser


def parse_args() -> argparse.Namespace:
    return build_parser().parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)
