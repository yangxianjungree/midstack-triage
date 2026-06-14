---
description: Analyse the current or specified Midstack incident
argument-hint: [incident-id-or-path]
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

If `$ARGUMENTS` is empty, analyse the current incident:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" analyse \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

If `$ARGUMENTS` contains an incident id or path, pass `--incident-dir`:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" analyse \
  --incident-dir "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents/<incident-id>" \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

After analyse succeeds, summarize `analysis.yaml`, `report.md`, and
`reasoning-board.yaml` when present.
