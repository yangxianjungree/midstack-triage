#!/usr/bin/env python3

"""Shared helpers for Cursor agent-cli integration smoke tests."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import yaml


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_INSTALL = PLUGIN_DIR / "plugin-install.py"
MIDSTACK_LOCAL = ROOT / "tools" / "plugin" / "midstack-local.py"
COMMAND_FILES = [
    "midstack:start.md",
    "midstack:analyse.md",
    "midstack:review.md",
    "midstack:validate.md",
]


def run_plugin_install(args: List[str], cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), *args],
        cwd=str(cwd or ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def upgrade_workspace(workspace: Path) -> None:
    proc = run_plugin_install(["--upgrade", "--workspace-init", str(workspace)])
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip() or proc.stdout.strip())


def check_workspace(workspace: Path) -> None:
    proc = run_plugin_install(["--check-workspace", str(workspace)])
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip() or proc.stdout.strip())


def check_manifest() -> None:
    proc = run_plugin_install(["--check-manifest"])
    if proc.returncode != 0:
        raise AssertionError(proc.stderr.strip() or proc.stdout.strip())


def assert_command_contracts() -> None:
    errors: List[str] = []
    for name in COMMAND_FILES:
        path = PLUGIN_DIR / "commands" / name
        text = path.read_text(encoding="utf-8")
        if name == "midstack:validate.md":
            if "validate-repo.py" not in text:
                errors.append("%s must reference validate-repo.py" % name)
        elif "midstack-local.py" not in text:
            errors.append("%s must reference midstack-local.py" % name)
        if "Agent CLI + shell" not in text:
            errors.append("%s must declare Agent CLI + shell usage" % name)
    rule = (PLUGIN_DIR / "rules" / "midstack-triage.mdc").read_text(encoding="utf-8")
    if "midstack-local.py" not in rule:
        errors.append("rules must reference midstack-local.py")
    if errors:
        raise AssertionError("; ".join(errors))


def run_cli_analyse_fixture(
    workspace: Path,
    *,
    fixture_relpath: str,
    output_relpath: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)
    return subprocess.run(
        [
            sys.executable,
            str(MIDSTACK_LOCAL),
            "analyse",
            "--input-dir",
            fixture_relpath,
            "--output-dir",
            output_relpath,
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )


def run_cli_review(
    workspace: Path,
    *,
    incident_relpath: str,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)
    return subprocess.run(
        [
            sys.executable,
            str(MIDSTACK_LOCAL),
            "review",
            "--incident-dir",
            incident_relpath,
            "--output-root",
            ".local/incidents",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )


def assert_incident_outputs(
    workspace: Path,
    incident_relpath: str,
    *,
    require_review: bool = True,
    text_token: Optional[str] = None,
) -> None:
    incident_dir = workspace / incident_relpath
    analysis_file = incident_dir / "analysis.yaml"
    reasoning_task_file = incident_dir / "agent-reasoning-task.md"
    rule_draft_file = incident_dir / "analysis.rule-draft.yaml"
    if not analysis_file.exists():
        raise AssertionError("missing analysis.yaml under %s" % incident_relpath)
    if not reasoning_task_file.exists():
        raise AssertionError("missing agent-reasoning-task.md under %s" % incident_relpath)
    if not rule_draft_file.exists():
        raise AssertionError("missing analysis.rule-draft.yaml under %s" % incident_relpath)
    reasoning_task_text = reasoning_task_file.read_text(encoding="utf-8")
    for expected in ("expected_gap", "critical_gap", "deepest_supported_level"):
        if expected not in reasoning_task_text:
            raise AssertionError("reasoning task missing token: %s" % expected)
    analysis = yaml.safe_load(analysis_file.read_text(encoding="utf-8")) or {}
    if require_review and "review" not in analysis:
        raise AssertionError("analysis.yaml missing review block")
    if text_token and text_token not in analysis_file.read_text(encoding="utf-8"):
        raise AssertionError("analysis.yaml missing token: %s" % text_token)
