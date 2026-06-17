# Midstack Validate

Maintainer check. Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `runtime_root`.

Cursor validation runs against the workspace-local bundled runtime. It must not `cd` into the Midstack source repository.

This is a maintenance-only check, not part of the user triage path.

```bash
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/validate-repo.py" \
  --skip-cursor \
  --score-min-level medium
```

Report whether assets, replay, and score gate passed. If maintainers also need Cursor adapter smoke, run it from the Midstack source repository outside the user workflow.
