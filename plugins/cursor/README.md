# Cursor Integration

Official **local Cursor plugin** for Midstack Triage using **Agent CLI + shell**.

Commands and rules tell the agent to run the workspace-local bundled runtime at `.cursor/midstack-triage-runtime/`. **Not for Cursor Marketplace upload.**

## Boundary

`plugins/cursor/` is the Cursor adapter source.

- It projects slash commands and rules into the target workspace as copied files.
- It stages a workspace-local runtime payload under `.cursor/midstack-triage-runtime/`.
- Installed Cursor commands read `runtime_root` from `.cursor/midstack-triage.workspace.json`.
- Installed Cursor commands must not `cd` into the Midstack source repository or call source `tools/plugin/midstack-local.py`.
- If code must survive installation as runtime implementation, it belongs under `src/`, not under `plugins/cursor/`.
- Repository-side validation and replay helpers stay under `tools/` or `tests/`.

## Plugin layout

```text
plugins/cursor/
├── .cursor-plugin/plugin.json
├── commands/midstack:*.md
├── rules/midstack-triage.mdc
├── plugin-install.py
├── cli_smoke.py
├── test-agent-cli.py
└── test-sandbox.py
```

## Install

```bash
python3 plugins/cursor/plugin-install.py \
  --upgrade \
  --workspace-init /path/to/your/workspace
```

This:

1. Symlinks `plugins/cursor/` to `~/.cursor/plugins/local/midstack-triage`
2. Copies `.cursor/commands/midstack:*.md` and `.cursor/rules/midstack-triage.mdc` into the workspace
3. Copies runtime assets into `.cursor/midstack-triage-runtime/`
4. Writes `.cursor/midstack-triage.workspace.json` with `runtime_root` and `plugin_version`

Reload Cursor after upgrading.

## Agent CLI usage

```bash
cd /path/to/your/workspace
agent --workspace .
```

Use slash commands as usual:

```text
/midstack:start 我的192.168.154.251环境的一个mongo节点有问题，账号密码是root/<password>
/midstack:analyse
```

The agent reads `runtime_root` from `.cursor/midstack-triage.workspace.json` and runs:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
python3 "$(pwd)/.cursor/midstack-triage-runtime/bin/midstack-local.py" analyse --output-root .local/incidents
```

## Commands

| Command | Shell subcommand |
|---------|------------------|
| `/midstack:start` | `midstack-local.py start` |
| `/midstack:analyse` | `midstack-local.py analyse` |
| `/midstack:review` | `midstack-local.py review` |
| `/midstack:validate` | `validate-repo.py --skip-cursor` |

After analyse, the agent still edits `analysis.yaml` / `report.md`, then runs `finalize-analysis`.

## Checks

```bash
python3 plugins/cursor/plugin-install.py --check-manifest
python3 plugins/cursor/plugin-install.py --check-workspace /path/to/workspace
python3 plugins/cursor/test-agent-cli.py
python3 plugins/cursor/test-sandbox.py /home/stephen/AI/midstack-sandbox
python3 tools/validators/validate-repo.py
```

When `plugin.json` `version` changes, rerun `--upgrade --workspace-init` on each workspace.

## Bring your own

| You provide | Notes |
|-------------|-------|
| Cursor Agent CLI + LLM | Required |
| Python 3 + PyYAML | Required |
| `sshpass` | Live `/midstack:start` only |
| SSH / K8s / MongoDB cluster | Live triage only |
