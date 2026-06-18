---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-remote-error-contract-split/spec.md
  - ../2026-06-18-executor-preflight-split/spec.md
  - ../2026-06-17-module-refactor-roadmap/spec.md
---

# Spec: Script Capabilities Split

## Objective

Move script-level Pod target resolution and pod tool probing out of `execution.remote.capabilities` into `execution.remote.script_capabilities`.

`capabilities.py` remains a compatibility surface for old imports, while `script_runner.py` calls the focused module directly.

## Assumptions

1. Existing imports from `execution.remote.capabilities` and `execution.remote.executor` must continue to work.
2. This slice does not change MongoDB Pod selection, shell probing, command strings, capability check names, or warnings.
3. Batch-level preflight remains in `executor_preflight.py`; `script_capabilities.py` only handles per-script target/tool readiness.

## Success Criteria

- `src/execution/remote/script_capabilities.py` owns `remote_kubectl_get_pods`, target resolution helpers, pod tool probing, and `validate_script_capabilities`.
- `src/execution/remote/capabilities.py` delegates script-level capability checks to the new module.
- `src/execution/remote/script_runner.py` imports `validate_script_capabilities` from the focused module.
- Remote executor validator still passes.

## Commands

```bash
python3 -m py_compile src/execution/remote/capabilities.py src/execution/remote/script_capabilities.py src/execution/remote/script_runner.py src/execution/remote/executor.py
python3 tools/validators/validate-remote-executor.py
python3 -m pytest tests/execution/remote tests/plugins/test_install_common.py -q
git diff --check
```

## Boundaries

- Always: Preserve old compatibility imports.
- Ask first: Changing Pod selection, shell probing, check names, warnings, or command strings.
- Never: Move or rewrite `mongodb_collection_runtime.py` in this slice.

## Tasks

- [x] Task: Extract script capability module
  - Acceptance: script-level target and pod tool probing implementation no longer lives in `capabilities.py`.
  - Verify: `python3 tools/validators/validate-remote-executor.py`
  - Files: `src/execution/remote/script_capabilities.py`, `src/execution/remote/capabilities.py`, `src/execution/remote/script_runner.py`
- [x] Task: Keep installed runtime complete
  - Acceptance: plugin runtime marker checks include the new module and the compatibility facade it imports.
  - Verify: `python3 -m pytest tests/plugins/test_install_common.py -q`
  - Files: `plugins/support/install_common.py`, `plugins/claude/runtime/bin/selfcheck.py`, `tests/plugins/test_install_common.py`

## Open Questions

Future work can decide whether MongoDB target resolution should absorb the compatibility scoring helpers now exposed by `capabilities.py`.
