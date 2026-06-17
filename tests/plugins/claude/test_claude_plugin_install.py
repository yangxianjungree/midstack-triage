import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
PLUGIN_INSTALL_PATH = ROOT / "plugins" / "claude" / "plugin-install.py"


def load_claude_plugin_install():
    spec = importlib.util.spec_from_file_location("claude_plugin_install", PLUGIN_INSTALL_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_install_purges_claude_project_state_by_default(tmp_path, monkeypatch, capsys):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    calls = []

    monkeypatch.setattr(module, "build_marketplace", lambda target: calls.append(("build", target)) or (target / ".claude" / "marketplaces" / module.MARKETPLACE_NAME))
    monkeypatch.setattr(module, "purge_project_state", lambda target: calls.append(("purge", target)))
    monkeypatch.setattr(module, "cleanup_legacy_workspace_projection", lambda target: calls.append(("cleanup", target)) or [])
    monkeypatch.setattr(module, "uninstall_legacy_plugins", lambda target: calls.append(("uninstall_legacy_plugins", target)) or [])
    monkeypatch.setattr(module, "write_workspace_state", lambda target: calls.append(("write_state", target)))
    monkeypatch.setattr(module, "ensure_marketplace", lambda target: calls.append(("ensure_marketplace", target)))
    monkeypatch.setattr(module, "install_plugin", lambda target: calls.append(("install_plugin", target)))
    monkeypatch.setattr(module, "check_install", lambda target: calls.append(("check_install", target)) or [])
    monkeypatch.setattr(
        sys,
        "argv",
        [str(PLUGIN_INSTALL_PATH), "install", "--workspace", str(workspace)],
    )

    assert module.main() == 0
    assert calls == [
        ("build", workspace),
        ("purge", workspace),
        ("cleanup", workspace),
        ("uninstall_legacy_plugins", workspace),
        ("write_state", workspace),
        ("ensure_marketplace", workspace),
        ("install_plugin", workspace),
        ("check_install", workspace),
    ]

    output = capsys.readouterr().out
    assert "ok: purged Claude project state" in output
    assert "old Claude resume sessions for this workspace were deleted" in output


def test_install_can_keep_claude_project_state(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    calls = []

    monkeypatch.setattr(module, "build_marketplace", lambda target: calls.append(("build", target)) or (target / ".claude" / "marketplaces" / module.MARKETPLACE_NAME))
    monkeypatch.setattr(module, "purge_project_state", lambda target: calls.append(("purge", target)))
    monkeypatch.setattr(module, "cleanup_legacy_workspace_projection", lambda target: calls.append(("cleanup", target)) or [])
    monkeypatch.setattr(module, "uninstall_legacy_plugins", lambda target: calls.append(("uninstall_legacy_plugins", target)) or [])
    monkeypatch.setattr(module, "write_workspace_state", lambda target: calls.append(("write_state", target)))
    monkeypatch.setattr(module, "ensure_marketplace", lambda target: calls.append(("ensure_marketplace", target)))
    monkeypatch.setattr(module, "install_plugin", lambda target: calls.append(("install_plugin", target)))
    monkeypatch.setattr(module, "check_install", lambda target: calls.append(("check_install", target)) or [])
    monkeypatch.setattr(
        sys,
        "argv",
        [str(PLUGIN_INSTALL_PATH), "install", "--workspace", str(workspace), "--keep-project-state"],
    )

    assert module.main() == 0
    assert ("purge", workspace) not in calls
    assert calls == [
        ("build", workspace),
        ("cleanup", workspace),
        ("uninstall_legacy_plugins", workspace),
        ("write_state", workspace),
        ("ensure_marketplace", workspace),
        ("install_plugin", workspace),
        ("check_install", workspace),
    ]


def test_install_fails_when_post_install_check_fails(tmp_path, monkeypatch, capsys):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()

    monkeypatch.setattr(module, "build_marketplace", lambda target: target / ".claude" / "marketplaces" / module.MARKETPLACE_NAME)
    monkeypatch.setattr(module, "purge_project_state", lambda target: None)
    monkeypatch.setattr(module, "cleanup_legacy_workspace_projection", lambda target: [])
    monkeypatch.setattr(module, "uninstall_legacy_plugins", lambda target: [])
    monkeypatch.setattr(module, "write_workspace_state", lambda target: None)
    monkeypatch.setattr(module, "ensure_marketplace", lambda target: None)
    monkeypatch.setattr(module, "install_plugin", lambda target: None)
    monkeypatch.setattr(module, "check_install", lambda target: ["plugin command is not visible to Claude: /start"])
    monkeypatch.setattr(
        sys,
        "argv",
        [str(PLUGIN_INSTALL_PATH), "install", "--workspace", str(workspace)],
    )

    assert module.main() == 1
    error = capsys.readouterr().err
    assert "ERROR: Claude plugin install check failed" in error
    assert "/start" in error


def test_build_marketplace_runs_bundled_runtime_selfcheck(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    calls = []

    monkeypatch.setattr(module, "validate_source", lambda: calls.append("validate_source"))
    monkeypatch.setattr(module, "copy_plugin_source", lambda target: calls.append(("copy_plugin_source", target)))
    monkeypatch.setattr(module, "stage_runtime_bundle", lambda target: calls.append(("stage_runtime_bundle", target)))
    monkeypatch.setattr(module, "validate_runtime_bundle", lambda target: calls.append(("validate_runtime_bundle", target)))
    monkeypatch.setattr(module, "write_marketplace_manifest", lambda target: calls.append(("write_marketplace_manifest", target)))
    monkeypatch.setattr(module, "require_ok", lambda cmd, cwd: calls.append(("require_ok", cmd, cwd)))
    monkeypatch.setattr(
        module,
        "require_json_output",
        lambda cmd, cwd: calls.append(("require_json_output", cmd, cwd)) or {"status": "passed", "errors": []},
    )

    marketplace_dir = module.build_marketplace(workspace)

    assert marketplace_dir == module.workspace_marketplace_dir(workspace)
    plugin_dir = module.marketplace_plugin_dir(workspace)
    assert calls == [
        "validate_source",
        ("copy_plugin_source", plugin_dir),
        ("stage_runtime_bundle", plugin_dir),
        ("validate_runtime_bundle", plugin_dir),
        ("require_json_output", [sys.executable, str(plugin_dir / "runtime" / "bin" / "selfcheck.py")], workspace),
        ("write_marketplace_manifest", workspace),
        ("require_ok", ["claude", "plugin", "validate", str(module.workspace_marketplace_dir(workspace))], module.ENGINE_ROOT),
    ]


def test_runtime_markers_do_not_include_removed_remote_shims():
    module = load_claude_plugin_install()
    assert "runtime/tools/remote-executor/mongodb-executor.py" not in module.RUNTIME_MARKER_FILES
    assert all("remote-executor" not in item for item in module.RUNTIME_COPY_DIRS)


def test_claude_start_command_contract_forces_bundled_runtime_first():
    text = (ROOT / "plugins" / "claude" / "commands" / "start.md").read_text(encoding="utf-8")

    required = [
        "First action",
        "Bash",
        "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py",
        "Do not claim the incident was started",
        "adapter-output.yaml",
        "Do not run `mongosh`",
        "Do not run `pip",
        "Do not run raw `ssh`",
        "Do not run raw `kubectl`",
    ]
    for token in required:
        assert token in text


def test_claude_command_contracts_do_not_depend_on_source_checkout():
    command_dir = ROOT / "plugins" / "claude" / "commands"
    for path in command_dir.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        assert "${CLAUDE_PLUGIN_ROOT}" in text
        if path.name != "validate.md":
            assert "resolve-workspace.py" in text
            assert 'MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"' not in text
        if path.name in ("start.md", "analyse.md"):
            assert "Do not print passwords or tokens" in text
        assert "engine_root" not in text
        assert "cd /home/stephen/AI/midstack-triage" not in text
        assert "tools/plugin/midstack-local.py" not in text


def test_resolve_workspace_uses_installed_plugin_project_path(tmp_path, monkeypatch):
    plugin_root = tmp_path / "cache" / "midstack"
    workspace = tmp_path / "sandbox"
    home = tmp_path / "home"
    installed = home / ".claude" / "plugins" / "installed_plugins.json"
    resolver = ROOT / "plugins" / "claude" / "runtime" / "bin" / "resolve-workspace.py"

    plugin_root.mkdir(parents=True)
    workspace.mkdir()
    installed.parent.mkdir(parents=True)
    installed.write_text(
        json.dumps(
            {
                "plugins": {
                    "midstack@midstack-triage-local": [
                        {
                            "scope": "local",
                            "installPath": str(plugin_root),
                            "projectPath": str(workspace),
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env.pop("CLAUDE_PROJECT_DIR", None)
    proc = subprocess.run(
        [sys.executable, str(resolver)],
        cwd=str(plugin_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == str(workspace.resolve())


def test_check_install_reports_installed_plugin_selfcheck_errors(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    plugin_id = "%s@%s" % (module.PLUGIN_NAME, module.MARKETPLACE_NAME)
    install_path = (tmp_path / "install").resolve()
    commands_dir = install_path / "commands"
    runtime_bin = install_path / "runtime" / "bin"
    commands_dir.mkdir(parents=True)
    runtime_bin.mkdir(parents=True)

    for name in module.EXPECTED_COMMANDS:
        (commands_dir / ("%s.md" % name)).write_text(
            'Use ${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py\\n',
            encoding="utf-8",
        )
    for marker in module.RUNTIME_MARKER_FILES:
        path = install_path / marker
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
    (runtime_bin / "selfcheck.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    workspace_state = workspace / ".claude" / module.WORKSPACE_STATE
    workspace_state.parent.mkdir(parents=True, exist_ok=True)
    workspace_state.write_text(
        json.dumps(
            {
                "plugin_version": module.plugin_version(),
                "marketplace_dir": str(module.workspace_marketplace_dir(workspace)),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "installed_plugin_record", lambda pid, target: {"installPath": str(install_path)} if pid == plugin_id else {})

    class Proc:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, cwd):
        if cmd[:3] == ["claude", "plugin", "validate"]:
            return Proc(0, "ok")
        if cmd[:3] == ["claude", "plugin", "list"]:
            return Proc(0, plugin_id)
        if cmd[:3] == ["claude", "plugin", "details"]:
            return Proc(0, "Skills (4)  analyse, review, start, validate")
        if cmd[:4] == ["claude", "plugin", "marketplace", "list"]:
            return Proc(0, str(module.workspace_marketplace_dir(workspace)))
        if cmd[0] == sys.executable and cmd[1] == str(runtime_bin / "selfcheck.py"):
            return Proc(
                1,
                json.dumps(
                    {
                        "dependency_boundary": {"source_repo_required": False},
                        "errors": ["missing required local command: sshpass"],
                    }
                ),
            )
        raise AssertionError("unexpected command: %r" % (cmd,))

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "run_installed_runtime_smoke", lambda wrapper, target: [])

    errors = module.check_install(workspace)

    assert "installed plugin selfcheck failed" in errors
    assert "installed plugin selfcheck: missing required local command: sshpass" in errors


def test_check_install_reports_installed_runtime_smoke_errors(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    plugin_id = "%s@%s" % (module.PLUGIN_NAME, module.MARKETPLACE_NAME)
    install_path = (tmp_path / "install").resolve()
    commands_dir = install_path / "commands"
    runtime_bin = install_path / "runtime" / "bin"
    commands_dir.mkdir(parents=True)
    runtime_bin.mkdir(parents=True)

    for name in module.EXPECTED_COMMANDS:
        (commands_dir / ("%s.md" % name)).write_text(
            'Use ${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py\\n',
            encoding="utf-8",
        )
    for marker in module.RUNTIME_MARKER_FILES:
        path = install_path / marker
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("ok\n", encoding="utf-8")
    (runtime_bin / "selfcheck.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    workspace_state = workspace / ".claude" / module.WORKSPACE_STATE
    workspace_state.parent.mkdir(parents=True, exist_ok=True)
    workspace_state.write_text(
        json.dumps(
            {
                "plugin_version": module.plugin_version(),
                "marketplace_dir": str(module.workspace_marketplace_dir(workspace)),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "installed_plugin_record", lambda pid, target: {"installPath": str(install_path)} if pid == plugin_id else {})

    class Proc:
        def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, cwd):
        if cmd[:3] == ["claude", "plugin", "validate"]:
            return Proc(0, "ok")
        if cmd[:3] == ["claude", "plugin", "list"]:
            return Proc(0, plugin_id)
        if cmd[:3] == ["claude", "plugin", "details"]:
            return Proc(0, "Skills (4)  analyse, review, start, validate")
        if cmd[:4] == ["claude", "plugin", "marketplace", "list"]:
            return Proc(0, str(module.workspace_marketplace_dir(workspace)))
        if cmd[0] == sys.executable and cmd[1] == str(runtime_bin / "selfcheck.py"):
            return Proc(0, json.dumps({"dependency_boundary": {"source_repo_required": False}, "errors": []}))
        raise AssertionError("unexpected command: %r" % (cmd,))

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "run_installed_runtime_smoke", lambda wrapper, target: ["installed plugin analyse smoke failed: traceback"])

    errors = module.check_install(workspace)

    assert "installed plugin analyse smoke failed: traceback" in errors


def test_uninstall_legacy_plugins_uses_local_scope(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    calls = []

    class Proc:
        def __init__(self, returncode):
            self.returncode = returncode

    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        return Proc(0)

    monkeypatch.setattr(module, "run", fake_run)

    removed = module.uninstall_legacy_plugins(workspace)

    assert removed == ["midstack-triage@midstack-triage-local"]
    assert calls == [
        (
            ["claude", "plugin", "uninstall", "midstack-triage@midstack-triage-local", "--scope", "local"],
            workspace,
        )
    ]


def test_install_plugin_enables_local_plugin_after_update(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    plugin_id = "%s@%s" % (module.PLUGIN_NAME, module.MARKETPLACE_NAME)
    calls = []

    class Proc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        return Proc(0)

    monkeypatch.setattr(module, "run", fake_run)

    module.install_plugin(workspace)

    assert calls == [
        (["claude", "plugin", "update", plugin_id, "--scope", "local"], workspace),
        (["claude", "plugin", "enable", plugin_id, "--scope", "local"], workspace),
    ]


def test_install_plugin_enables_local_plugin_after_install(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    plugin_id = "%s@%s" % (module.PLUGIN_NAME, module.MARKETPLACE_NAME)
    calls = []

    class Proc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        if cmd[:3] == ["claude", "plugin", "update"]:
            return Proc(1)
        return Proc(0)

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "require_ok", lambda cmd, cwd: calls.append((cmd, cwd)) or Proc(0))

    module.install_plugin(workspace)

    assert calls == [
        (["claude", "plugin", "update", plugin_id, "--scope", "local"], workspace),
        (["claude", "plugin", "install", plugin_id, "--scope", "local"], workspace),
        (["claude", "plugin", "enable", plugin_id, "--scope", "local"], workspace),
    ]


def test_install_plugin_treats_already_enabled_as_success(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    plugin_id = "%s@%s" % (module.PLUGIN_NAME, module.MARKETPLACE_NAME)
    calls = []

    class Proc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, cwd):
        calls.append((cmd, cwd))
        if cmd[:3] == ["claude", "plugin", "enable"]:
            return Proc(1, stderr='Plugin "%s" is already enabled at local scope' % plugin_id)
        return Proc(0)

    monkeypatch.setattr(module, "run", fake_run)

    module.install_plugin(workspace)

    assert calls == [
        (["claude", "plugin", "update", plugin_id, "--scope", "local"], workspace),
        (["claude", "plugin", "enable", plugin_id, "--scope", "local"], workspace),
    ]


def test_purge_project_state_ignores_missing_claude_state(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()

    class Proc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    monkeypatch.setattr(
        module,
        "run",
        lambda cmd, cwd: Proc(
            1,
            stderr="No Claude Code project state found for %s under /root/.claude.\n" % workspace,
        ),
    )

    module.purge_project_state(workspace)


def test_build_marketplace_stages_bundled_runtime(tmp_path, monkeypatch):
    module = load_claude_plugin_install()
    workspace = tmp_path / "sandbox"
    workspace.mkdir(parents=True)
    plugin_dir = module.marketplace_plugin_dir(workspace)

    module.copy_plugin_source(plugin_dir)
    module.stage_runtime_bundle(plugin_dir)
    module.validate_runtime_bundle(plugin_dir)

    for marker in module.RUNTIME_MARKER_FILES:
        assert plugin_dir.joinpath(marker).exists(), marker
    assert (plugin_dir / "LICENSE").read_text(encoding="utf-8") == (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert (plugin_dir / "NOTICE").read_text(encoding="utf-8") == (ROOT / "NOTICE").read_text(encoding="utf-8")


def test_write_workspace_state_uses_bundled_runtime_mode(tmp_path):
    module = load_claude_plugin_install()
    workspace = tmp_path / "sandbox"
    workspace.mkdir(parents=True)

    module.write_workspace_state(workspace)

    state = json.loads((workspace / ".claude" / module.WORKSPACE_STATE).read_text(encoding="utf-8"))
    assert state["install_mode"] == "claude-local-marketplace-bundled-runtime"
    assert state["runtime_mode"] == "bundled-plugin"
    assert "engine_root" not in state
    assert "plugin_source" not in state
    assert state["marketplace_dir"] == str(module.workspace_marketplace_dir(workspace))


def test_staged_runtime_analyse_smoke_handles_blocked_remote_collection(tmp_path):
    module = load_claude_plugin_install()
    workspace = (tmp_path / "sandbox").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    plugin_dir = module.marketplace_plugin_dir(workspace)
    incident_dir = workspace / ".local" / "incidents" / "mongodb-ready-incident"
    remote_runs_dir = workspace / ".local" / "remote-runs"
    fake_bin = workspace / ".tmp-bin"
    fake_sshpass = fake_bin / "sshpass"

    module.copy_plugin_source(plugin_dir)
    module.stage_runtime_bundle(plugin_dir)
    module.validate_runtime_bundle(plugin_dir)

    incident_dir.mkdir(parents=True, exist_ok=True)
    remote_runs_dir.mkdir(parents=True, exist_ok=True)
    fake_bin.mkdir(parents=True, exist_ok=True)

    fake_sshpass.write_text(
        "#!/bin/sh\n"
        "echo 'ssh: connect to host 192.0.2.10 port 22: Connection refused' >&2\n"
        "exit 255\n",
        encoding="utf-8",
    )
    fake_sshpass.chmod(0o755)

    (incident_dir / "input.yaml").write_text(
        yaml.safe_dump(
            {
                "incident_id": "mongodb-ready-incident",
                "middleware": "mongodb",
                "namespace": "psmdb-test",
                "cluster_id": "",
                "customer_clue": "MongoDB pod is not ready.",
                "scenario": "unknown",
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    (incident_dir / "meta.yaml").write_text(
        yaml.safe_dump(
            {
                "incident_id": "mongodb-ready-incident",
                "middleware": "mongodb",
                "status": "ready",
                "current_command": "start",
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    (incident_dir / "remote-config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "mongodb-ready-incident-remote",
                "purpose": "incident remote Kubernetes environment",
                "access": {
                    "candidate_ips": ["192.0.2.10"],
                    "primary_ip": "192.0.2.10",
                    "username": "root",
                    "password": "secret",
                    "port": 22,
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["MIDSTACK_TRIAGE_WORKSPACE"] = str(workspace)
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    proc = subprocess.run(
        [
            sys.executable,
            str(plugin_dir / "runtime" / "bin" / "midstack-local.py"),
            "analyse",
            "--incident-dir",
            str(incident_dir),
        ],
        cwd=str(workspace),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    assert proc.returncode == 0
    assert "Traceback" not in proc.stdout
    assert "Traceback" not in proc.stderr

    adapter = yaml.safe_load((incident_dir / "adapter-output.yaml").read_text(encoding="utf-8"))
    assert adapter["status"] == "blocked"
    assert adapter["blocking_items"][0]["code"] == "ssh_unreachable"
    assert "rerun /midstack:analyse" in adapter["next_actions"][0]

    remote_run = yaml.safe_load((incident_dir / "remote-executor-run.yaml").read_text(encoding="utf-8"))
    assert remote_run["status"] == "blocked"
    assert remote_run["error"]["code"] == "ssh_unreachable"
