"""Shared install helpers for agent plugin adapters."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


RUNTIME_SOURCE_DIRS: Tuple[str, ...] = (
    "tools/plugin",
    "tools/support",
    "tools/validators",
    "src",
    "domains",
    "scenarios",
    "core",
    "interfaces",
)
LICENSE_FILES: Tuple[str, ...] = ("LICENSE", "NOTICE")
LOCAL_OUTPUTS_GITIGNORE_MARKER = "# Midstack Triage local runtime outputs"
COMMON_RUNTIME_MARKER_FILES: Tuple[str, ...] = (
    "tools/plugin/midstack-local.py",
    "tools/support/common.py",
    "src/commands/plugin_cli.py",
    "src/execution/__init__.py",
    "src/execution/remote/__init__.py",
    "src/execution/remote/access.py",
    "src/execution/remote/capabilities.py",
    "src/execution/remote/cli.py",
    "src/execution/remote/error_contract.py",
    "src/execution/remote/executor.py",
    "src/execution/remote/executor_preflight.py",
    "src/execution/remote/kubectl.py",
    "src/execution/remote/mongodb_collection_runtime.py",
    "src/execution/remote/runtime_support.py",
    "src/execution/remote/script_capabilities.py",
    "src/execution/remote/script_output_contract.py",
    "src/execution/remote/script_runner.py",
    "src/execution/remote/transport.py",
    "src/phases/phase4/rules/__init__.py",
    "src/phases/phase4/rules/common.py",
    "src/phases/phase4/rules/mongodb.py",
    "src/phases/phase4/rules/pulsar.py",
    "src/shared/__init__.py",
    "src/shared/asset_resolver.py",
    "src/shared/io.py",
    "src/shared/patch_merge.py",
    "src/shared/scenario_router.py",
    "src/shared/skill_resolver.py",
    "src/shared/workspace.py",
    "domains/mongodb/scripts/manifest.yaml",
    "core/routing/scenario-signal-map.yaml",
    "interfaces/plugin/script-runtime-map.example.yaml",
)


@dataclass(frozen=True)
class RuntimeBundleLayout:
    """Runtime payload layout for one agent adapter."""

    root_prefix: str = ""

    def copy_dirs(self) -> List[Tuple[str, str]]:
        prefix = self.root_prefix.strip("/")
        result: List[Tuple[str, str]] = []
        for source in RUNTIME_SOURCE_DIRS:
            target = "%s/%s" % (prefix, source) if prefix else source
            result.append((source, target))
        return result


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> Dict[str, Any]:
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


def remove_path(path: Path) -> None:
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        remove_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(source, target, ignore=ignore)


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_license_files(source_root: Path, target_dir: Path, names: Sequence[str] = LICENSE_FILES) -> None:
    for name in names:
        copy_file(source_root / name, target_dir / name)


def stage_runtime_dirs(source_root: Path, target_root: Path, copy_dirs: Iterable[Tuple[str, str]]) -> None:
    for source_rel, target_rel in copy_dirs:
        copy_tree(source_root / source_rel, target_root / target_rel)


def prefixed_runtime_markers(prefix: str = "") -> Tuple[str, ...]:
    normalized = prefix.strip("/")
    if not normalized:
        return COMMON_RUNTIME_MARKER_FILES
    return tuple("%s/%s" % (normalized, marker) for marker in COMMON_RUNTIME_MARKER_FILES)


def missing_markers(root: Path, markers: Iterable[str]) -> List[str]:
    return [marker for marker in markers if not root.joinpath(marker).exists()]


def ensure_local_outputs_gitignore(workspace: Path) -> None:
    gitignore = workspace / ".gitignore"
    entry = "%s\n.local/\n" % LOCAL_OUTPUTS_GITIGNORE_MARKER
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if LOCAL_OUTPUTS_GITIGNORE_MARKER not in content and "\n.local/\n" not in ("\n" + content):
            suffix = "" if content.endswith("\n") else "\n"
            gitignore.write_text(content + suffix + "\n" + entry, encoding="utf-8")
    else:
        gitignore.write_text(entry, encoding="utf-8")
