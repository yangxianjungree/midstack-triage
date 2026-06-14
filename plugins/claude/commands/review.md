---
description: Review and score a Midstack incident analysis
argument-hint: [incident-id-or-path]
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" review \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

For an explicit incident, pass `--incident-dir
"$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents/<incident-id>"`.

Return the review score dimensions from `analysis.yaml` or
`review-adapter-output.yaml`.
