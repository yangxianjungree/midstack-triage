---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-environment-modes/spec.md
---

# Spec: Phase 1 Blocked Follow-Up Completeness

## Objective

Make `/start` blocked outputs consistently actionable. Any Phase 1/2 blocker
created after intake, including remote validation failures and MongoDB namespace
inventory blockers, should add a matching `follow_up_questions` entry so the
slash-command adapter can ask the user exactly what is needed next.

## Assumptions

1. `blocking_items` remain the machine-readable authority for why the start is
   blocked.
2. `follow_up_questions` are user-facing prompts derived from blocking items.
3. Remote validation remains in `start`; this slice only improves the output
   contract when validation or inventory blocks.
4. Existing ready remote and offline flows must not change.

## Success Criteria

- Remote validation failure includes a follow-up question for remote access.
- Multiple MongoDB namespaces include a namespace follow-up question with
  candidate names.
- MongoDB namespace not found includes a namespace follow-up question asking for
  the target namespace or corrected middleware/access context.
- `adapter-output.yaml.next_actions` mirrors the new follow-up questions.

## Commands

```bash
python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/commands/start.py
git diff --check
```

## Boundaries

- Always: keep `blocking_items` stable and explicit.
- Always: keep prompts free of passwords or secret values.
- Ask first: changing Phase 2 inventory discovery semantics.
- Never: hide a blocker by returning `ready` when validation or inventory failed.

## Tasks

- [x] Task: Add follow-up prompts for post-intake start blockers
  - Acceptance: remote validation failure, namespace ambiguity, and namespace not found all include follow-up questions and next actions.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Mark proposal complete
  - Acceptance: proposal status and task list reflect verified implementation.
  - Verify: `git diff --check`
  - Files: `docs/proposals/2026-06-18-phase1-blocked-follow-up-completeness/spec.md`
