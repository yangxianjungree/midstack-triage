# Midstack Analyse

Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `runtime_root`. Set `MIDSTACK_TRIAGE_WORKSPACE` to the absolute workspace path.

Cursor runs Midstack from the workspace-local bundled runtime. Use `runtime_root` from workspace state and do not `cd` into the Midstack source repository.

If the user just ran `/midstack:start` and does not provide an incident directory, run `analyse` without `--incident-dir` (uses `.local/incidents/.current-incident`).

If the user provides an incident directory, pass `--incident-dir <path>` relative to the workspace or absolute.

## Run analyse

Current incident after `/midstack:start`:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" analyse \
  --output-root .local/incidents
```

Explicit incident directory:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" analyse \
  --incident-dir .local/incidents/<incident-id> \
  --output-root .local/incidents
```

Maintainer fixture replay is not part of normal installed workspace use. Run it from the Midstack source repository test suite, not from this Cursor command.

Remote run directory:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" analyse \
  --remote-run-dir .local/remote-runs/<run-id> \
  --output-root .local/incidents
```

Local remote config:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" analyse \
  --remote-config .local/test-envs/mongodb-k8s.yaml \
  --remote-output-dir .local/remote-runs \
  --output-root .local/incidents
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
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" finalize-analysis \
  --output-root .local/incidents
```

Or `--incident-dir .local/incidents/<incident-id>`.

Then summarize conclusion, confidence, supported level, evidence gaps, and output paths.

For normal incident triage, do not run fixture replay. Use the current incident from `/midstack:start` or an explicit incident directory.
