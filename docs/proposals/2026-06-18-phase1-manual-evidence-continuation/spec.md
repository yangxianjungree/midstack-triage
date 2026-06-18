---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-continuation/spec.md
  - ../2026-06-18-phase1-manual-evidence-capture/spec.md
---

# Spec: Phase 1 Manual Evidence Continuation

## Objective

Keep Phase 1 continuation lossless for manually pasted evidence. When a blocked
offline/manual incident is resumed with the same `incident_id`, previously saved
raw evidence must remain part of the intake state even if the user is only
answering a later follow-up question.

## Assumptions

1. Pasted evidence remains raw-only and is still stored at
   `logs/raw/manual-evidence.txt`.
2. Continuation should reuse the prior `manual_evidence_ref` from `input.yaml`
   when no new `--pasted-evidence` is supplied.
3. New `--pasted-evidence` replaces the raw manual evidence file for that
   incident.
4. This slice does not normalize manual evidence into governed analysis files.

## Success Criteria

- A second `/start --incident-id <id>` call preserves
  `input.yaml.manual_evidence_ref`.
- `phase1-intake.yaml.manual_evidence.status` remains `captured` across
  continuation.
- The raw evidence file remains under `logs/raw/manual-evidence.txt`.
- The incident remains `blocked` until a complete offline artifact directory or
  future normalization step exists.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py
git diff --check
```

## Boundaries

- Always: preserve existing raw evidence refs on same-incident continuation.
- Always: keep pasted evidence raw-only.
- Ask first: appending multiple pasted evidence blobs or introducing an evidence
  normalization contract.
- Never: generate `structured_record.yaml`, `signal_bundle.yaml`, or
  `collection_report.yaml` from pasted text in this slice.

## Tasks

- [x] Task: Preserve manual evidence during start continuation
  - Acceptance: repeated start with the same incident id keeps the raw evidence ref and captured status.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py::test_start_manual_offline_continuation_preserves_raw_evidence_ref -q`
  - Files: `src/commands/start.py`, `src/phases/phase1/intake.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document completed behavior
  - Acceptance: proposal status is completed after verification.
  - Verify: `git diff --check`
  - Files: `docs/proposals/2026-06-18-phase1-manual-evidence-continuation/spec.md`
