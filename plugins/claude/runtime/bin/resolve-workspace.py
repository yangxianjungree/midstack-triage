#!/usr/bin/env python3

import json
import os
from pathlib import Path


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def env_workspace(plugin_root: Path) -> Path | None:
    for name in ("CLAUDE_PROJECT_DIR", "CLAUDE_WORKSPACE", "CLAUDE_CWD", "INIT_CWD"):
        value = os.environ.get(name)
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists() and not is_under(candidate, plugin_root):
            return candidate
    return None


def installed_plugin_workspace(plugin_root: Path) -> Path | None:
    installed = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not installed.exists():
        return None
    try:
        data = json.loads(installed.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    plugins = data.get("plugins") or {}
    for records in plugins.values():
        if not isinstance(records, list):
            continue
        for item in records:
            if not isinstance(item, dict):
                continue
            install_path = item.get("installPath")
            project_path = item.get("projectPath")
            if not install_path or not project_path:
                continue
            if Path(install_path).expanduser().resolve() == plugin_root:
                candidate = Path(project_path).expanduser().resolve()
                if candidate.exists():
                    return candidate
    return None


def main() -> int:
    plugin_root_value = os.environ.get("CLAUDE_PLUGIN_ROOT")
    plugin_root = Path(plugin_root_value).expanduser().resolve() if plugin_root_value else Path(__file__).resolve().parents[2]
    workspace = env_workspace(plugin_root) or installed_plugin_workspace(plugin_root)
    if workspace is None:
        cwd = Path.cwd().resolve()
        workspace = cwd if not is_under(cwd, plugin_root) else plugin_root
    print(workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
