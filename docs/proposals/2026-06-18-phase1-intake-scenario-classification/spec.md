---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../presentation.md
  - ../../specs/triage-workflow.spec.md
  - ../../specs/plugin-runtime.spec.md
  - ../2026-06-18-phase1-intake-environment-modes/spec.md
---

# Spec: Phase 1 Intake Scenario Classification

## Objective

Record the high-level access scenario during Phase 1 so later slices can choose
the right questioning, executor, or artifact path without overloading
`execution_mode`.

## Scenario Contract

`phase1-intake.yaml` includes `intake_scenario`:

- `id`
- `environment_class`
- `access_pattern`
- `evidence_source`
- `readiness`

Current IDs:

- `remote_ssh`: default live SSH path for development/test and generic remote environments.
- `local_fault_cluster`: runtime is already on the fault cluster or control host; currently blocked until a local executor exists.
- `offline_existing_artifacts`: user has existing incident, fixture, remote-run, logs, or command output.
- `offline_production`: production/online/SRE clues with existing evidence or platform artifacts.
- `manual_guided_offline`: ToDesk/remote desktop/manual paste style flow.

## Success Criteria

- Remote start keeps `remote_ssh` and remains the only ready live path.
- Local mode records `local_fault_cluster` and remains blocked.
- Offline production clues are distinguished from generic artifact replay.
- Manual/ToDesk clues are distinguished from production platform artifacts.
- Offline follow-up questions are scenario-specific instead of using one generic
  artifact prompt for production and manual guided environments.
- Classification is pure intake logic; it does not run local commands, remote
  commands, filesystem scans, or platform adapters.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: use `execution_mode` for collection mechanics and `intake_scenario` for user/access context.
- Always: keep local/offline starts blocked until their execution or artifact intake path is implemented.
- Ask first: automatic local Kubernetes context probing.
- Never: infer production by executing commands against the target environment.

## Tasks

- [x] Task: Add pure Phase 1 scenario classification
  - Acceptance: unit tests cover remote, local, offline production, and manual offline clues.
  - Verify: `python3 -m pytest tests/phases/phase1 -q`
  - Files: `src/phases/phase1/intake.py`, `tests/phases/phase1/test_intake.py`
- [x] Task: Persist scenario classification in start output
  - Acceptance: `phase1-intake.yaml` includes `intake_scenario` on ready remote starts.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document the scenario contract
  - Acceptance: workflow/runtime specs explain the separation from `execution_mode`.
  - Verify: `git diff --check`
  - Files: `docs/specs/triage-workflow.spec.md`, `docs/specs/plugin-runtime.spec.md`
- [x] Task: Make offline follow-up prompts scenario-specific
  - Acceptance: production offline asks for alert/SRE references; manual offline asks for pasted output, screenshots, or logs.
  - Verify: `python3 -m pytest tests/phases/phase1 -q`
  - Files: `src/phases/phase1/intake.py`, `tests/phases/phase1/test_intake.py`

## Open Questions

- Whether production platform intake should become a separate adapter profile or
  remain an offline/local evidence source.
- Whether manual guided offline needs a dedicated command loop or can be served
  by repeated `/start` and incident-derived offline `/analyse` interactions.
