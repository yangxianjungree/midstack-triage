---
status: proposed
last_updated: 2026-06-19
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-environment-modes/spec.md
  - ../2026-06-18-phase1-local-context-probe/spec.md
---

# Spec: Phase 1/2 Boundary and Local Execution

## Objective

Re-cut `/start` around the intended workflow boundary:

- Phase 1 decides whether to create or continue an incident record and preserves
  initial user memory/context.
- Phase 2 owns input completion, access readiness checks, environment probing,
  and object inventory gates.
- `local` should become the same execution shape as `remote` minus the SSH
  transport layer. Conversely, `remote` is `local` plus an SSH transport.

Offline/manual paths remain documented but are not deepened in this slice.

## Assumptions

1. `/midstack:start` remains the user-facing command that orchestrates Phase 1
   and Phase 2 together.
2. The first implementation slice should preserve current external behavior
   while moving readiness logic into Phase 2.
3. `remote` remains the default supported path during the boundary refactor.
4. `local` will be implemented incrementally after the Phase 2 gate exists.
5. No new offline behavior should be added while this proposal is active.

## Success Criteria

- Phase 2 exposes a startup/readiness gate that owns:
  - local context probing;
  - remote environment validation;
  - MongoDB namespace/object inventory blockers;
  - follow-up questions derived from post-intake blockers.
- `src/commands/start.py` delegates Phase 2 readiness instead of directly
  containing SSH/kubectl validation and MongoDB inventory branching.
- Existing remote start behavior stays compatible.
- Local mode remains blocked until the next local-executor slice, but its
  readiness state is produced by Phase 2 rather than Phase 1 command glue.
- Specs explain the new Phase 1 vs Phase 2 contract.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/phases/phase2 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/commands/start.py src/phases/phase1/intake.py src/phases/phase2/startup_gate.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: keep `/midstack:start` as the orchestration command.
- Always: keep remote SSH behavior compatible while refactoring boundaries.
- Always: treat local as the same logical collection path as remote without SSH.
- Ask first: changing offline/manual evidence behavior.
- Ask first: making local analyse execute real collection before the startup
  local gate is in place.
- Never: hide readiness failures by returning `ready`.

## Tasks

- [x] Task: Extract Phase 2 startup readiness gate
  - Acceptance: remote validation, local context probing, and MongoDB inventory blockers are produced by `phases.phase2.startup_gate`.
  - Verify: `python3 -m pytest tests/phases/phase2 tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/phases/phase2/startup_gate.py`, `src/commands/start.py`, `tests/phases/phase2/test_startup_gate.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document Phase 1/2 boundary
  - Acceptance: workflow/runtime specs describe Phase 1 as incident creation/continuation and Phase 2 as information completion plus readiness checks.
  - Verify: `git diff --check`
  - Files: `docs/specs/triage-workflow.spec.md`, `docs/specs/plugin-runtime.spec.md`
- [x] Task: Prepare local execution contract
  - Acceptance: proposal and specs define local as remote-minus-SSH and identify the next implementation slice.
  - Verify: `git diff --check`
  - Files: `docs/proposals/2026-06-19-phase1-phase2-boundary-and-local-execution/spec.md`

## Open Questions

- Whether the local executor should reuse the remote executor CLI with a local
  transport adapter, or get a separate CLI facade over the same script runner.
- Whether Phase 2 should eventually own all missing-input prompts, or only
  command-backed readiness prompts. This proposal starts by moving the
  command-backed gates first.
