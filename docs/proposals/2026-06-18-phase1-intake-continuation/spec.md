---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/plugin-usage.spec.md
  - ../../specs/triage-workflow.spec.md
  - ../2026-06-18-phase1-intake-environment-modes/spec.md
---

# Spec: Phase 1 Intake Continuation

## Objective

Make blocked Phase 1 intake records resumable so the user can answer follow-up
questions without starting a new incident or restating already captured context.

## Assumptions

1. Default `/midstack:start` without `incident_id` still creates a new incident.
2. `/midstack:start --incident-id <existing blocked incident>` means continue the
   same intake record and merge newly supplied answers with existing `input.yaml`
   and `remote-config.yaml`.
3. Runtime validation remains authoritative. The slash-command layer may omit
   fields and let Phase 1 return structured `blocked` output.
4. This slice does not implement local live collection, offline artifact ingestion
   from `/start`, or a separate interactive command loop.

## Success Criteria

- A blocked remote start with host/clue but missing credentials can be continued
  with the same `incident_id` and only the missing credentials.
- Previously captured middleware, clue, environment IPs, namespace, cluster id,
  environment mode, and remote port are preserved unless explicitly replaced.
- CLI parsing no longer rejects missing `--middleware`; Phase 1 writes
  `missing_middleware` and follow-up questions instead.
- Remote ready behavior remains compatible with the current main path.

## Commands

```bash
python3 -m pytest tests/phases/phase1 tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/commands/start.py src/commands/plugin_cli.py src/phases/phase1/intake.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: keep `remote` as the only ready live path.
- Always: only merge prior values when `incident_id` is explicit.
- Ask first: changing `/start` into an interactive REPL or hidden prompt loop.
- Never: make the slash command layer inspect source code or run ad-hoc SSH.

## Tasks

- [x] Task: Make start continuation merge prior intake values
  - Acceptance: a second start call with the same incident id and missing answers can transition the incident from `blocked` to `ready`.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Let runtime own missing middleware validation
  - Acceptance: `midstack-local.py start` can return `missing_middleware` instead of argparse usage failure.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/plugin_cli.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Document continuation behavior
  - Acceptance: runtime, usage, workflow, and slash command docs tell agents to continue blocked starts with `--incident-id`.
  - Verify: `git diff --check`
  - Files: `docs/specs/*.spec.md`, `plugins/*/commands/*start*.md`

## Open Questions

- Whether a future adapter should implement a true conversational prompt loop, or
  keep the current explicit `follow_up_questions` + repeated `/start` model.
- Whether local and offline modes should use the same continuation mechanism once
  their executor/artifact intake paths are implemented.
