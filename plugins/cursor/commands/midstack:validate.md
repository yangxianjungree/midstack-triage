# Midstack Validate

Maintainer check. Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `engine_root`.

Cursor validation runs against the source checkout. It does not use a bundled plugin runtime payload.

```bash
cd "/abs/path/to/midstack-triage" && python3 tools/validators/validate-repo.py \
  --skip-cursor \
  --score-min-level medium
```

Report whether assets, replay, and score gate passed. If maintainers also need Cursor adapter smoke, run `python3 plugins/cursor/test-agent-cli.py` or `validate-repo.py` without `--skip-cursor`.
