# Midstack Analyse

Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `engine_root`. Set `MIDSTACK_TRIAGE_WORKSPACE` to the absolute workspace path.

If the user just ran `/midstack:start` and does not provide an incident directory, run `analyse` without `--incident-dir` (uses `.local/incidents/.current-incident`).

If the user provides an incident directory, pass `--incident-dir <path>` relative to the workspace or absolute.

## Run analyse

Current incident after `/midstack:start`:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py analyse \
  --output-root .local/incidents
```

Explicit incident directory:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py analyse \
  --incident-dir .local/incidents/<incident-id> \
  --output-root .local/incidents
```

Fixture replay:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py analyse \
  --input-dir tests/fixtures/mongodb/connection-failure-sample \
  --output-dir .local/incidents/cursor-connection-failure
```

Remote run directory:

```bash
... analyse --remote-run-dir .local/remote-runs/<run-id> --output-root .local/incidents
```

Local remote config:

```bash
... analyse --remote-config .local/test-envs/mongodb-k8s.yaml --remote-output-dir .local/remote-runs --output-root .local/incidents
```

## After analyse shell succeeds

- Read `agent-reasoning-task.md` in the incident directory.
- Read `input.yaml`, `structured_record.yaml`, `signal_bundle.yaml`, and `collection_report.yaml`.
- Inspect `signal_bundle.log_highlights`, `structured_record.details.dns_checks`, `structured_record.details.pod_terminations`, and any `file_tail` log evidence.
- Treat `analysis.rules-fallback.yaml` as fallback only.
- Update `analysis.yaml` and `report.md` with Agent-led multi-hypothesis reasoning, gap classification, source-boundary handling, DNS/file-log validation, and conclusion-depth limits.
- Classify gaps as `expected_gap` or `critical_gap`.
- Use `deepest_supported_level` when useful: `phenomenon`, `impact`, `mechanism`, or `root_cause`.
- Treat DNS probe `blocked` as an evidence gap; DNS probe `failed` is mechanism evidence only with DNS-layer error text.

Finalize:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py finalize-analysis \
  --output-root .local/incidents
```

Or `--incident-dir .local/incidents/<incident-id>`.

Then summarize conclusion, confidence, supported level, evidence gaps, and output paths.

Default fixture smoke (when user did not specify a case): use the fixture command above, then run `/midstack:review` for the same incident directory.
