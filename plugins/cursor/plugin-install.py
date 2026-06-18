#!/usr/bin/env python3

"""Install Midstack Triage as a local Cursor plugin (official format, no Marketplace upload)."""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SUPPORT_DIR = Path(__file__).resolve().parents[1] / "support"
if str(SUPPORT_DIR) not in sys.path:
    sys.path.insert(0, str(SUPPORT_DIR))

from install_common import (  # noqa: E402
    LICENSE_FILES,
    RuntimeBundleLayout,
    copy_file,
    copy_tree,
    ensure_local_outputs_gitignore,
    load_json,
    missing_markers,
    now_iso,
    prefixed_runtime_markers,
    remove_path,
    stage_runtime_dirs,
    write_json,
)

PLUGIN_DIR = Path(__file__).resolve().parent
PLUGIN_NAME = "midstack-triage"
LOCAL_PLUGIN_DIR = Path.home() / ".cursor" / "plugins" / "local" / PLUGIN_NAME
MANIFEST_PATH = PLUGIN_DIR / ".cursor-plugin" / "plugin.json"
WORKSPACE_STATE_NAME = "midstack-triage.workspace.json"
INSTALL_MODE = "agent-cli-bundled-runtime"
WORKSPACE_RUNTIME_DIR = "midstack-triage-runtime"
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
RUNTIME_COPY_DIRS = RuntimeBundleLayout().copy_dirs()
RUNTIME_MARKER_FILES = [
    "bin/midstack-local.py",
    "bin/validate-repo.py",
] + list(prefixed_runtime_markers())
RUNTIME_FORBIDDEN_TEXT = [
    "Cursor source-checkout",
    "workspace `engine_root`",
    "workspace state `engine_root`",
    "engine_root` 调用",
    "source-checkout adapter",
]


# -----------------------------------------------------------------------------
# Path helpers


def plugin_version() -> str:
    if not MANIFEST_PATH.exists():
        return "0.0.0"
    return str(load_json(MANIFEST_PATH).get("version") or "0.0.0")


def source_root_path() -> Path:
    return PLUGIN_DIR.resolve().parents[1]


def license_source(name: str) -> Path:
    return source_root_path() / name


def workspace_state_path(target_root: Path) -> Path:
    return target_root / ".cursor" / WORKSPACE_STATE_NAME


def workspace_runtime_dir(target_root: Path) -> Path:
    return target_root / ".cursor" / WORKSPACE_RUNTIME_DIR


def plugin_command_source(name: str) -> Path:
    return PLUGIN_DIR / "commands" / name


def plugin_rule_source() -> Path:
    return PLUGIN_DIR / "rules" / LEGACY_RULE


# -----------------------------------------------------------------------------
# Filesystem projection helpers


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


# -----------------------------------------------------------------------------
# Workspace runtime staging


def write_runtime_wrapper(path: Path, tool_relpath: str) -> None:
    path.write_text(
        "#!/usr/bin/env python3\n\n"
        "import os\n"
        "import runpy\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "RUNTIME_ROOT = Path(__file__).resolve().parents[1]\n"
        "os.environ.setdefault(\"MIDSTACK_TRIAGE_RUNTIME_ROOT\", str(RUNTIME_ROOT))\n"
        "sys.path.insert(0, str(RUNTIME_ROOT / \"src\"))\n"
        "runpy.run_path(str(RUNTIME_ROOT / \"%s\"), run_name=\"__main__\")\n" % tool_relpath,
        encoding="utf-8",
    )


def write_runtime_wrappers(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    write_runtime_wrapper(bin_dir / "midstack-local.py", "tools/plugin/midstack-local.py")
    write_runtime_wrapper(bin_dir / "validate-repo.py", "tools/validators/validate-repo.py")
    for path in sorted(bin_dir.glob("*.py")):
        path.chmod(0o755)


def stage_workspace_runtime(target_root: Path) -> Path:
    runtime_dir = workspace_runtime_dir(target_root)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    stage_runtime_dirs(source_root_path(), runtime_dir, RUNTIME_COPY_DIRS)
    write_runtime_wrappers(runtime_dir / "bin")
    return runtime_dir


def validate_workspace_runtime(target_root: Path) -> List[str]:
    errors: List[str] = []
    runtime_dir = workspace_runtime_dir(target_root)
    for marker in missing_markers(runtime_dir, RUNTIME_MARKER_FILES):
        errors.append("missing workspace runtime file: .cursor/%s/%s" % (WORKSPACE_RUNTIME_DIR, marker))
    for relpath in [
        "tools/plugin/README.md",
        "tools/validators/README.md",
        "tools/validators/validate-repo.py",
    ]:
        path = runtime_dir / relpath
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for token in RUNTIME_FORBIDDEN_TEXT:
            if token in text:
                errors.append("workspace runtime file contains deprecated Cursor source dependency text: %s" % relpath)
                break
    return errors


# -----------------------------------------------------------------------------
# Workspace command and rule projection


def project_workspace_slash_commands(target_root: Path) -> List[str]:
    projected: List[str] = []
    command_dir = target_root / ".cursor" / "commands"
    projected.extend(remove_legacy_command_names(command_dir, target_root))
    for name in REQUIRED_COMMANDS:
        target = command_dir / name
        if target.exists() or target.is_symlink():
            remove_path(target)
        copy_file(plugin_command_source(name), target)
        projected.append(str(target.relative_to(target_root)))
    rule_target = target_root / ".cursor" / "rules" / LEGACY_RULE
    if rule_target.exists() or rule_target.is_symlink():
        remove_path(rule_target)
    copy_file(plugin_rule_source(), rule_target)
    projected.append(str(rule_target.relative_to(target_root)))
    return projected


def check_projected_files(target_root: Path) -> List[str]:
    errors: List[str] = []
    command_dir = target_root / ".cursor" / "commands"
    for name in LEGACY_COMMANDS:
        if (command_dir / name).exists():
            errors.append("legacy command name still present: .cursor/commands/%s" % name)
    for name in REQUIRED_COMMANDS:
        path = command_dir / name
        expected = plugin_command_source(name)
        if path.is_symlink():
            errors.append("command must be copied into workspace, not symlinked: .cursor/commands/%s" % name)
        elif not path.exists():
            errors.append("missing projected command: .cursor/commands/%s" % name)
        elif path.read_text(encoding="utf-8") != expected.read_text(encoding="utf-8"):
            errors.append("command projection drift: .cursor/commands/%s" % name)
    rule_path = target_root / ".cursor" / "rules" / LEGACY_RULE
    expected_rule = plugin_rule_source()
    if rule_path.is_symlink():
        errors.append("rule must be copied into workspace, not symlinked: .cursor/rules/%s" % LEGACY_RULE)
    elif not rule_path.exists():
        errors.append("missing projected rule: .cursor/rules/%s" % LEGACY_RULE)
    elif rule_path.read_text(encoding="utf-8") != expected_rule.read_text(encoding="utf-8"):
        errors.append("rule projection drift: .cursor/rules/%s" % LEGACY_RULE)
    return errors


# -----------------------------------------------------------------------------
# Workspace migration and checks


def migrate_workspace(target_root: Path) -> Dict[str, Any]:
    target_root.mkdir(parents=True, exist_ok=True)
    agents_md = target_root / "AGENTS.md"
    if agents_md.exists():
        agents_md.unlink()

    runtime_dir = stage_workspace_runtime(target_root)
    projected = project_workspace_slash_commands(target_root)
    init_workspace(target_root)
    state = {
        "install_mode": INSTALL_MODE,
        "plugin_name": PLUGIN_NAME,
        "plugin_version": plugin_version(),
        "runtime_root": str(runtime_dir),
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
        "`.cursor/commands/midstack:*.md` are workspace-local command files — use `/midstack:start`, `/midstack:analyse`, etc.\n\n"
        "```bash\n"
        "cd %s\n"
        "agent --workspace .\n"
        "```\n\n"
        "- Install or upgrade:\n"
        "  `python3 %s/plugin-install.py --upgrade --workspace-init .`\n"
        "- `runtime_root`: `.cursor/midstack-triage.workspace.json`\n"
        "- Incident outputs: `.local/incidents/`\n"
        % (target_root.resolve(), PLUGIN_DIR.resolve()),
        encoding="utf-8",
    )
    ensure_local_outputs_gitignore(target_root)


def check_manifest() -> List[str]:
    errors: List[str] = []
    if not MANIFEST_PATH.exists():
        return ["missing manifest: %s" % MANIFEST_PATH]
    manifest = load_json(MANIFEST_PATH)
    if manifest.get("name") != PLUGIN_NAME:
        errors.append("manifest name must be %s" % PLUGIN_NAME)
    if manifest.get("license") != "Apache-2.0":
        errors.append("manifest license must be Apache-2.0")
    for name in REQUIRED_COMMANDS:
        if not plugin_command_source(name).exists():
            errors.append("missing command file: commands/%s" % name)
    if not plugin_rule_source().exists():
        errors.append("missing rule file: rules/%s" % LEGACY_RULE)
    for name in LICENSE_FILES:
        path = PLUGIN_DIR / name
        source = license_source(name)
        if not path.exists():
            errors.append("missing license projection: %s" % path.relative_to(PLUGIN_DIR))
        elif source.exists() and path.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
            errors.append("license projection drifted from root: %s" % path.relative_to(PLUGIN_DIR))
    return errors


def check_workspace_state(target_root: Path) -> List[str]:
    errors: List[str] = []
    state_path = workspace_state_path(target_root)
    if not state_path.exists():
        errors.append("missing workspace state: .cursor/%s" % WORKSPACE_STATE_NAME)
        return errors
    state = load_json(state_path)
    if state.get("install_mode") != INSTALL_MODE:
        errors.append("workspace install_mode must be %s" % INSTALL_MODE)
    if state.get("plugin_name") != PLUGIN_NAME:
        errors.append("workspace plugin_name mismatch")
    if "engine_root" in state:
        errors.append("workspace state must not contain deprecated field: engine_root")
    runtime_root = str(state.get("runtime_root") or "")
    if not runtime_root or not Path(runtime_root).exists():
        errors.append("workspace runtime_root is missing or does not exist")
    elif Path(runtime_root).resolve() != workspace_runtime_dir(target_root).resolve():
        errors.append("workspace runtime_root does not match workspace runtime")
    current_version = plugin_version()
    if str(state.get("plugin_version") or "") != current_version:
        errors.append(
            "workspace plugin_version is %s, expected %s — rerun with --upgrade"
            % (state.get("plugin_version"), current_version)
        )
    return errors


def check_workspace(target_root: Path) -> List[str]:
    errors: List[str] = []
    errors.extend(check_projected_files(target_root))
    errors.extend(validate_workspace_runtime(target_root))
    errors.extend(check_workspace_state(target_root))
    return errors


# -----------------------------------------------------------------------------
# Local plugin link


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


# -----------------------------------------------------------------------------
# CLI entrypoints


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Midstack Triage as a local Cursor plugin (not for Marketplace upload)."
    )
    parser.add_argument(
        "--workspace-init",
        metavar="DIR",
        help="Copy slash commands/rules and bundled runtime into workspace .cursor/, then write workspace state.",
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
        help="Verify workspace slash-command projections, bundled runtime, and plugin version.",
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
            print("ok: slash commands projected:")
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
        print("ok: workspace valid for agent-cli bundled-runtime mode (version %s)" % plugin_version())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
