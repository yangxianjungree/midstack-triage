---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-execution-facade-cleanup/spec.md
  - ../2026-06-18-remote-error-contract-split/spec.md
  - ../2026-06-18-script-output-contract-split/spec.md
  - ../2026-06-18-executor-preflight-split/spec.md
  - ../2026-06-18-script-capabilities-split/spec.md
---

# Spec: Executor Facade Focused Imports

## Objective

Reduce facade-to-facade coupling in `execution.remote.executor` after the remote runtime split.

`executor.py` remains the compatibility import surface and `python -m execution.remote.executor` entrypoint, but it should import compatibility symbols from the focused modules rather than through `execution.remote.capabilities`.

## Assumptions

1. Existing imports from `execution.remote.executor` must continue to work.
2. Existing imports from `execution.remote.capabilities` must continue to work.
3. Validator monkeypatches that replace `executor.run_ssh`, `executor.scp_to`, and `executor.scp_from` must keep flowing into default transports.
4. This slice does not change command strings, error codes, request/result schemas, pod target resolution, or script output validation behavior.

## Success Criteria

- `src/execution/remote/executor.py` no longer imports `execution.remote.capabilities`.
- Compatibility symbols in `executor.py` are sourced directly from `error_contract.py`, `script_output_contract.py`, `executor_preflight.py`, and `script_capabilities.py`.
- Remote executor validator and focused remote tests still pass.

## Commands

```bash
python3 -m py_compile src/execution/remote/executor.py src/execution/remote/capabilities.py src/execution/remote/script_runner.py
python3 tools/validators/validate-remote-executor.py
python3 -m pytest tests/execution/remote -q
git diff --check
```

## Boundaries

- Always: Keep `executor.py` as the compatibility facade and module entrypoint.
- Ask first: Removing `capabilities.py` compatibility exports.
- Never: Change remote execution behavior in this slice.

## Tasks

- [x] Task: Point executor facade at focused modules
  - Acceptance: `executor.py` no longer imports `execution.remote.capabilities`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/executor.py`

## Open Questions

Future work can decide whether `executor.py` should eventually shrink further by exposing fewer compatibility symbols after downstream callers migrate.
