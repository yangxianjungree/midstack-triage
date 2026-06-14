# Agent Plugin Adapters

This directory contains source adapters for agent runtimes. It must not contain
target workspace installation projections.

## Layout

```text
plugins/
├── README.md
├── claude/
│   ├── .claude-plugin/plugin.json
│   ├── commands/
│   ├── runtime/
│   ├── plugin-install.py
│   └── README.md
└── cursor/
    ├── .cursor-plugin/plugin.json
    ├── commands/
    ├── rules/
    ├── plugin-install.py
    └── README.md
```

## Ownership

- `plugins/claude/` is the Claude Code plugin source. It is validated with
  `claude plugin validate plugins/claude` and installed through
  `plugins/claude/plugin-install.py`.
- `plugins/claude/runtime/` is the Claude-only packaged runtime payload. Treat
  it as installer-owned output structure inside the plugin source tree. Files
  under this subtree must support plugin-local execution with
  `${CLAUDE_PLUGIN_ROOT}` and must not assume the source repository checkout is
  available from the sandbox.
- `plugins/cursor/` is the Cursor adapter source. It installs Cursor command
  and rule projections only; runtime execution still goes through the source
  repository checkout referenced by workspace `engine_root`.
- Shared runtime code stays in project-level source directories such as
  `src/` for reusable implementation, `tools/` for thin entrypoints and
  validators, plus `domains/`, `core/`, and `scenarios/` for knowledge/runtime
  assets.

## Claude Directory Contract

`plugins/claude/` is intentionally split by responsibility:

- `.claude-plugin/plugin.json`
  Claude manifest only.
- `commands/*.md`
  User-facing slash commands. These must use `${CLAUDE_PLUGIN_ROOT}` for
  plugin-internal paths and must not read `engine_root` from workspace state.
- `runtime/bin/*.py`
  Thin entry wrappers invoked by command markdown.
- `runtime/tools`, `runtime/src`, `runtime/domains`, `runtime/scenarios`,
  `runtime/core`, `runtime/interfaces`
  Bundled runtime tree copied into the installed Claude plugin payload.
- `plugin-install.py`
  The only supported pack/install/update entrypoint for Claude.

Do not place unrelated agent files, ad hoc experiments, or workspace-specific
projections into `plugins/claude/`. If a file does not belong to the manifest,
command surface, bundled runtime, or installer flow, it is in the wrong place.

## Source Vs Projection

Plugin source belongs in this repository. Target workspaces such as
`/home/stephen/AI/midstack-cursor-sandbox` are consumers.

Target workspaces may contain runtime state:

```text
.claude/midstack-triage.workspace.json
.claude/marketplaces/midstack-triage-local/
.cursor/midstack-triage.workspace.json
.local/incidents/
```

Target workspaces must not be treated as plugin source. Do not copy
`.claude-plugin/plugin.json`, `commands/`, or partial runtime files into a
sandbox root to simulate installation. Claude only lists installed plugins that
were registered through its plugin install system or loaded for a session with
`--plugin-dir`.

## Boundaries

Always:

- Keep agent-specific plugin files under their matching adapter directory.
- Use the adapter's own installer for packaging, install, deploy, and update.
- Validate with the runtime's native validator before testing in a sandbox.

Ask first:

- Adding a new adapter directory under `plugins/`.
- Changing the shared runtime contract in `src/commands/` or the plugin CLI adapter contract in `tools/plugin/midstack-local.py`.
- Replacing an existing install mode.

Never:

- Put Claude plugin files in `plugins/cursor/`.
- Put Cursor projection logic in `plugins/claude/`.
- Put source plugin manifests at a sandbox project root as a substitute for
  installation.
- Hard-code one developer's absolute sandbox path in reusable plugin skills or
  commands.
- Keep duplicate Claude slash surfaces such as both `/midstack-start` and
  `/midstack:start` for the same action. Claude may route users to the wrong
  skill name.
- Implement Claude `/midstack:*` entrypoints as `skills/midstack:*`. For Claude
  plugin Tab-completion behavior, use plugin name `midstack` plus
  `plugins/claude/commands/*.md`.
- Put repository-only assumptions into Claude commands, such as `cd
  "$ENGINE_ROOT"` or reading `engine_root` from workspace state. Claude plugin
  commands must be able to run from the installed plugin payload alone.

Self-contained means "runtime payload bundled into the installed plugin", not
"no host or remote prerequisites". A correct Claude plugin install must run
without a source-repo checkout in the sandbox, but live triage still requires
host tools such as `python3` and `sshpass`, plus the remote Kubernetes/MongoDB
environment that the incident collection flow targets.

## Current Commands

Claude:

```bash
claude plugin validate plugins/claude
python3 plugins/claude/plugin-install.py install --workspace /home/stephen/AI/midstack-cursor-sandbox
python3 plugins/claude/plugin-install.py check --workspace /home/stephen/AI/midstack-cursor-sandbox
```

`plugins/claude/plugin-install.py install` purges Claude's saved project state
for the target sandbox before reinstalling, rebuilds a sandbox-local marketplace
under `.claude/marketplaces/midstack-triage-local/`, removes the legacy
`midstack-triage@midstack-triage-local` install, and installs
`midstack@midstack-triage-local`. This is deliberate: old resumed sessions, the
old namespaced plugin id, and a repo-local marketplace can all keep the wrong
slash-command behavior or runtime path alive. Use `--keep-project-state` only
when you explicitly want to preserve transcript/history state.

Cursor:

```bash
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /home/stephen/AI/midstack-cursor-sandbox
python3 plugins/cursor/plugin-install.py --check-workspace /home/stephen/AI/midstack-cursor-sandbox
```
