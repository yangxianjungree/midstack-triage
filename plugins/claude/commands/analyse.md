---
description: Analyse the current or specified Midstack incident
argument-hint: [incident-id-or-path]
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

First hop: run the installed Midstack runtime wrapper below. Do not implement
triage directly in the slash command before the runtime command returns.

Command boundary:

- The first shell command must call `${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py`.
- Do not call repository source-tree `tools/plugin/midstack-local.py`.
- Do not run ad-hoc SSH, sshpass, scp, kubectl, database clients, or package
  installers from the slash command layer.
- Remote execution tools are runtime implementation details; the Midstack
  runtime may use SSH/sshpass/scp/kubectl internally.
- Do not create or edit `analysis.yaml` before `midstack-local.py analyse`
  succeeds.
- If `analyse` returns `blocked`, summarize `blocking_items` and stop.
- Do not print passwords or tokens; redact credentials in summaries.
- `--execution-mode remote` is the default live-collection mode. Use
  `--execution-mode offline` only when analysing existing incident artifacts or
  a remote-run directory; local execution is reserved and currently returns
  blocked.

If `$ARGUMENTS` is empty, analyse the current incident:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/resolve-workspace.py")"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" analyse \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

If `$ARGUMENTS` contains an incident id or path, pass `--incident-dir`:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/resolve-workspace.py")"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" analyse \
  --incident-dir "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents/<incident-id>" \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

After analyse succeeds, refine `analysis.yaml` and `report.md` according to
`agent-reasoning-task.md`, then run `finalize-analysis`.

After finalize succeeds, read `.local/incidents/<incident-id>/adapter-output.yaml`.
If `status=completed`, print `user_message` from `adapter-output.yaml` verbatim.
It is the fixed Markdown table for the completed analysis response; do not
rewrite it as prose.
