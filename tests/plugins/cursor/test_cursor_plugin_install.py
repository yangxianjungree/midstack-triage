import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from install_contracts import (
    assert_analyse_command_runtime_first_contract,
    assert_cli_command_options_documented,
    assert_cursor_files_use_workspace_runtime,
    assert_no_common_source_checkout_contract,
    assert_review_and_validate_not_main_path,
    assert_slash_command_surface_doc,
    assert_start_command_ready_message_table,
    assert_start_command_uses_runtime_first_hop,
)


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = ROOT / "plugins" / "cursor"
PLUGIN_INSTALL = PLUGIN_DIR / "plugin-install.py"
from commands import plugin_cli


def test_command_contracts_use_agent_cli_shell():
    sys.path.insert(0, str(PLUGIN_DIR))
    from cli_smoke import assert_command_contracts

    assert_command_contracts()
    files = list((PLUGIN_DIR / "commands").glob("midstack:*.md")) + [PLUGIN_DIR / "rules" / "midstack-triage.mdc"]
    assert_no_common_source_checkout_contract(files)
    assert_cursor_files_use_workspace_runtime(files)
    assert_analyse_command_runtime_first_contract(PLUGIN_DIR / "commands" / "midstack:analyse.md")
    assert_start_command_uses_runtime_first_hop(PLUGIN_DIR / "commands" / "midstack:start.md")
    assert_start_command_ready_message_table(PLUGIN_DIR / "commands" / "midstack:start.md")
    assert_review_and_validate_not_main_path((PLUGIN_DIR / "commands").glob("midstack:*.md"))


def test_slash_command_surface_documents_phase_mapping():
    assert_slash_command_surface_doc(ROOT / "docs" / "project" / "slash-command-surface.md")


def test_cursor_command_docs_track_cli_arguments():
    assert_cli_command_options_documented(
        {
            "start": PLUGIN_DIR / "commands" / "midstack:start.md",
            "analyse": PLUGIN_DIR / "commands" / "midstack:analyse.md",
            "review": PLUGIN_DIR / "commands" / "midstack:review.md",
            "finalize-analysis": PLUGIN_DIR / "commands" / "midstack:analyse.md",
        },
        plugin_cli,
    )


def test_plugin_manifest_check_passes():
    proc = subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), "--check-manifest"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert (PLUGIN_DIR / "LICENSE").read_text(encoding="utf-8") == (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (PLUGIN_DIR / "NOTICE").read_text(encoding="utf-8") == (ROOT / "NOTICE").read_text(encoding="utf-8")


def test_workspace_init_projects_slash_commands_and_runtime(tmp_path):
    cursor = tmp_path / ".cursor"
    commands = cursor / "commands"
    rules = cursor / "rules"
    commands.mkdir(parents=True)
    rules.mkdir(parents=True)
    (commands / "midstack:start.md").write_text("stale copy", encoding="utf-8")
    (rules / "midstack-triage.mdc").write_text("stale copy", encoding="utf-8")

    migrate = subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), "--workspace-init", str(tmp_path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert migrate.returncode == 0, migrate.stderr or migrate.stdout

    start_command = commands / "midstack:start.md"
    rule_file = rules / "midstack-triage.mdc"
    assert start_command.exists()
    assert rule_file.exists()
    assert not start_command.is_symlink()
    assert not rule_file.is_symlink()
    assert start_command.read_text(encoding="utf-8") == (PLUGIN_DIR / "commands" / "midstack:start.md").read_text(
        encoding="utf-8"
    )
    assert rule_file.read_text(encoding="utf-8") == (PLUGIN_DIR / "rules" / "midstack-triage.mdc").read_text(
        encoding="utf-8"
    )
    assert "midstack-triage-runtime/bin/midstack-local.py" in start_command.read_text(encoding="utf-8")
    assert "engine_root" not in start_command.read_text(encoding="utf-8")
    assert "source-checkout" not in rule_file.read_text(encoding="utf-8")

    state = json.loads((cursor / "midstack-triage.workspace.json").read_text(encoding="utf-8"))
    assert state["install_mode"] == "agent-cli-bundled-runtime"
    assert "engine_root" not in state
    runtime_root = Path(state["runtime_root"])
    assert runtime_root == cursor / "midstack-triage-runtime"
    assert (runtime_root / "bin" / "midstack-local.py").exists()
    assert (runtime_root / "bin" / "validate-repo.py").exists()
    assert (runtime_root / "domains" / "mongodb" / "scripts" / "manifest.yaml").exists()
    assert (runtime_root / "src" / "commands" / "plugin_cli.py").exists()
    assert not (tmp_path / "AGENTS.md").exists()

    check = subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), "--check-workspace", str(tmp_path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert check.returncode == 0, check.stderr or check.stdout
