# Midstack Triage Claude Plugin

Claude Code local plugin with a bundled Midstack runtime.

The plugin source lives in this repository under `plugins/claude/`. A target
workspace stores runtime configuration and incident outputs, but the executable
runtime is packaged into the installed Claude plugin itself.

Claude command-surface rule: this plugin must use `name = "midstack"` plus
`commands/*.md`. Do not model Claude slash entrypoints as `skills/midstack:*`.
Claude may display `/midstack:start` in the picker but accept `Tab` as a
different canonical command when the plugin is implemented as namespaced
skills.

## Install To Sandbox

```bash
python3 plugins/claude/plugin-install.py install \
  --workspace /home/stephen/AI/midstack-cursor-sandbox
```

This command:

1. Validates `plugins/claude/` with `claude plugin validate`.
2. Runs `claude project purge -y <workspace>` to delete stale Claude project
   transcripts/history for that sandbox.
3. Copies the Midstack runtime payload into the plugin package under
   `plugins/claude/runtime/` in the marketplace snapshot.
4. Writes `.claude/midstack-triage.workspace.json` in the target workspace.
5. Builds a local Claude marketplace under
   `<workspace>/.claude/marketplaces/midstack-triage-local/`.
6. Registers that sandbox-local marketplace with Claude Code for the target
   project.
7. Uninstalls legacy `midstack-triage@midstack-triage-local` if present.
8. Installs or updates `midstack@midstack-triage-local` at local project scope.
9. Runs a post-install check against Claude's visible plugin inventory and the
   installed plugin payload.

After changing plugin source or bundled runtime files, run the same `install`
command again. The installer publishes a new marketplace snapshot, purges old
Claude resume sessions for that workspace, and asks Claude to update the local
installation. This prevents stale slash metadata from old resumed sessions
rewriting `/midstack:start` to legacy entries.

If you intentionally want to keep Claude project history during an install, add
`--keep-project-state`. That mode may preserve stale resumed-session slash
metadata, so use it only when command-surface changes are not involved.

## Check

```bash
python3 plugins/claude/plugin-install.py check \
  --workspace /home/stephen/AI/midstack-cursor-sandbox
```

Then from the sandbox:

```bash
cd /home/stephen/AI/midstack-cursor-sandbox
claude plugin list
```

`midstack@midstack-triage-local` should appear.
The check command also verifies that Claude exposes the short command ids
`start`, `analyse`, `review`, and `validate` under the `midstack` plugin, that
the installed plugin contains the bundled runtime payload, and that the active
marketplace root lives under the target sandbox instead of this source repo.

The plugin exposes these Claude slash commands:

- `/midstack:start`
- `/midstack:analyse`
- `/midstack:review`
- `/midstack:validate`

Do not keep parallel hyphen aliases such as `/midstack-start` in the Claude
plugin. When both styles are installed, Claude may attribute turns to the
hyphen skill and users end up invoking `/midstack-triage:midstack-start` or
seeing `/midstack:start` rewritten to the wrong entry.

For Claude, do not use `skills/midstack:*`. The short `/midstack:*` command
surface is achieved by naming the plugin `midstack` and keeping the actual
command files as `commands/start.md`, `commands/analyse.md`, `commands/review.md`,
and `commands/validate.md`.

## Runtime Mode

Claude commands run plugin-local wrappers such as:

- `${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py`
- `${CLAUDE_PLUGIN_ROOT}/runtime/bin/validate-repo.py`

Those wrappers execute the bundled runtime tree under
`${CLAUDE_PLUGIN_ROOT}/runtime/...`. They do not `cd` back into the source
repository and do not read `engine_root` from workspace state.

The workspace state file remains only for project-local output settings such as
`.local/incidents`, the sandbox-local marketplace root, and installed version
bookkeeping.

The bundled runtime itself is dual-plane:

- control plane
  slash command handling, incident orchestration, phase flow, reasoning, and reporting
- execution plane
  SSH/SSHPass remote access, capability checks, script staging, remote execution, and artifact retrieval

For Claude, both planes are bundled into `${CLAUDE_PLUGIN_ROOT}/runtime/src/...`.
Only the remote target environment sits outside the plugin payload.

## Dependency Boundary

The installed Claude plugin is self-contained in one specific sense: the
Midstack runtime code, manifests, routing maps, domain assets, and analyse
entrypoints are bundled into the installed plugin payload under
`${CLAUDE_PLUGIN_ROOT}/runtime/`. The sandbox does not need a separate
`/home/stephen/AI/midstack-triage` checkout at runtime.

It is not self-contained in the stronger "single binary with no external
requirements" sense. Live triage still depends on:

- local host tools: `python3`, `bash`, `claude`, `ssh`, `sshpass`, `PyYAML`
- remote access: a reachable jump host and valid SSH credentials
- remote environment: `kubectl`, usable kube context, and the cluster-side
  permissions/scripts needed by the selected MongoDB collection flow

Real Phase 4 Claude-API reasoning is optional. The current bundled runtime
defaults to the mock Phase 4 agent, so `anthropic` and `ANTHROPIC_API_KEY` are
not required unless you explicitly switch that path on later.

Run `/midstack:validate` inside the sandbox after install to check the bundled
runtime and local host dependencies from the installed plugin itself.

## Dev Session

For one-off development without installing through the marketplace:

```bash
cd /home/stephen/AI/midstack-cursor-sandbox
claude --plugin-dir /home/stephen/AI/midstack-triage/plugins/claude
```
