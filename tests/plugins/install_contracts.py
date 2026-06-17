from pathlib import Path
from typing import Iterable, List


COMMON_FORBIDDEN_TOKENS = [
    "/home/stephen/AI/midstack-triage",
    "/home/stephen/AI/midstack-sandbox",
    "cd <source-checkout>",
    "source-checkout adapter",
    "python3 tools/plugin/midstack-local.py",
]


START_COMMAND_FIRST_HOP_TOKENS = [
    "First hop",
    "first shell command must call",
    "midstack-local.py",
    "Do not call repository source-tree `tools/plugin/midstack-local.py`",
    "runtime implementation details",
]


ANALYSE_COMMAND_CONTRACT_TOKENS = [
    *START_COMMAND_FIRST_HOP_TOKENS,
    "Do not create or edit `analysis.yaml` before",
    "If `analyse` returns `blocked`, summarize `blocking_items` and stop",
    "Do not print passwords or tokens",
]


def read_texts(paths: Iterable[Path]) -> List[tuple[Path, str]]:
    return [(path, path.read_text(encoding="utf-8")) for path in sorted(paths)]


def normalize_space(text: str) -> str:
    return " ".join(text.split())


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


def assert_start_command_uses_runtime_first_hop(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    errors = [token for token in START_COMMAND_FIRST_HOP_TOKENS if token not in text]
    if errors:
        raise AssertionError("%s is missing runtime first-hop contract tokens: %s" % (path, ", ".join(errors)))


def assert_start_command_ready_next_step(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "next run /midstack:analyse" not in text:
        raise AssertionError("%s must state the exact ready follow-up: next run /midstack:analyse" % path)


def assert_analyse_command_runtime_first_contract(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    errors = [token for token in ANALYSE_COMMAND_CONTRACT_TOKENS if token not in text]
    if errors:
        raise AssertionError("%s is missing analyse runtime-first contract tokens: %s" % (path, ", ".join(errors)))


def assert_review_and_validate_not_main_path(paths: Iterable[Path]) -> None:
    errors: List[str] = []
    for path, text in read_texts(paths):
        normalized = normalize_space(text.replace("`", ""))
        if path.name.endswith("review.md") or path.name.endswith("validate.md"):
            if (
                "not part of the /midstack:start -> /midstack:analyse main path" not in normalized
                and "not part of the user triage path" not in normalized
            ):
                errors.append("%s must state review/validate is not part of the main user triage path" % path.name)
    if errors:
        raise AssertionError("; ".join(errors))


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
