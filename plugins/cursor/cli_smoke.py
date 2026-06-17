#!/usr/bin/env python3

"""Shared helpers for Cursor agent-cli integration smoke tests."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import yaml


ROOT = Path(__file__).resolve().parents[2]
PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_INSTALL = PLUGIN_DIR / "plugin-install.py"
COMMAND_FILES = [
    "midstack:start.md",
    "midstack:analyse.md",
    "midstack:review.md",
    "midstack:validate.md",
]


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def workspace_runtime_root(workspace: Path) -> Path:
    state_path = workspace / ".cursor" / "midstack-triage.workspace.json"
    data = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
    runtime_root = Path(str(data.get("runtime_root") or ""))
    if not runtime_root.exists():
        raise AssertionError("workspace runtime_root is missing or does not exist: %s" % runtime_root)
    return runtime_root


def workspace_midstack_local(workspace: Path) -> Path:
    return workspace_runtime_root(workspace) / "bin" / "midstack-local.py"


def workspace_validate_repo(workspace: Path) -> Path:
    return workspace_runtime_root(workspace) / "bin" / "validate-repo.py"


def stage_fixture(workspace: Path, fixture_relpath: str) -> Path:
    source = ROOT / fixture_relpath
    if not source.exists():
        raise AssertionError("missing source fixture for smoke: %s" % source)
    target = workspace / ".local" / "cursor-smoke-fixtures" / Path(fixture_relpath).name
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    return target.relative_to(workspace)


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
    forbidden_tokens = [
        "engine_root",
        "source-checkout",
        "cd \"/abs/path/to/midstack-triage\"",
        "/abs/path/to/midstack-triage/tests/fixtures",
        "python3 tools/plugin/midstack-local.py",
    ]
    for name in COMMAND_FILES:
        path = PLUGIN_DIR / "commands" / name
        text = path.read_text(encoding="utf-8")
        if "runtime_root" not in text:
            errors.append("%s must reference runtime_root workspace state" % name)
        if name == "midstack:validate.md":
            if "validate-repo.py" not in text:
                errors.append("%s must reference validate-repo.py" % name)
        elif "midstack-local.py" not in text:
            errors.append("%s must reference midstack-local.py" % name)
        else:
            if "MIDSTACK_TRIAGE_WORKSPACE" not in text:
                errors.append("%s must export MIDSTACK_TRIAGE_WORKSPACE" % name)
        if "Agent CLI + shell" not in text:
            errors.append("%s must declare Agent CLI + shell usage" % name)
        if "${CLAUDE_PLUGIN_ROOT}" in text:
            errors.append("%s must not reference Claude bundled-runtime paths" % name)
        for token in forbidden_tokens:
            if token in text:
                errors.append("%s must not contain installed-runtime forbidden token: %s" % (name, token))
    rule = (PLUGIN_DIR / "rules" / "midstack-triage.mdc").read_text(encoding="utf-8")
    if "midstack-local.py" not in rule:
        errors.append("rules must reference midstack-local.py")
    if "runtime_root" not in rule:
        errors.append("rules must reference runtime_root workspace state")
    for token in forbidden_tokens:
        if token in rule:
            errors.append("rules must not contain installed-runtime forbidden token: %s" % token)
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
    workspace_fixture = stage_fixture(workspace, fixture_relpath)
    return subprocess.run(
        [
            sys.executable,
            str(workspace_midstack_local(workspace)),
            "analyse",
            "--input-dir",
            str(workspace_fixture),
            "--output-dir",
            output_relpath,
        ],
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )


def run_cli_analyse_current_incident(
    workspace: Path,
    *,
    incident_relpath: str,
    timeout: int = 120,
) -> subprocess.CompletedProcess:
    incident_dir = workspace / incident_relpath
    output_root = incident_dir.parent
    tmp_bin = workspace / ".local" / "cursor-smoke-bin"
    fake_sshpass = tmp_bin / "sshpass"
    output_root.mkdir(parents=True, exist_ok=True)
    tmp_bin.mkdir(parents=True, exist_ok=True)
    (output_root / ".current-incident").write_text(str(incident_dir) + "\n", encoding="utf-8")
    write_yaml(
        incident_dir / "input.yaml",
        {
            "incident_id": incident_dir.name,
            "middleware": "mongodb",
            "namespace": "psmdb-test",
            "cluster_id": "",
            "customer_clue": "current incident smoke",
            "scenario": "unknown",
        },
    )
    write_yaml(
        incident_dir / "meta.yaml",
        {
            "incident_id": incident_dir.name,
            "middleware": "mongodb",
            "status": "ready",
            "current_command": "start",
        },
    )
    write_yaml(
        incident_dir / "remote-config.yaml",
        {
            "name": "%s-remote" % incident_dir.name,
            "purpose": "cursor current incident smoke",
            "access": {
                "candidate_ips": ["192.0.2.10"],
                "primary_ip": "192.0.2.10",
                "username": "root",
                "password": "secret",
                "port": 22,
            },
        },
    )
    fake_sshpass.write_text(
        "#!/bin/sh\n"
        "echo 'ssh: connect to host 192.0.2.10 port 22: Connection refused' >&2\n"
        "exit 255\n",
        encoding="utf-8",
    )
    fake_sshpass.chmod(0o755)

    env = os.environ.copy()
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)
    env["PATH"] = str(tmp_bin) + os.pathsep + env.get("PATH", "")
    return subprocess.run(
        [
            sys.executable,
            str(workspace_midstack_local(workspace)),
            "analyse",
            "--output-root",
            ".local/incidents",
        ],
        cwd=str(workspace),
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
            str(workspace_midstack_local(workspace)),
            "review",
            "--incident-dir",
            incident_relpath,
            "--output-root",
            ".local/incidents",
        ],
        cwd=str(workspace),
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
    rules_fallback_file = incident_dir / "analysis.rules-fallback.yaml"
    legacy_rule_draft_file = incident_dir / "analysis.rule-draft.yaml"
    if not analysis_file.exists():
        raise AssertionError("missing analysis.yaml under %s" % incident_relpath)
    if not reasoning_task_file.exists():
        raise AssertionError("missing agent-reasoning-task.md under %s" % incident_relpath)
    if not rules_fallback_file.exists() and not legacy_rule_draft_file.exists():
        raise AssertionError("missing analysis.rules-fallback.yaml under %s" % incident_relpath)
    reasoning_task_text = reasoning_task_file.read_text(encoding="utf-8")
    for expected in ("expected_gap", "critical_gap", "deepest_supported_level"):
        if expected not in reasoning_task_text:
            raise AssertionError("reasoning task missing token: %s" % expected)
    analysis = yaml.safe_load(analysis_file.read_text(encoding="utf-8")) or {}
    if require_review and "review" not in analysis:
        raise AssertionError("analysis.yaml missing review block")
    if text_token and text_token not in analysis_file.read_text(encoding="utf-8"):
        raise AssertionError("analysis.yaml missing token: %s" % text_token)


def assert_current_incident_blocked_without_traceback(workspace: Path, incident_relpath: str, proc: subprocess.CompletedProcess) -> None:
    combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part)
    if proc.returncode != 0:
        raise AssertionError(combined.strip() or "current incident analyse failed")
    if "Traceback" in combined:
        raise AssertionError("current incident analyse raised traceback: %s" % combined)
    if "/home/stephen/AI/domains/" in combined:
        raise AssertionError("current incident analyse used sibling directory as repo root: %s" % combined)
    if "/home/stephen/AI/midstack-triage/tools/plugin/midstack-local.py" in combined:
        raise AssertionError("current incident analyse used source-checkout plugin CLI: %s" % combined)

    incident_dir = workspace / incident_relpath
    adapter_path = incident_dir / "adapter-output.yaml"
    if not adapter_path.exists():
        raise AssertionError("missing adapter-output.yaml under %s" % incident_relpath)
    adapter_text = adapter_path.read_text(encoding="utf-8")
    if "status: blocked" not in adapter_text:
        raise AssertionError("current incident smoke did not produce blocked adapter output")
    if "ssh_unreachable" not in adapter_text:
        raise AssertionError("current incident smoke did not report ssh_unreachable")
    if not (incident_dir / "remote-executor-run.yaml").exists():
        raise AssertionError("current incident smoke did not persist remote-executor-run.yaml")
