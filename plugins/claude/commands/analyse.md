---
description: Analyse the current or specified Midstack incident
argument-hint: [incident-id-or-path]
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

First action: run the Bash command below. Do not inspect the environment,
install packages, or connect to MongoDB directly before the runtime command.

Hard boundary:

- Do not run `mongosh`, `mongo`, `pip`, `pip3`, `apt`, `yum`, raw `ssh`, or raw
  `kubectl`.
- Do not create or edit `analysis.yaml` before `midstack-local.py analyse`
  succeeds.
- If `analyse` returns `blocked`, summarize `blocking_items` and stop.
- Do not print passwords or tokens; redact credentials in summaries.

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

After analyse succeeds, summarize `analysis.yaml`, `report.md`, and
`reasoning-board.yaml` when present.
