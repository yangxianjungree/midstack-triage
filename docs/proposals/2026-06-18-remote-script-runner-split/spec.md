---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-execution-facade-cleanup/spec.md
  - ../../concepts/architecture.md
---

# Spec: Remote Script Runner Split

## Objective

Continue the execution facade cleanup by moving per-script remote execution out of `execution.remote.executor`.

`executor.py` remains the compatibility import and `python -m execution.remote.executor` entrypoint. New runtime implementation for one script run lives in `execution.remote.script_runner`.

## Assumptions

1. Existing callers may still import `run_script` and helper symbols from `execution.remote.executor`.
2. Validator monkeypatches currently replace `executor.run_ssh`, `executor.scp_to`, and `executor.scp_from`; this compatibility must keep working.
3. This slice does not change request/result schema, status semantics, capability checks, or CLI arguments.

## Success Criteria

- `src/execution/remote/script_runner.py` owns `run_script`.
- `src/execution/remote/executor.py` is a compatibility facade that delegates to `script_runner`.
- `src/execution/remote/cli.py` imports implementation from focused modules instead of depending on executor internals for new code.
- Remote executor validator and targeted tests pass.

## Commands

```bash
python3 -m pytest tests/execution/remote tests/phases/phase3/test_collection.py -q
python3 tools/validators/validate-remote-executor.py
python3 -m py_compile src/execution/remote/executor.py src/execution/remote/script_runner.py src/execution/remote/cli.py
git diff --check
```

## Boundaries

- Always: preserve `python -m execution.remote.executor`.
- Always: preserve old imports from `execution.remote.executor`.
- Ask first: changing remote executor output files or schema.
- Never: fold CLI orchestration back into `executor.py`.

## Tasks

- [x] Task: Add script runner module
  - Acceptance: `run_script` implementation no longer lives in `executor.py`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/script_runner.py`, `src/execution/remote/executor.py`
- [x] Task: Update module docs and runtime markers
  - Acceptance: execution README and plugin marker list mention the new module.
  - Verify: `python3 -m pytest tests/plugins/claude tests/plugins/cursor -q`
  - Files: `src/execution/remote/README.md`, `src/execution/README.md`, `plugins/support/install_common.py`

## Open Questions

Further splitting of artifact retrieval or script staging can wait until there is a live remote regression plan.
