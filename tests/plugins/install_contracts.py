from pathlib import Path
from typing import Iterable, List


COMMON_FORBIDDEN_TOKENS = [
    "/home/stephen/AI/midstack-triage",
    "/home/stephen/AI/midstack-sandbox",
    "cd <source-checkout>",
    "source-checkout adapter",
    "python3 tools/plugin/midstack-local.py",
]


START_COMMAND_FORBIDDEN_ACTIONS = [
    "run raw `ssh`",
    "run raw `sshpass`",
    "run raw `kubectl`",
    "run `mongosh`",
    "run `pip",
]


def read_texts(paths: Iterable[Path]) -> List[tuple[Path, str]]:
    return [(path, path.read_text(encoding="utf-8")) for path in sorted(paths)]


def assert_no_common_source_checkout_contract(paths: Iterable[Path]) -> None:
    errors: List[str] = []
    for path, text in read_texts(paths):
        for token in COMMON_FORBIDDEN_TOKENS:
            if token in text:
                errors.append("%s must not contain source checkout token: %s" % (path, token))
    if errors:
        raise AssertionError("; ".join(errors))


def assert_claude_commands_use_bundled_runtime(command_dir: Path) -> None:
    errors: List[str] = []
    for path, text in read_texts(command_dir.glob("*.md")):
        if "${CLAUDE_PLUGIN_ROOT}" not in text:
            errors.append("%s must use CLAUDE_PLUGIN_ROOT" % path.name)
        if path.name != "validate.md" and "resolve-workspace.py" not in text:
            errors.append("%s must resolve the installed Claude workspace" % path.name)
        if "engine_root" in text or "midstack-triage.workspace.json" in text:
            errors.append("%s must not use historical workspace engine_root state" % path.name)
    if errors:
        raise AssertionError("; ".join(errors))


def assert_cursor_files_use_workspace_runtime(paths: Iterable[Path]) -> None:
    errors: List[str] = []
    for path, text in read_texts(paths):
        if "${CLAUDE_PLUGIN_ROOT}" in text:
            errors.append("%s must not reference Claude runtime paths" % path.name)
        if "runtime_root" not in text:
            errors.append("%s must reference Cursor workspace runtime_root" % path.name)
        if "engine_root" in text or "source-checkout" in text:
            errors.append("%s must not reference historical source checkout state" % path.name)
    if errors:
        raise AssertionError("; ".join(errors))


def assert_start_command_blocks_agent_first_hop_tools(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    errors = [token for token in START_COMMAND_FORBIDDEN_ACTIONS if token not in text]
    if errors:
        raise AssertionError("%s is missing first-hop tool guardrails: %s" % (path, ", ".join(errors)))


def assert_slash_command_surface_doc(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    required_tokens = [
        "Slash Command Surface",
        "/midstack:start",
        "/midstack:analyse",
        "/midstack:review",
        "/midstack:validate",
        "Phase 1",
        "Phase 2",
        "Phase 3",
        "Phase 4",
        "Phase 5",
    ]
    errors = [token for token in required_tokens if token not in text]
    if errors:
        raise AssertionError("%s is missing slash surface tokens: %s" % (path, ", ".join(errors)))
