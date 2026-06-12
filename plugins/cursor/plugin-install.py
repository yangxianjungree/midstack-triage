#!/usr/bin/env python3

"""Install Midstack Triage as a local Cursor plugin (official format, no Marketplace upload)."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAME = "midstack-triage"
LOCAL_PLUGIN_DIR = Path.home() / ".cursor" / "plugins" / "local" / PLUGIN_NAME
MANIFEST_PATH = PLUGIN_DIR / ".cursor-plugin" / "plugin.json"
WORKSPACE_STATE_NAME = "midstack-triage.workspace.json"
INSTALL_MODE = "agent-cli"
REQUIRED_COMMANDS = [
    "midstack:start.md",
    "midstack:analyse.md",
    "midstack:review.md",
    "midstack:validate.md",
]
LEGACY_COMMANDS = [
    "midstack-start.md",
    "midstack-analyse.md",
    "midstack-review.md",
    "midstack-validate.md",
]
LEGACY_RULE = "midstack-triage.mdc"


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


def plugin_version() -> str:
    if not MANIFEST_PATH.exists():
        return "0.0.0"
    return str(load_json(MANIFEST_PATH).get("version") or "0.0.0")


def engine_root_path() -> Path:
    return PLUGIN_DIR.resolve().parents[1]


def workspace_state_path(target_root: Path) -> Path:
    return target_root / ".cursor" / WORKSPACE_STATE_NAME


def plugin_command_source(name: str) -> Path:
    return PLUGIN_DIR / "commands" / name


def plugin_rule_source() -> Path:
    return PLUGIN_DIR / "rules" / LEGACY_RULE


def remove_path(path: Path) -> None:
    if path.is_file() or path.is_symlink():
        path.unlink()
    elif path.is_dir():
        for child in sorted(path.iterdir(), reverse=True):
            remove_path(child)
        path.rmdir()


def ensure_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    resolved_target = target.resolve()
    if link.is_symlink():
        if link.resolve() == resolved_target:
            return
        link.unlink()
    elif link.exists():
        remove_path(link)
    link.symlink_to(resolved_target)


def remove_legacy_command_names(command_dir: Path, target_root: Path) -> List[str]:
    removed: List[str] = []
    for name in LEGACY_COMMANDS:
        path = command_dir / name
        if path.exists():
            removed.append(str(path.relative_to(target_root)))
            remove_path(path)
    return removed


def project_workspace_slash_commands(target_root: Path) -> List[str]:
    projected: List[str] = []
    command_dir = target_root / ".cursor" / "commands"
    projected.extend(remove_legacy_command_names(command_dir, target_root))
    for name in REQUIRED_COMMANDS:
        link = command_dir / name
        ensure_symlink(link, plugin_command_source(name))
        projected.append(str(link.relative_to(target_root)))
    rule_link = target_root / ".cursor" / "rules" / LEGACY_RULE
    ensure_symlink(rule_link, plugin_rule_source())
    projected.append(str(rule_link.relative_to(target_root)))
    return projected


def check_projected_symlinks(target_root: Path) -> List[str]:
    errors: List[str] = []
    command_dir = target_root / ".cursor" / "commands"
    for name in LEGACY_COMMANDS:
        if (command_dir / name).exists():
            errors.append("legacy command name still present: .cursor/commands/%s" % name)
    for name in REQUIRED_COMMANDS:
        link = command_dir / name
        expected = plugin_command_source(name)
        if not link.is_symlink():
            errors.append("command must be a symlink to plugin: .cursor/commands/%s" % name)
        elif link.resolve() != expected.resolve():
            errors.append("command symlink drift: .cursor/commands/%s" % name)
    rule_link = target_root / ".cursor" / "rules" / LEGACY_RULE
    expected_rule = plugin_rule_source()
    if not rule_link.is_symlink():
        errors.append("rule must be a symlink to plugin: .cursor/rules/%s" % LEGACY_RULE)
    elif rule_link.resolve() != expected_rule.resolve():
        errors.append("rule symlink drift: .cursor/rules/%s" % LEGACY_RULE)
    return errors


def migrate_workspace(target_root: Path) -> Dict[str, Any]:
    target_root.mkdir(parents=True, exist_ok=True)
    agents_md = target_root / "AGENTS.md"
    if agents_md.exists():
        agents_md.unlink()

    projected = project_workspace_slash_commands(target_root)
    init_workspace(target_root)
    state = {
        "install_mode": INSTALL_MODE,
        "plugin_name": PLUGIN_NAME,
        "plugin_version": plugin_version(),
        "engine_root": str(engine_root_path()),
        "last_migrated_at": now_iso(),
        "projected_slash_commands": [p for p in projected if p.startswith(".cursor/commands/")],
    }
    write_json(workspace_state_path(target_root), state)
    return state


def init_workspace(target_root: Path) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    readme = target_root / "README.md"
    readme.write_text(
        "# Midstack Cursor Workspace\n\n"
        "Open this folder in Cursor or run Agent CLI from here.\n\n"
        "## Slash commands\n\n"
        "`.cursor/commands/midstack:*.md` are symlinks to the plugin — use `/midstack:start`, `/midstack:analyse`, etc.\n\n"
        "```bash\n"
        "cd %s\n"
        "agent --workspace .\n"
        "```\n\n"
        "- Install or upgrade:\n"
        "  `python3 %s/plugin-install.py --upgrade --workspace-init .`\n"
        "- `engine_root`: `.cursor/midstack-triage.workspace.json`\n"
        "- Incident outputs: `.local/incidents/`\n"
        % (target_root.resolve(), PLUGIN_DIR.resolve()),
        encoding="utf-8",
    )
    gitignore = target_root / ".gitignore"
    marker = "# Midstack Triage local runtime outputs"
    entry = "%s\n.local/\n" % marker
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if marker not in content and "\n.local/\n" not in ("\n" + content):
            suffix = "" if content.endswith("\n") else "\n"
            gitignore.write_text(content + suffix + "\n" + entry, encoding="utf-8")
    else:
        gitignore.write_text(entry, encoding="utf-8")


def check_manifest() -> List[str]:
    errors: List[str] = []
    if not MANIFEST_PATH.exists():
        return ["missing manifest: %s" % MANIFEST_PATH]
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("name") != PLUGIN_NAME:
        errors.append("manifest name must be %s" % PLUGIN_NAME)
    for name in REQUIRED_COMMANDS:
        if not plugin_command_source(name).exists():
            errors.append("missing command file: commands/%s" % name)
    if not plugin_rule_source().exists():
        errors.append("missing rule file: rules/%s" % LEGACY_RULE)
    return errors


def check_workspace(target_root: Path) -> List[str]:
    errors: List[str] = []
    errors.extend(check_projected_symlinks(target_root))
    state_path = workspace_state_path(target_root)
    if not state_path.exists():
        errors.append("missing workspace state: .cursor/%s" % WORKSPACE_STATE_NAME)
        return errors
    state = load_json(state_path)
    if state.get("install_mode") != INSTALL_MODE:
        errors.append("workspace install_mode must be %s" % INSTALL_MODE)
    if state.get("plugin_name") != PLUGIN_NAME:
        errors.append("workspace plugin_name mismatch")
    engine_root = str(state.get("engine_root") or "")
    if not engine_root or not Path(engine_root).exists():
        errors.append("workspace engine_root is missing or does not exist")
    elif Path(engine_root).resolve() != engine_root_path().resolve():
        errors.append("workspace engine_root does not match linked plugin engine")
    current_version = plugin_version()
    if str(state.get("plugin_version") or "") != current_version:
        errors.append(
            "workspace plugin_version is %s, expected %s — rerun with --upgrade"
            % (state.get("plugin_version"), current_version)
        )
    return errors


def link_plugin() -> Tuple[bool, str]:
    LOCAL_PLUGIN_DIR.parent.mkdir(parents=True, exist_ok=True)
    target = PLUGIN_DIR.resolve()
    if LOCAL_PLUGIN_DIR.is_symlink():
        if LOCAL_PLUGIN_DIR.resolve() == target:
            return True, str(LOCAL_PLUGIN_DIR)
        LOCAL_PLUGIN_DIR.unlink()
    elif LOCAL_PLUGIN_DIR.exists():
        return False, "refusing to replace non-symlink path: %s" % LOCAL_PLUGIN_DIR
    LOCAL_PLUGIN_DIR.symlink_to(target)
    return True, str(LOCAL_PLUGIN_DIR)


def check_link() -> List[str]:
    errors: List[str] = []
    if not LOCAL_PLUGIN_DIR.exists():
        errors.append("local plugin not linked: %s" % LOCAL_PLUGIN_DIR)
        return errors
    if not LOCAL_PLUGIN_DIR.is_symlink():
        errors.append("local plugin path is not a symlink: %s" % LOCAL_PLUGIN_DIR)
        return errors
    if LOCAL_PLUGIN_DIR.resolve() != PLUGIN_DIR.resolve():
        errors.append(
            "local plugin symlink points to %s, expected %s"
            % (LOCAL_PLUGIN_DIR.resolve(), PLUGIN_DIR.resolve())
        )
    linked_manifest = LOCAL_PLUGIN_DIR / ".cursor-plugin" / "plugin.json"
    if not linked_manifest.exists():
        errors.append("linked plugin is missing manifest at %s" % linked_manifest)
    elif str(load_json(linked_manifest).get("version") or "") != plugin_version():
        errors.append("linked plugin manifest version drifted from source")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Midstack Triage as a local Cursor plugin (not for Marketplace upload)."
    )
    parser.add_argument(
        "--workspace-init",
        metavar="DIR",
        help="Symlink plugin slash commands/rules into workspace .cursor/ and write workspace state.",
    )
    parser.add_argument(
        "--upgrade",
        action="store_true",
        help="Refresh local plugin symlink, migrate workspace, and update workspace state to current plugin version.",
    )
    parser.add_argument("--link", action="store_true", help="Symlink this plugin into ~/.cursor/plugins/local/.")
    parser.add_argument("--check-manifest", action="store_true", help="Verify official plugin manifest and bundled files.")
    parser.add_argument("--check-link", action="store_true", help="Verify ~/.cursor/plugins/local symlink.")
    parser.add_argument(
        "--check-workspace",
        metavar="DIR",
        help="Verify workspace slash-command symlinks and plugin version.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not any(
        [
            args.workspace_init,
            args.upgrade,
            args.link,
            args.check_manifest,
            args.check_link,
            args.check_workspace,
        ]
    ):
        print(
            "ERROR: specify at least one of --check-manifest, --link, --workspace-init, --upgrade, --check-workspace, --check-link",
            file=sys.stderr,
        )
        return 1

    if args.check_manifest or args.link or args.check_link or args.upgrade:
        manifest_errors = check_manifest()
        if manifest_errors:
            print("ERROR: plugin manifest check failed", file=sys.stderr)
            for item in manifest_errors:
                print("  - %s" % item, file=sys.stderr)
            return 1
        if args.check_manifest:
            print("ok: plugin manifest valid (version %s)" % plugin_version())

    if args.upgrade or args.link:
        ok, message = link_plugin()
        if not ok:
            print("ERROR: %s" % message, file=sys.stderr)
            return 1
        print("ok: linked local plugin at %s (version %s)" % (message, plugin_version()))

    if args.check_link:
        link_errors = check_link()
        if link_errors:
            print("ERROR: local plugin link check failed", file=sys.stderr)
            for item in link_errors:
                print("  - %s" % item, file=sys.stderr)
            return 1
        print("ok: local plugin link valid (version %s)" % plugin_version())

    workspace_dir = args.workspace_init
    if args.upgrade and not workspace_dir:
        print("ERROR: --upgrade requires --workspace-init DIR", file=sys.stderr)
        return 1

    if workspace_dir:
        workspace = Path(workspace_dir).expanduser().resolve()
        state = migrate_workspace(workspace)
        print(str(workspace))
        projected = state.get("projected_slash_commands") or []
        if projected:
            print("ok: slash commands linked:")
            for item in projected:
                print("  - %s" % item)
        print("ok: workspace state updated to plugin version %s" % state.get("plugin_version"))

    if args.check_workspace:
        workspace_errors = check_workspace(Path(args.check_workspace).expanduser().resolve())
        if workspace_errors:
            print("ERROR: workspace check failed", file=sys.stderr)
            for item in workspace_errors:
                print("  - %s" % item, file=sys.stderr)
            return 1
        print("ok: workspace valid for agent-cli mode (version %s)" % plugin_version())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
