#!/usr/bin/env python3

"""Install Midstack Triage as a local Claude Code plugin for a sandbox workspace."""

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


PLUGIN_NAME = "midstack"
MARKETPLACE_NAME = "midstack-triage-local"
WORKSPACE_STATE = "midstack-triage.workspace.json"
EXPECTED_COMMANDS = [
    "start",
    "analyse",
    "review",
    "validate",
]
LEGACY_SKILLS = [
    "midstack-start",
    "midstack-analyse",
    "midstack-review",
    "midstack-validate",
]
LEGACY_PLUGIN_IDS = [
    "midstack-triage@midstack-triage-local",
]

PLUGIN_DIR = Path(__file__).resolve().parent
ENGINE_ROOT = PLUGIN_DIR.parents[1]
MANIFEST_PATH = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
INSTALLED_PLUGINS_PATH = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
RUNTIME_MARKER_FILES = [
    "runtime/bin/midstack-local.py",
    "runtime/tools/plugin/midstack-local.py",
    "runtime/bin/selfcheck.py",
    "runtime/tools/remote-executor/mongodb-executor.py",
    "runtime/tools/analyse/mongodb-analyse.py",
    "runtime/tools/support/common.py",
    "runtime/src/commands/plugin_cli.py",
    "runtime/src/execution/__init__.py",
    "runtime/src/execution/remote/__init__.py",
    "runtime/src/execution/remote/access.py",
    "runtime/src/execution/remote/executor.py",
    "runtime/src/execution/remote/mongodb_collection_runtime.py",
    "runtime/src/phases/phase4/rules/__init__.py",
    "runtime/src/phases/phase4/rules/mongodb.py",
    "runtime/src/phases/phase4/rules/pulsar.py",
    "runtime/src/shared/__init__.py",
    "runtime/src/shared/patch_merge.py",
    "runtime/src/shared/scenario_router.py",
    "runtime/src/shared/skill_resolver.py",
    "runtime/src/shared/mongodb_collection_runtime.py",
    "runtime/domains/mongodb/scripts/manifest.yaml",
    "runtime/core/routing/scenario-signal-map.yaml",
    "runtime/interfaces/plugin/script-runtime-map.example.yaml",
]
RUNTIME_COPY_DIRS = [
    ("tools/plugin", "runtime/tools/plugin"),
    ("tools/analyse", "runtime/tools/analyse"),
    ("tools/support", "runtime/tools/support"),
    ("tools/validators", "runtime/tools/validators"),
    ("tools/remote-executor", "runtime/tools/remote-executor"),
    ("src", "runtime/src"),
    ("domains", "runtime/domains"),
    ("scenarios", "runtime/scenarios"),
    ("core", "runtime/core"),
    ("interfaces", "runtime/interfaces"),
]


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


def run(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def require_ok(cmd: List[str], cwd: Path) -> subprocess.CompletedProcess:
    proc = run(cmd, cwd)
    if proc.returncode != 0:
        if proc.stdout:
            print(proc.stdout, file=sys.stderr)
        if proc.stderr:
            print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    return proc


def require_json_output(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    proc = require_ok(cmd, cwd)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit("expected JSON output from `%s`: %s" % (" ".join(cmd), exc))
    if not isinstance(data, dict):
        raise SystemExit("expected JSON object from `%s`" % " ".join(cmd))
    return data


def plugin_version() -> str:
    return str(load_json(MANIFEST_PATH).get("version") or "0.0.0")


def workspace_marketplace_dir(workspace: Path) -> Path:
    return workspace / ".claude" / "marketplaces" / MARKETPLACE_NAME


def marketplace_plugin_dir(workspace: Path) -> Path:
    return workspace_marketplace_dir(workspace) / "plugins" / PLUGIN_NAME


def marketplace_manifest_path(workspace: Path) -> Path:
    return workspace_marketplace_dir(workspace) / ".claude-plugin" / "marketplace.json"


def validate_source_layout() -> None:
    errors: List[str] = []
    manifest = load_json(MANIFEST_PATH)
    manifest_commands = manifest.get("commands")

    if manifest_commands != "./commands":
        errors.append('plugin manifest commands must be "./commands"')

    if PLUGIN_DIR.joinpath("skills").exists():
        errors.append("plugins/claude/skills must not exist; use only commands/*.md")

    for name in EXPECTED_COMMANDS:
        if not PLUGIN_DIR.joinpath("commands", "%s.md" % name).exists():
            errors.append("missing required Claude command: commands/%s.md" % name)

    for marker in ("runtime/bin/midstack-local.py", "runtime/bin/validate-repo.py", "runtime/bin/selfcheck.py"):
        if not PLUGIN_DIR.joinpath(marker).exists():
            errors.append("missing required Claude runtime wrapper: %s" % marker)

    for name in LEGACY_SKILLS:
        if PLUGIN_DIR.joinpath("skills", name).exists():
            errors.append("legacy hyphen skill must not exist: skills/%s" % name)

    if errors:
        for item in errors:
            print("ERROR: %s" % item, file=sys.stderr)
        raise SystemExit(1)


def validate_source() -> None:
    validate_source_layout()
    require_ok(["claude", "plugin", "validate", str(PLUGIN_DIR)], ENGINE_ROOT)


def copy_plugin_source(target_plugin_dir: Path) -> None:
    if target_plugin_dir.exists():
        shutil.rmtree(target_plugin_dir)
    target_plugin_dir.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(PLUGIN_DIR, target_plugin_dir, ignore=ignore)


def copy_runtime_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    shutil.copytree(source, target, ignore=ignore)


def stage_runtime_bundle(target_plugin_dir: Path) -> None:
    for source_rel, target_rel in RUNTIME_COPY_DIRS:
        copy_runtime_tree(ENGINE_ROOT / source_rel, target_plugin_dir / target_rel)


def validate_runtime_bundle(target_plugin_dir: Path) -> None:
    errors: List[str] = []
    for marker in RUNTIME_MARKER_FILES:
        if not target_plugin_dir.joinpath(marker).exists():
            errors.append("missing bundled runtime file: %s" % marker)
    if errors:
        for item in errors:
            print("ERROR: %s" % item, file=sys.stderr)
        raise SystemExit(1)


def write_marketplace_manifest(workspace: Path) -> None:
    manifest = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": MARKETPLACE_NAME,
        "description": "Local marketplace for Midstack Triage Claude Code plugin development.",
        "owner": {
            "name": "Midstack Triage"
        },
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": "./plugins/%s" % PLUGIN_NAME,
                "description": "MongoDB middleware incident triage with Midstack local runtime.",
                "version": plugin_version(),
                "license": "MIT",
                "keywords": ["mongodb", "triage", "incident", "middleware"],
            }
        ],
    }
    write_json(marketplace_manifest_path(workspace), manifest)


def build_marketplace(workspace: Path) -> Path:
    marketplace_dir = workspace_marketplace_dir(workspace)
    plugin_dir = marketplace_plugin_dir(workspace)
    validate_source()
    copy_plugin_source(plugin_dir)
    stage_runtime_bundle(plugin_dir)
    validate_runtime_bundle(plugin_dir)
    selfcheck = require_json_output([sys.executable, str(plugin_dir / "runtime" / "bin" / "selfcheck.py")], workspace)
    if selfcheck.get("status") != "passed":
        print("ERROR: bundled runtime selfcheck failed", file=sys.stderr)
        for item in selfcheck.get("errors") or []:
            print("  - %s" % item, file=sys.stderr)
        raise SystemExit(1)
    write_marketplace_manifest(workspace)
    require_ok(["claude", "plugin", "validate", str(marketplace_dir)], ENGINE_ROOT)
    return marketplace_dir


def write_workspace_state(workspace: Path) -> None:
    state = {
        "plugin_name": PLUGIN_NAME,
        "plugin_version": plugin_version(),
        "install_mode": "claude-local-marketplace-bundled-runtime",
        "runtime_mode": "bundled-plugin",
        "marketplace": MARKETPLACE_NAME,
        "marketplace_dir": str(workspace_marketplace_dir(workspace)),
        "output_root": ".local/incidents",
        "last_installed_at": now_iso(),
    }
    write_json(workspace / ".claude" / WORKSPACE_STATE, state)
    gitignore = workspace / ".gitignore"
    marker = "# Midstack Triage local runtime outputs"
    entry = "%s\n.local/\n" % marker
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if marker not in content and "\n.local/\n" not in ("\n" + content):
            suffix = "" if content.endswith("\n") else "\n"
            gitignore.write_text(content + suffix + "\n" + entry, encoding="utf-8")
    else:
        gitignore.write_text(entry, encoding="utf-8")


def remove_path(path: Path) -> None:
    if path.is_file() or path.is_symlink():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)


def cleanup_legacy_workspace_projection(workspace: Path) -> List[str]:
    """Remove earlier non-plugin Claude projections from the target workspace."""
    removed: List[str] = []
    legacy_manifest = workspace / ".claude-plugin"
    if legacy_manifest.exists():
        remove_path(legacy_manifest)
        removed.append(".claude-plugin/")

    legacy_skills = workspace / ".claude" / "skills"
    if legacy_skills.exists():
        for child in sorted(legacy_skills.glob("midstack*")):
            remove_path(child)
            removed.append(str(child.relative_to(workspace)))

    return removed


def purge_project_state(workspace: Path) -> None:
    proc = run(["claude", "project", "purge", "-y", str(workspace)], ENGINE_ROOT)
    combined = "\n".join(part for part in [proc.stdout, proc.stderr] if part).strip()
    if proc.returncode == 0:
        return
    if "No Claude Code project state found" in combined:
        return
    if proc.stdout:
        print(proc.stdout, file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    raise SystemExit(proc.returncode)


def uninstall_legacy_plugins(workspace: Path) -> List[str]:
    removed: List[str] = []
    for plugin_id in LEGACY_PLUGIN_IDS:
        uninstall = run(["claude", "plugin", "uninstall", plugin_id, "--scope", "local"], workspace)
        if uninstall.returncode == 0:
            removed.append(plugin_id)
    return removed


def ensure_marketplace(workspace: Path) -> None:
    marketplace_dir = workspace_marketplace_dir(workspace)
    remove = run(["claude", "plugin", "marketplace", "remove", MARKETPLACE_NAME, "--scope", "local"], workspace)
    if remove.returncode != 0:
        pass
    require_ok(
        [
            "claude",
            "plugin",
            "marketplace",
            "add",
            str(marketplace_dir),
            "--scope",
            "local",
        ],
        workspace,
    )


def install_plugin(workspace: Path) -> None:
    plugin_id = "%s@%s" % (PLUGIN_NAME, MARKETPLACE_NAME)
    update = run(["claude", "plugin", "update", plugin_id, "--scope", "local"], workspace)
    if update.returncode == 0:
        return

    require_ok(["claude", "plugin", "install", plugin_id, "--scope", "local"], workspace)


def installed_plugin_record(plugin_id: str, workspace: Path) -> Dict[str, Any]:
    if not INSTALLED_PLUGINS_PATH.exists():
        return {}
    data = load_json(INSTALLED_PLUGINS_PATH)
    plugins = data.get("plugins") or {}
    records = plugins.get(plugin_id) or []
    for item in records:
        if not isinstance(item, dict):
            continue
        if str(item.get("scope") or "") != "local":
            continue
        if Path(str(item.get("projectPath") or "")).resolve() == workspace.resolve():
            return item
    return {}


def check_install(workspace: Path) -> List[str]:
    errors: List[str] = []
    plugin_id = "%s@%s" % (PLUGIN_NAME, MARKETPLACE_NAME)
    state_path = workspace / ".claude" / WORKSPACE_STATE
    if not state_path.exists():
        errors.append("missing workspace state: .claude/%s" % WORKSPACE_STATE)
    else:
        state = load_json(state_path)
        if str(state.get("plugin_version") or "") != plugin_version():
            errors.append("workspace plugin version is stale")
        for legacy_key in ("engine_root", "plugin_source"):
            if legacy_key in state:
                errors.append("workspace state still contains legacy repo dependency field: %s" % legacy_key)
        expected_marketplace_dir = workspace_marketplace_dir(workspace)
        if Path(str(state.get("marketplace_dir") or "")).resolve() != expected_marketplace_dir.resolve():
            errors.append("workspace marketplace_dir is stale")

    validate = run(["claude", "plugin", "validate", str(PLUGIN_DIR)], ENGINE_ROOT)
    if validate.returncode != 0:
        errors.append("source plugin validation failed")

    listing = run(["claude", "plugin", "list"], workspace)
    if listing.returncode != 0:
        errors.append("claude plugin list failed")
    elif plugin_id not in listing.stdout:
        errors.append("plugin is not installed in Claude: %s" % plugin_id)
    else:
        for legacy_plugin_id in LEGACY_PLUGIN_IDS:
            if legacy_plugin_id in listing.stdout:
                errors.append("legacy plugin install is still present in Claude: %s" % legacy_plugin_id)

    details = run(["claude", "plugin", "details", plugin_id], workspace)
    if details.returncode != 0:
        errors.append("claude plugin details failed")
    else:
        for command_name in ["start", "analyse", "review", "validate"]:
            if command_name not in details.stdout:
                errors.append("plugin command is not visible to Claude: /%s" % command_name)
        for legacy_name in ["midstack-start", "midstack-analyse", "midstack-review", "midstack-validate"]:
            if legacy_name in details.stdout:
                errors.append("legacy hyphen skill is still visible to Claude: /%s" % legacy_name)
        if "midstack-triage:" in details.stdout:
            errors.append("legacy plugin namespace leaked into Claude slash commands")
        if "midstack:" in details.stdout:
            errors.append("command names must remain short command ids under plugin name midstack")

    record = installed_plugin_record(plugin_id, workspace)
    if not record:
        errors.append("installed plugin metadata is missing from ~/.claude/plugins/installed_plugins.json")
        return errors

    install_path = Path(str(record.get("installPath") or ""))
    if not install_path.exists():
        errors.append("installed plugin path does not exist: %s" % install_path)
        return errors

    for marker in RUNTIME_MARKER_FILES:
        if not install_path.joinpath(marker).exists():
            errors.append("installed plugin is missing bundled runtime file: %s" % marker)

    for command_name in EXPECTED_COMMANDS:
        command_path = install_path / "commands" / ("%s.md" % command_name)
        if not command_path.exists():
            errors.append("installed plugin command file is missing: %s" % command_path)
            continue
        text = command_path.read_text(encoding="utf-8")
        if "${CLAUDE_PLUGIN_ROOT}" not in text:
            errors.append("installed command does not use CLAUDE_PLUGIN_ROOT: %s" % command_path.name)
        if "midstack-triage.workspace.json" in text or "engine_root" in text:
            errors.append("installed command still depends on workspace engine_root state: %s" % command_path.name)

    selfcheck_path = install_path / "runtime" / "bin" / "selfcheck.py"
    if not selfcheck_path.exists():
        errors.append("installed plugin selfcheck entrypoint is missing: %s" % selfcheck_path)
    else:
        selfcheck = run([sys.executable, str(selfcheck_path)], workspace)
        if selfcheck.returncode != 0:
            errors.append("installed plugin selfcheck failed")
        try:
            selfcheck_payload = json.loads(selfcheck.stdout or "{}")
        except json.JSONDecodeError:
            errors.append("installed plugin selfcheck did not emit valid JSON")
            selfcheck_payload = {}
        if isinstance(selfcheck_payload, dict):
            if bool(selfcheck_payload.get("dependency_boundary", {}).get("source_repo_required")):
                errors.append("installed plugin selfcheck reports an unexpected source repo dependency")
            for item in selfcheck_payload.get("errors") or []:
                errors.append("installed plugin selfcheck: %s" % item)

    marketplace_info = run(["claude", "plugin", "marketplace", "list"], workspace)
    if marketplace_info.returncode != 0:
        errors.append("claude plugin marketplace list failed")
    else:
        expected_dir = str(workspace_marketplace_dir(workspace))
        if expected_dir not in marketplace_info.stdout:
            errors.append("workspace marketplace is not rooted under sandbox: %s" % expected_dir)
        if str(ENGINE_ROOT / ".local" / "claude-marketplace") in marketplace_info.stdout:
            errors.append("legacy repo-local marketplace is still configured for this workspace")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the Midstack Claude plugin into a sandbox workspace.")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ["build-marketplace", "check"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--workspace", required=True, help="Target Claude workspace, e.g. /home/stephen/AI/midstack-cursor-sandbox")

    install = sub.add_parser("install")
    install.add_argument("--workspace", required=True, help="Target Claude workspace, e.g. /home/stephen/AI/midstack-cursor-sandbox")
    install.add_argument(
        "--keep-project-state",
        action="store_true",
        help="Skip `claude project purge` and keep Claude transcripts/history for the target workspace.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    if args.command == "build-marketplace":
        marketplace_dir = build_marketplace(workspace)
        print("ok: built local marketplace at %s" % marketplace_dir)
        return 0

    if args.command == "install":
        marketplace_dir = build_marketplace(workspace)
        if not args.keep_project_state:
            purge_project_state(workspace)
        removed = cleanup_legacy_workspace_projection(workspace)
        removed_plugins = uninstall_legacy_plugins(workspace)
        write_workspace_state(workspace)
        ensure_marketplace(workspace)
        install_plugin(workspace)
        errors = check_install(workspace)
        if errors:
            print("ERROR: Claude plugin install check failed", file=sys.stderr)
            for item in errors:
                print("  - %s" % item, file=sys.stderr)
            return 1
        if not args.keep_project_state:
            print("ok: purged Claude project state for %s" % workspace)
            print("note: old Claude resume sessions for this workspace were deleted")
        print("ok: installed %s@%s for %s" % (PLUGIN_NAME, MARKETPLACE_NAME, workspace))
        print("ok: sandbox marketplace rooted at %s" % marketplace_dir)
        if removed_plugins:
            print("ok: removed legacy Claude plugins:")
            for item in removed_plugins:
                print("  - %s" % item)
        if removed:
            print("ok: removed legacy workspace projection:")
            for item in removed:
                print("  - %s" % item)
        return 0

    if args.command == "check":
        errors = check_install(workspace)
        if errors:
            print("ERROR: Claude plugin install check failed", file=sys.stderr)
            for item in errors:
                print("  - %s" % item, file=sys.stderr)
            return 1
        print("ok: Claude plugin installed (%s@%s)" % (PLUGIN_NAME, MARKETPLACE_NAME))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
