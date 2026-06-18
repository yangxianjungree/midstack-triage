---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-remote-script-runner-split/spec.md
  - ../2026-06-17-module-refactor-roadmap/spec.md
---

# Spec: Script Output Contract Split

## Objective

Reduce `execution.remote.capabilities` scope by moving `output.yaml` schema constants and validation into a focused `execution.remote.script_output_contract` module.

`capabilities.py` keeps compatibility exports for existing callers, but new runtime code should import the contract module directly.

## Assumptions

1. Existing validator code may still call `execution.remote.executor.validate_script_output_contract`.
2. Existing imports of `SCRIPT_OUTPUT_REQUIRED_FIELDS`, `SCRIPT_OUTPUT_ALLOWED_STATUSES`, and `validate_script_output_contract` from `capabilities.py` must continue to work.
3. This slice does not change `output.yaml` required fields, allowed statuses, or error messages.

## Success Criteria

- `src/execution/remote/script_output_contract.py` owns script output constants and validation.
- `src/execution/remote/capabilities.py` no longer implements the output contract logic.
- `src/execution/remote/script_runner.py` imports the validator from the focused module.
- Remote executor validator still passes.

## Commands

```bash
python3 -m py_compile src/execution/remote/capabilities.py src/execution/remote/script_output_contract.py src/execution/remote/script_runner.py src/execution/remote/executor.py
python3 tools/validators/validate-remote-executor.py
python3 -m pytest tests/execution/remote tests/plugins/test_install_common.py -q
git diff --check
```

## Boundaries

- Always: Preserve old compatibility imports.
- Ask first: Changing `output.yaml` schema or stricter validation behavior.
- Never: Mix pod target probing or preflight checks into this contract module.

## Tasks

- [x] Task: Extract script output contract
  - Acceptance: `capabilities.py` delegates to `script_output_contract.py`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/script_output_contract.py`, `src/execution/remote/capabilities.py`, `src/execution/remote/script_runner.py`
- [x] Task: Keep installed runtime complete
  - Acceptance: plugin runtime marker checks include the new module.
  - Verify: `python3 -m pytest tests/plugins/test_install_common.py -q`
  - Files: `plugins/support/install_common.py`, `plugins/claude/runtime/bin/selfcheck.py`, `tests/plugins/test_install_common.py`

## Open Questions

None for this slice.
