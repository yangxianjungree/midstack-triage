---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-executor-preflight-split/spec.md
  - ../2026-06-17-module-refactor-roadmap/spec.md
---

# Spec: Remote Error Contract Split

## Objective

Move remote execution error codes, status mapping, capability-check result construction, and common error classifiers out of `execution.remote.capabilities` into `execution.remote.error_contract`.

This reduces coupling before splitting script-level Pod probing from `capabilities.py`.

## Assumptions

1. Existing imports from `execution.remote.capabilities` and `execution.remote.executor` must continue to work.
2. This slice does not change error codes, status mapping, check names, or classification behavior.
3. No live remote command behavior changes in this slice.

## Success Criteria

- `src/execution/remote/error_contract.py` owns common remote error helpers.
- `executor_preflight.py`, `script_runner.py`, and `capabilities.py` use the focused module for common error helpers.
- `capabilities.py` retains compatibility exports.
- Remote executor validator still passes.

## Commands

```bash
python3 -m py_compile src/execution/remote/error_contract.py src/execution/remote/capabilities.py src/execution/remote/executor_preflight.py src/execution/remote/script_runner.py src/execution/remote/executor.py
python3 tools/validators/validate-remote-executor.py
python3 -m pytest tests/execution/remote tests/plugins/test_install_common.py -q
git diff --check
```

## Boundaries

- Always: Preserve old compatibility imports.
- Ask first: Changing any error code or blocked/failed mapping.
- Never: Move Pod target probing in this slice.

## Tasks

- [x] Task: Extract remote error contract
  - Acceptance: common remote error helpers live in `error_contract.py`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/error_contract.py`, `src/execution/remote/capabilities.py`, `src/execution/remote/executor_preflight.py`, `src/execution/remote/script_runner.py`
- [x] Task: Keep installed runtime complete
  - Acceptance: plugin runtime marker checks include the new module.
  - Verify: `python3 -m pytest tests/plugins/test_install_common.py -q`
  - Files: `plugins/support/install_common.py`, `plugins/claude/runtime/bin/selfcheck.py`, `tests/plugins/test_install_common.py`

## Open Questions

None for this slice.
