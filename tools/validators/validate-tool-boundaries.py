#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TOOL_DIRS = {
    "analyse",
    "generators",
    "importers",
    "lib",
    "plugin",
    "remote-executor",
    "remote-smoke",
    "replay",
    "validators",
}
THIN_WRAPPER_SPECS = {
    "tools/plugin/midstack-local.py": {
        "max_lines": 25,
        "required": [
            'SRC_DIR = Path(__file__).resolve().parents[2] / "src"',
            "from commands.plugin_cli import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "tempfile",
            "shutil",
            "def parse_args",
        ],
    },
    "tools/analyse/mongodb-analyse.py": {
        "max_lines": 25,
        "required": [
            'SRC_DIR = Path(__file__).resolve().parents[2] / "src"',
            "from phases.phase4.rules.mongodb import *",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/analyse/pulsar-analyse.py": {
        "max_lines": 25,
        "required": [
            'SRC_DIR = Path(__file__).resolve().parents[2] / "src"',
            "from phases.phase4.rules.pulsar import *",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/remote-executor/mongodb-executor.py": {
        "max_lines": 25,
        "required": [
            'SRC_DIR = Path(__file__).resolve().parents[2] / "src"',
            "from execution.remote.executor import *",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/remote-smoke/mongodb-smoke.py": {
        "max_lines": 30,
        "required": [
            'SRC_DIR = ROOT / "src"',
            "from execution.remote.executor import main as executor_main",
            "return executor_main()",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/lib/mongodb_collection_runtime.py": {
        "max_lines": 20,
        "required": [
            'SRC_DIR = ROOT / "src"',
            "from execution.remote.mongodb_collection_runtime import *",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/lib/patch_merge.py": {
        "max_lines": 20,
        "required": [
            'SRC_DIR = ROOT / "src"',
            "from shared.patch_merge import *",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/lib/scenario_router.py": {
        "max_lines": 20,
        "required": [
            'SRC_DIR = ROOT / "src"',
            "from shared.scenario_router import *",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
    "tools/lib/skill_resolver.py": {
        "max_lines": 20,
        "required": [
            'SRC_DIR = ROOT / "src"',
            "from shared.skill_resolver import *",
        ],
        "forbidden": [
            "argparse",
            "subprocess",
            "yaml",
            "json",
            "def parse_args",
        ],
    },
}
SRC_TOOLS_IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+tools\b", re.MULTILINE)


def validate_tool_directories(root: Path) -> List[str]:
    errors: List[str] = []
    tools_dir = root / "tools"
    if not tools_dir.exists():
        return ["missing tools/ directory: %s" % tools_dir]

    actual_dirs = {path.name for path in tools_dir.iterdir() if path.is_dir()}
    missing_dirs = sorted(REQUIRED_TOOL_DIRS - actual_dirs)
    if missing_dirs:
        errors.append("tools/ missing required subdirectories: %s" % missing_dirs)

    for name in sorted(actual_dirs & REQUIRED_TOOL_DIRS):
        readme = tools_dir / name / "README.md"
        if not readme.exists():
            errors.append("missing tools README: %s" % readme)
    return errors


def validate_wrapper_script(path: Path, spec: Dict[str, object]) -> List[str]:
    errors: List[str] = []
    if not path.exists():
        return ["missing thin wrapper script: %s" % path]

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    max_lines = int(spec["max_lines"])
    if len(lines) > max_lines:
        errors.append("%s must stay thin: %d lines > %d" % (path, len(lines), max_lines))

    for needle in spec["required"]:
        if str(needle) not in text:
            errors.append("%s missing required wrapper marker: %s" % (path, needle))

    for needle in spec["forbidden"]:
        if str(needle) in text:
            errors.append("%s contains forbidden thick-wrapper marker: %s" % (path, needle))

    return errors


def validate_wrapper_scripts(root: Path) -> List[str]:
    errors: List[str] = []
    for relative_path, spec in THIN_WRAPPER_SPECS.items():
        errors.extend(validate_wrapper_script(root / relative_path, spec))
    return errors


def validate_src_import_boundary(root: Path) -> List[str]:
    errors: List[str] = []
    src_dir = root / "src"
    if not src_dir.exists():
        return ["missing src/ directory: %s" % src_dir]

    for path in sorted(src_dir.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if SRC_TOOLS_IMPORT_PATTERN.search(text):
            errors.append("src runtime must not import tools/: %s" % path)
    return errors


def main() -> int:
    errors: List[str] = []
    errors.extend(validate_tool_directories(ROOT))
    errors.extend(validate_wrapper_scripts(ROOT))
    errors.extend(validate_src_import_boundary(ROOT))

    if errors:
        for error in errors:
            print("ERROR: %s" % error, file=sys.stderr)
        return 1

    print("Tool boundary validation passed: %d thin wrappers and %d tool directories checked" % (
        len(THIN_WRAPPER_SPECS),
        len(REQUIRED_TOOL_DIRS),
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
