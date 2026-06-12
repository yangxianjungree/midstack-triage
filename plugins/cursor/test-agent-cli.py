#!/usr/bin/env python3

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cli_smoke import (
    assert_command_contracts,
    assert_incident_outputs,
    check_manifest,
    check_workspace,
    run_cli_analyse_fixture,
    run_cli_review,
    upgrade_workspace,
)


ROOT = Path(__file__).resolve().parents[2]
INCIDENT_RELPATH = ".local/incidents/cursor-agent-cli-test"


def main() -> int:
    temp_parent = ROOT / ".local" / "cursor-agent-cli-tests"
    temp_parent.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="midstack-agent-cli-", dir=str(temp_parent)))
    try:
        check_manifest()
        assert_command_contracts()
        upgrade_workspace(workspace)
        check_workspace(workspace)

        analyse = run_cli_analyse_fixture(
            workspace,
            fixture_relpath="tests/fixtures/mongodb/connection-failure-sample",
            output_relpath=INCIDENT_RELPATH,
        )
        if analyse.returncode != 0:
            raise AssertionError(analyse.stderr.strip() or analyse.stdout.strip())

        review = run_cli_review(workspace, incident_relpath=INCIDENT_RELPATH)
        if review.returncode != 0:
            raise AssertionError(review.stderr.strip() or review.stdout.strip())

        assert_incident_outputs(workspace, INCIDENT_RELPATH, require_review=True)
        print("ok: cursor agent-cli smoke test passed")
        return 0
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
