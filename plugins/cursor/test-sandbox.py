#!/usr/bin/env python3

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_smoke import (
    assert_current_incident_blocked_without_traceback,
    assert_incident_outputs,
    check_manifest,
    check_workspace,
    run_cli_analyse_current_incident,
    run_cli_analyse_fixture,
    run_cli_review,
    run_plugin_install,
    upgrade_workspace,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SANDBOX = ROOT.parent / "midstack-sandbox"
INCIDENT_RELPATH = ".local/incidents/cursor-sandbox-k8s-runtime-test"
CURRENT_INCIDENT_RELPATH = ".local/incidents/cursor-sandbox-current-incident-test"
FIXTURE = "tests/fixtures/active/mongodb/kubernetes-scheduling-failure-sample"


def main() -> int:
    sandbox = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_SANDBOX
    sandbox.mkdir(parents=True, exist_ok=True)

    check_manifest()
    upgrade_workspace(sandbox)
    check_workspace(sandbox)

    link = run_plugin_install(["--link"])
    if link.returncode != 0:
        print(link.stderr or link.stdout, file=sys.stderr)
        return link.returncode

    analyse = run_cli_analyse_fixture(
        sandbox,
        fixture_relpath=FIXTURE,
        output_relpath=INCIDENT_RELPATH,
    )
    if analyse.returncode != 0:
        print(analyse.stderr or analyse.stdout, file=sys.stderr)
        return analyse.returncode

    review = run_cli_review(sandbox, incident_relpath=INCIDENT_RELPATH)
    if review.returncode != 0:
        print(review.stderr or review.stdout, file=sys.stderr)
        return review.returncode

    try:
        assert_incident_outputs(
            sandbox,
            INCIDENT_RELPATH,
            require_review=True,
            text_token="kubernetes-scheduling",
        )
    except AssertionError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    current_analyse = run_cli_analyse_current_incident(
        sandbox,
        incident_relpath=CURRENT_INCIDENT_RELPATH,
    )
    try:
        assert_current_incident_blocked_without_traceback(sandbox, CURRENT_INCIDENT_RELPATH, current_analyse)
    except AssertionError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1

    print("ok: Cursor sandbox upgraded (agent-cli) and smoke tested: %s" % sandbox)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
