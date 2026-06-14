#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = ROOT / "tools" / "lib"
SRC_DIR = ROOT / "src"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from midstack_runtime import (  # noqa: E402
    adapter_output,
    add_record_ref_if_exists,
    load_incident_meta,
    load_yaml,
    path_from_arg,
    read_current_incident,
    resolve_path,
    update_incident_meta,
    write_blocked_output,
    write_current_incident,
    write_yaml,
)
from midstack_runtime.analysis import (  # noqa: E402
    AGENT_REASONING_TASK_FILENAME,
    ANALYSIS_RULE_DRAFT_FILENAME,
    analysis_matches_rule_draft,
    analysis_next_action_texts,
    analysis_summary_text,
    apply_analysis_guardrails,
    write_agent_reasoning_task,
    write_report,
)
from commands import analyse as analyse_command  # noqa: E402
from commands import finalize as finalize_command  # noqa: E402
from commands import review as review_command  # noqa: E402
from commands import start as start_command  # noqa: E402
from phases.phase1.startup import validate_remote_environment  # noqa: E402
from phases.phase3.collection import (  # noqa: E402
    build_incident_from_remote_run,
    apply_scenario_routing_if_needed,
    enrich_skill_runtime_context,
    load_remote_executor_run_result,
    normalize_collection_report_gaps,
    remote_executor_next_actions,
    remote_executor_required_user_action,
    run_remote_smoke,
    run_directed_recollection_if_needed,
)
from phases.phase2.inventory import discover_mongodb_inventory  # noqa: E402


ANALYSABLE_STATUSES = ("ready", "analysed")
ANALYSIS_RULE_DRAFT_FILENAME = "analysis.rule-draft.yaml"
AGENT_REASONING_TASK_FILENAME = "agent-reasoning-task.md"


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
        root=ROOT,
        run_remote_smoke=run_remote_smoke,
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Local midstack-triage plugin command prototype.")
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
    input_source.add_argument("--remote-config", help="Run MongoDB remote smoke first, then analyse the generated remote run directory.")
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

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
