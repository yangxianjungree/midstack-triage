#!/usr/bin/env python3

"""Self-check for the Cursor workspace-local runtime bundle."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(os.environ.get("MIDSTACK_TRIAGE_WORKSPACE") or Path.cwd()).resolve()
STATE_PATH = WORKSPACE_ROOT / ".cursor" / "midstack-triage.workspace.json"
REQUIRED_MARKERS = (
    "bin/midstack-local.py",
    "bin/selfcheck.py",
    "tools/plugin/midstack-local.py",
    "tools/support/common.py",
    "tools/validators/validate-repo.py",
    "src/commands/plugin_cli.py",
    "src/phases/phase4/rules/mongodb.py",
    "src/shared/workspace.py",
    "domains/mongodb/scripts/manifest.yaml",
    "core/routing/scenario-signal-map.yaml",
    "core/interfaces/plugin/script-runtime-map.example.yaml",
)


def _load_state(errors: list[str]) -> dict:
    if not STATE_PATH.exists():
        errors.append("missing Cursor workspace state: %s" % STATE_PATH)
        return {}
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append("invalid Cursor workspace state JSON: %s" % exc)
        return {}
    if not isinstance(data, dict):
        errors.append("Cursor workspace state must be a JSON object")
        return {}
    return data


def _check_python(errors: list[str]) -> None:
    if sys.version_info < (3, 10):
        errors.append("Python 3.10+ is required, got %s" % ".".join(str(part) for part in sys.version_info[:3]))
    try:
        import yaml  # noqa: F401
    except ImportError:
        errors.append("PyYAML is required for the installed runtime")


def _check_markers(errors: list[str]) -> None:
    for marker in REQUIRED_MARKERS:
        if not (RUNTIME_ROOT / marker).exists():
            errors.append("missing runtime marker: %s" % marker)


def _check_workspace_state(state: dict, errors: list[str]) -> None:
    if state.get("install_mode") != "agent-cli-bundled-runtime":
        errors.append("workspace install_mode must be agent-cli-bundled-runtime")
    if "engine_root" in state:
        errors.append("workspace state must not contain deprecated engine_root")
    runtime_root = Path(str(state.get("runtime_root") or "")).expanduser()
    if not runtime_root:
        errors.append("workspace runtime_root is missing")
    elif runtime_root.resolve() != RUNTIME_ROOT.resolve():
        errors.append("workspace runtime_root does not match installed runtime: %s" % runtime_root)


def main() -> int:
    errors: list[str] = []
    _check_python(errors)
    _check_markers(errors)
    state = _load_state(errors)
    if state:
        _check_workspace_state(state, errors)
    payload = {
        "status": "failed" if errors else "passed",
        "runtime_root": str(RUNTIME_ROOT),
        "workspace_root": str(WORKSPACE_ROOT),
        "dependency_boundary": {"source_repo_required": False},
        "errors": errors,
    }
    print(json.dumps(payload, indent=2, sort_keys=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
