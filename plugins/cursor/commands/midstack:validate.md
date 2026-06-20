# Midstack Validate

Maintainer check. Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `runtime_root`.

Cursor validation runs an installed-runtime self-check against the workspace-local bundled runtime. It must not `cd` into the Midstack source repository.

This is a maintenance-only check, not part of the user triage path.

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/selfcheck.py"
```

Report whether the installed runtime self-check passed and include any `errors` from the JSON output. Full repository validator, replay, score gate, and Cursor adapter smoke still run from the Midstack source repository outside the user workflow.
