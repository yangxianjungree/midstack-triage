# Midstack Review

Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `engine_root`. Set `MIDSTACK_TRIAGE_WORKSPACE` to the absolute workspace path.

If the user did not provide `incident_dir`, omit `--incident-dir` so `review` uses the current incident marker under `.local/incidents/`.

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py review \
  --output-root .local/incidents
```

Explicit incident:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py review \
  --incident-dir .local/incidents/<incident-id> \
  --output-root .local/incidents
```

Return the `analysis.yaml` path and summarize the five score dimensions from its `review` block.
