# Cursor Integration

Official **local Cursor plugin** for Midstack Triage using **Agent CLI + shell**.

Commands and rules tell the agent to run `tools/plugin/midstack-local.py`. **Not for Cursor Marketplace upload.**

## Boundary

`plugins/cursor/` is a projection adapter, not a bundled runtime plugin.

- It projects slash commands and rules into the target workspace.
- Runtime execution still goes through the source checkout referenced by
  `.cursor/midstack-triage.workspace.json#engine_root`.
- If code must survive installation as runtime implementation, it belongs under
  `src/`, not under `plugins/cursor/`.
- If code is only for repository-side validation or replay, it belongs under
  `tools/` or `tests/`.

Do not copy partial runtime files into a Cursor sandbox to simulate install.
The supported flow is: keep source in this repo, project commands/rules into
the target workspace, and let the adapter call back into the source checkout.

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

1. Symlinks `plugins/cursor/` → `~/.cursor/plugins/local/midstack-triage`
2. Symlinks `.cursor/commands/midstack:*.md` and `.cursor/rules/midstack-triage.mdc` into the workspace (for slash-command expansion)
3. Writes `.cursor/midstack-triage.workspace.json` with `engine_root` and `plugin_version`

Reload Cursor after upgrading.

## Agent CLI usage (sandbox)

```bash
cd /path/to/your/workspace
agent --workspace .
```

Use slash commands as usual:

```text
/midstack:start 我的192.168.154.251环境的一个mongo节点有问题，账号密码是root/123
```

Approve shell when prompted (or use `--yolo` for unattended runs).

The agent reads `engine_root` from `.cursor/midstack-triage.workspace.json` and runs:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
cd "<engine_root>" && python3 tools/plugin/midstack-local.py start ...
```

## Manual CLI (same backend)

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/path/to/workspace"
cd "/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py analyse \
  --input-dir tests/fixtures/active/mongodb/connection-failure-sample \
  --output-dir .local/incidents/offline-test
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
python3 plugins/cursor/test-sandbox.py
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
| `midstack-triage` git clone | `engine_root` in workspace state |
