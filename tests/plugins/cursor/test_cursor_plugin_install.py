import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_DIR = ROOT / "plugins" / "cursor"
PLUGIN_INSTALL = PLUGIN_DIR / "plugin-install.py"


def test_command_contracts_use_agent_cli_shell():
    sys.path.insert(0, str(PLUGIN_DIR))
    from cli_smoke import assert_command_contracts

    assert_command_contracts()


def test_plugin_manifest_check_passes():
    proc = subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), "--check-manifest"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout


def test_workspace_init_links_slash_commands(tmp_path):
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

    start_link = commands / "midstack:start.md"
    rule_link = rules / "midstack-triage.mdc"
    assert start_link.is_symlink()
    assert rule_link.is_symlink()
    assert start_link.resolve() == (PLUGIN_DIR / "commands" / "midstack:start.md").resolve()
    assert rule_link.resolve() == (PLUGIN_DIR / "rules" / "midstack-triage.mdc").resolve()
    assert "midstack-local.py" in start_link.read_text(encoding="utf-8")

    state = json.loads((cursor / "midstack-triage.workspace.json").read_text(encoding="utf-8"))
    assert state["install_mode"] == "agent-cli"
    assert Path(state["engine_root"]).exists()
    assert not (tmp_path / "AGENTS.md").exists()

    check = subprocess.run(
        [sys.executable, str(PLUGIN_INSTALL), "--check-workspace", str(tmp_path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert check.returncode == 0, check.stderr or check.stdout
