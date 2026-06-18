---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/incident-record.spec.md
  - ../2026-06-18-phase1-offline-artifact-intake/spec.md
---

# Spec: Phase 1 Manual Evidence Capture

## Objective

Support ToDesk/manual-offline starts by preserving pasted command output or
screen text as raw evidence without pretending it is a complete analysed artifact
set.

## Assumptions

1. Pasted evidence is raw input, not governed `structured_record` /
   `signal_bundle` / `collection_report`.
2. `/start --environment-mode offline --pasted-evidence <text>` writes the raw
   text under `logs/raw/` and keeps the incident `blocked`.
3. The user must still provide a complete `--artifact-source` or a future
   normalization step before `/analyse --execution-mode offline` can complete.
4. This slice does not parse commands, infer signals, or run local/remote tools.

## Success Criteria

- CLI accepts `--pasted-evidence`.
- Offline/manual start with pasted evidence writes `logs/raw/manual-evidence.txt`.
- `phase1-intake.yaml.manual_evidence.status=captured`.
- The incident remains `blocked` with an actionable next step.
- No `structured_record.yaml`, `signal_bundle.yaml`, or `collection_report.yaml`
  is generated from pasted text.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/phases/phase1/intake.py src/commands/start.py src/commands/plugin_cli.py
git diff --check
```

## Boundaries

- Always: store pasted evidence as raw evidence only.
- Always: keep analyse blocked until governed artifact files exist.
- Ask first: parsing pasted output into structured signals.
- Never: execute commands from pasted text.

## Tasks

- [x] Task: Add intake field and CLI parameter
  - Acceptance: intake records `manual_evidence.status=captured` when text is present.
  - Verify: `python3 -m pytest tests/phases/phase1 -q`
  - Files: `src/phases/phase1/intake.py`, `src/commands/plugin_cli.py`, `tests/phases/phase1/test_intake.py`
- [x] Task: Persist raw manual evidence during start
  - Acceptance: start writes `logs/raw/manual-evidence.txt` and remains blocked.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document manual evidence capture
  - Acceptance: runtime and incident specs clarify raw-only behavior.
  - Verify: `git diff --check`
  - Files: `docs/specs/plugin-runtime.spec.md`, `docs/specs/incident-record.spec.md`
