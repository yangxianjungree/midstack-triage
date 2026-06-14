#!/usr/bin/env python3

import re
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_TOOL_DIRS = {
    "generators",
    "importers",
    "plugin",
    "replay",
    "support",
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
    "tools/generators/generate-asset.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from generators.asset_generator.core import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "KIND_CONFIG",
        ],
    },
    "tools/importers/import-runbook.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from importers.markdown_importer.core import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "VALID_RISK_LEVELS",
            "KIND_CONFIG",
        ],
    },
    "tools/replay/mongodb-freeze-fixture.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from replay.mongodb.freeze_fixture import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "shutil",
            "yaml",
            "json",
            "def parse_args",
            "FIXTURE_FILES",
        ],
    },
    "tools/replay/mongodb-replay.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from replay.mongodb.replay import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "REQUIRED_FILES",
        ],
    },
    "tools/replay/mongodb-score.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from replay.mongodb.score import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "DIMENSIONS",
        ],
    },
    "tools/replay/mongodb-score-summary.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from replay.mongodb.score_summary import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "DIMENSIONS",
        ],
    },
    "tools/replay/pulsar-replay.py": {
        "max_lines": 20,
        "required": [
            'TOOLS_DIR = Path(__file__).resolve().parents[1]',
            "from replay.pulsar.replay import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "REQUIRED_FILES",
        ],
    },
    "tools/validators/validate-mongodb-scripts.py": {
        "max_lines": 20,
        "required": [
            "from mongodb_assets.cli import main",
            "raise SystemExit(main())",
        ],
        "forbidden": [
            "argparse",
            "yaml",
            "json",
            "def parse_args",
            "REQUIRED_MANIFEST_FIELDS",
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

    for name in sorted(actual_dirs):
        readme = tools_dir / name / "README.md"
        if not readme.exists():
            errors.append("missing tools README: %s" % readme)
    return errors


def validate_removed_compat_layers(root: Path) -> List[str]:
    legacy_dir = root / "tools" / "lib"
    if legacy_dir.exists():
        return ["legacy compatibility layer must stay removed: %s" % legacy_dir]
    return []


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


def validate_removed_compat_paths(root: Path) -> List[str]:
    errors: List[str] = []
    for relative_path in (
        root / "tools" / "remote-executor",
        root / "tools" / "remote-smoke",
        root / "tests" / "replay",
        root / "tests" / "tools" / "analyse",
    ):
        if relative_path.exists():
            errors.append("obsolete compatibility path must stay removed: %s" % relative_path)
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
    errors.extend(validate_removed_compat_layers(ROOT))
    errors.extend(validate_removed_compat_paths(ROOT))
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
