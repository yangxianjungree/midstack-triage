---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/plugin-usage.spec.md
  - ../../specs/triage-workflow.spec.md
---

# Spec: Phase 1 Intake Environment Modes

## Objective

Make Phase 1 responsible for structured intake before remote validation:

- classify the start environment mode;
- identify missing required inputs;
- write follow-up questions that the slash-command adapter can present to the user;
- keep the current SSH remote development/test path as the default and only fully implemented live path.

## Assumptions

1. `remote` remains the default `/midstack:start` mode and keeps requiring environment IP, username, and password.
2. `local` means the agent/runtime is already on the fault cluster or control host. It is recognized in Phase 1, but live local collection remains blocked until a local executor exists.
3. `offline` means the user has existing incident, fixture, remote-run, logs, or command output. It is recognized in Phase 1, but `/start` does not execute collection; the user is guided to provide artifacts for offline analyse.
4. This slice does not implement local collection, ToDesk-style iterative command execution, or production SRE platform adapters.

## Success Criteria

- `src/phases/phase1/intake.py` owns Phase 1 input completeness and environment-mode classification.
- `/midstack:start` writes `phase1-intake.yaml`.
- Blocked `/midstack:start` outputs include `follow_up_questions` and actionable `next_actions`.
- Remote ready behavior remains compatible with the existing start flow.
- `local` and `offline` starts no longer demand SSH credentials, but they block with explicit mode-specific guidance.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py src/commands/plugin_cli.py
git diff --check
```

## Boundaries

- Always: preserve remote SSH as the default main path.
- Always: avoid writing secrets into intake summaries or follow-up prompts.
- Ask first: making local or offline `start` return ready.
- Never: add ad-hoc SSH, kubectl, database clients, or analysis work to the slash-command layer.

## Tasks

- [x] Task: Add Phase 1 intake contract
  - Acceptance: pure intake tests cover remote missing input, local mode, and offline mode.
  - Verify: `python3 -m pytest tests/phases/phase1 -q`
  - Files: `src/phases/phase1/intake.py`, `tests/phases/phase1/test_intake.py`
- [x] Task: Wire start command to intake output
  - Acceptance: blocked start writes follow-up questions; ready remote path remains compatible.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `src/commands/plugin_cli.py`, `plugins/cursor/commands/midstack:start.md`

## Open Questions

Future slices should decide:

- how to auto-detect local Kubernetes context safely;
- how ToDesk/manual-command mode stores iterative command requests and pasted outputs;
- whether production/SRE platform intake should be a separate execution mode or an adapter profile over offline/local evidence.
