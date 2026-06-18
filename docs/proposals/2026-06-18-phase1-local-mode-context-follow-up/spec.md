---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-local-context-probe/spec.md
---

# Spec: Phase 1 Local Mode Context Follow-Up

## Objective

Make the `local` start path more actionable by surfacing the lightweight
`local_context` probe in the follow-up question. The user should immediately
see whether the current machine appears to have a usable Kubernetes context.

## Assumptions

1. `local` remains blocked until a real local executor exists.
2. `local_context` is an intake hint only, not a readiness signal.
3. `probe_local_context` may return `available`, `unavailable`, or `unreachable`.
4. This slice does not add local collection or change how `local` is routed.

## Success Criteria

- `phase1-intake.yaml.local_context` is preserved for `local` mode.
- The `local` follow-up question mentions the detected context when available.
- The `local` follow-up question remains blocked and does not imply readiness.
- Remote and offline follow-up behavior remains unchanged.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py
git diff --check
```

## Boundaries

- Always: keep `local` blocked.
- Always: keep `local_context` a hint only.
- Ask first: implementing a real local executor.
- Never: turn `local_context` into a cluster truth source.

## Tasks

- [x] Task: Add local-mode context-aware follow-up
  - Acceptance: local mode follow-up mentions the current kubectl context when the probe finds one.
  - Verify: `python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/phases/phase1/intake.py`, `tests/phases/phase1/test_intake.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document the context-aware local prompt
  - Acceptance: runtime and workflow specs mention the local-mode hint.
  - Verify: `git diff --check`
  - Files: `docs/specs/plugin-runtime.spec.md`, `docs/specs/triage-workflow.spec.md`, `docs/proposals/2026-06-18-phase1-local-mode-context-follow-up/spec.md`
