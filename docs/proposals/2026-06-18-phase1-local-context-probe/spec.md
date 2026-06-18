---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-environment-modes/spec.md
  - ../2026-06-18-phase1-intake-scenario-classification/spec.md
---

# Spec: Phase 1 Local Context Probe

## Objective

Help Phase 1 identify when the runtime may already be on a fault-cluster or
control-plane machine by recording a lightweight local Kubernetes context probe.
The result should guide the next follow-up question without turning local mode
into an implemented executor.

## Assumptions

1. `remote` remains the default and only ready live path.
2. Local probing is only a hint for intake, not evidence collection.
3. Local probing may run when remote access fields are missing or when the user
   explicitly selects `local`.
4. A usable local `kubectl` context does not prove this is the target fault
   cluster; the user must still confirm or provide an artifact path.

## Success Criteria

- `/start` records `phase1-intake.yaml.local_context`.
- When no remote IP is provided and a local kubectl context is available, the
  environment-mode follow-up question mentions that local context as a possible
  `local` path.
- `local` mode still returns `blocked` until a local executor exists.
- The normal remote ready path does not run local probing.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/phases/phase1/local_context.py src/commands/start.py
git diff --check
```

## Boundaries

- Always: treat the local context result as an intake hint only.
- Always: use short timeouts and do not collect Kubernetes objects.
- Ask first: implementing local live collection or local analyse.
- Never: return `ready` for local mode in this slice.

## Tasks

- [x] Task: Add local context probe helper
  - Acceptance: helper reports missing kubectl, available context, and configured-but-unreachable context without touching the cluster for object collection.
  - Verify: `python3 -m pytest tests/phases/phase1/test_local_context.py -q`
  - Files: `src/phases/phase1/local_context.py`, `tests/phases/phase1/test_local_context.py`
- [x] Task: Surface local context in start intake
  - Acceptance: blocked remote starts with no IP record `local_context` and ask a local-aware environment-mode follow-up when kubectl context is available.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `src/phases/phase1/intake.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document completed behavior
  - Acceptance: runtime/workflow specs mention local context probing as a Phase 1 hint.
  - Verify: `git diff --check`
  - Files: `docs/specs/plugin-runtime.spec.md`, `docs/specs/triage-workflow.spec.md`, `docs/proposals/2026-06-18-phase1-local-context-probe/spec.md`
