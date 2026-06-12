# Midstack Validate

Maintainer check. Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `engine_root`.

```bash
cd "/abs/path/to/midstack-triage" && python3 tools/validators/validate-repo.py \
  --skip-cursor \
  --score-min-level medium
```

Report whether assets, replay, score gate, and agent-cli plugin smoke passed (`validate-repo.py` without `--skip-cursor`).
