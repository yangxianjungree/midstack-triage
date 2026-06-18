---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-script-output-contract-split/spec.md
  - ../2026-06-17-module-refactor-roadmap/spec.md
---

# Spec: Executor Preflight Split

## Objective

Reduce `execution.remote.capabilities` scope by moving batch-level remote executor preflight checks into `execution.remote.executor_preflight`.

The new module owns checks for local `sshpass`, remote SSH reachability, remote `kubectl`, cluster context, and `kubectl exec` permission. `capabilities.py` keeps compatibility exports for existing callers.

## Assumptions

1. Existing callers may still import or call `validate_executor_capabilities` from `execution.remote.capabilities` or `execution.remote.executor`.
2. This slice does not change error codes, check names, check order, or command strings.
3. Script-specific Pod target and pod tool probing remains in `capabilities.py` for a later slice.

## Success Criteria

- `src/execution/remote/executor_preflight.py` owns `validate_executor_capabilities`.
- `src/execution/remote/capabilities.py` delegates batch preflight to the new module.
- `src/execution/remote/script_runner.py` imports preflight from the focused module.
- Remote executor validator still passes.

## Commands

```bash
python3 -m py_compile src/execution/remote/capabilities.py src/execution/remote/executor_preflight.py src/execution/remote/script_runner.py src/execution/remote/executor.py
python3 tools/validators/validate-remote-executor.py
python3 -m pytest tests/execution/remote tests/plugins/test_install_common.py -q
git diff --check
```

## Boundaries

- Always: Preserve old compatibility imports and monkeypatch behavior through `executor.py`.
- Ask first: Changing remote command strings or blocked/failed status mapping.
- Never: Move script-level Pod target resolution in this slice.

## Tasks

- [x] Task: Extract executor preflight module
  - Acceptance: batch preflight implementation no longer lives in `capabilities.py`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/executor_preflight.py`, `src/execution/remote/capabilities.py`, `src/execution/remote/script_runner.py`
- [x] Task: Keep installed runtime complete
  - Acceptance: plugin runtime marker checks include the new module.
  - Verify: `python3 -m pytest tests/plugins/test_install_common.py -q`
  - Files: `plugins/support/install_common.py`, `plugins/claude/runtime/bin/selfcheck.py`, `tests/plugins/test_install_common.py`

## Open Questions

None for this slice.
