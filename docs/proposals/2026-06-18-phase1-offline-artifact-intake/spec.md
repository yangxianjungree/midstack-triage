---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/plugin-usage.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-scenario-classification/spec.md
---

# Spec: Phase 1 Offline Artifact Intake

## Objective

Let `/midstack:start --environment-mode offline` become ready when the user
provides an existing local evidence directory that can be analysed offline.

This closes the first practical path for production/offline/ToDesk-style
scenarios without implementing local live collection or manual command loops.

## Assumptions

1. `remote` remains the default and only ready live-collection path.
2. `offline` start accepts an existing local artifact directory through
   `--artifact-source`.
3. A valid offline artifact directory must contain the files required by current
   offline analyse: `input.yaml`, `structured_record.yaml`, `signal_bundle.yaml`,
   and `collection_report.yaml`.
4. `/start` records the artifact reference and marks the incident `ready`; it
   does not copy artifact contents or execute analysis.
5. Manual pasted text, screenshots, and log-file ingestion remain future slices.

## Success Criteria

- Missing `--artifact-source` in offline mode still returns `blocked` with
  scenario-specific follow-up questions.
- Nonexistent artifact source returns `blocked`.
- Artifact source missing required offline files returns `blocked` and lists
  missing files.
- Valid artifact source creates a ready incident with:
  - `phase1-intake.yaml.offline_artifact.status=ready`
  - `input.yaml.artifact_source`
  - no `remote-config.yaml`
  - next action pointing to offline analyse.
- Offline analyse on that ready incident consumes `artifact_source` and copies
  the collected input files into the incident directory before analysis.
- Remote start behavior remains unchanged.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py src/commands/plugin_cli.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: resolve artifact paths through workspace/runtime path helpers.
- Always: keep `/start` as intake only; analysis still runs through `/analyse`.
- Ask first: copying artifact directories into incident output.
- Ask first: accepting pasted command output as first-class evidence.
- Never: run local or remote collection commands from offline start.

## Tasks

- [x] Task: Add offline artifact-source CLI and intake validation
  - Acceptance: pure tests cover missing, nonexistent, incomplete, and valid artifact sources.
  - Verify: `python3 -m pytest tests/phases/phase1 -q`
  - Files: `src/phases/phase1/intake.py`, `src/commands/plugin_cli.py`, `tests/phases/phase1/test_intake.py`
- [x] Task: Wire ready offline start output
  - Acceptance: valid artifact source produces ready incident without remote config and points to offline analyse.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Let offline analyse consume start artifact references
  - Acceptance: a ready offline incident with `input.yaml.artifact_source` completes `analyse --execution-mode offline`.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_analyse.py::MidstackAnalyseTest::test_analyse_offline_incident_uses_artifact_source_from_start -q`
  - Files: `src/commands/analyse.py`, `tests/tools/plugin/test_midstack_analyse.py`
- [x] Task: Document offline artifact intake
  - Acceptance: runtime/usage specs and slash command docs mention `--artifact-source`.
  - Verify: `git diff --check`
  - Files: `docs/specs/*.spec.md`, `plugins/*/commands/*start*.md`

## Open Questions

- Whether future start should copy or snapshot artifact directories for
  reproducibility.
- Whether manual pasted text should become an artifact file under the incident
  directory or a separate command loop.
