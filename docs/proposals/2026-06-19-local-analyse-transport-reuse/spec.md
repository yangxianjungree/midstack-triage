---
status: proposed
last_updated: 2026-06-19
supersedes: none
superseded_by: none
related:
  - ../2026-06-19-phase1-phase2-boundary-and-local-execution/spec.md
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
---

# Spec: Local Analyse via Transport Reuse

## Objective

Enable `/midstack:analyse --execution-mode local` for ready local incidents by
reusing the existing Phase 3 script orchestration and replacing only the SSH
transport with a local subprocess/file-copy transport.

This keeps the architectural model explicit:

- `local` is the same live collection path as `remote` minus SSH.
- `remote` remains local execution plus SSH transport.
- `offline` remains artifact-only and is not deepened in this slice.

## Assumptions

1. `/start --environment-mode local` has already produced a ready incident with
   `local-config.yaml`.
2. The existing `remote-executor-*` result schema remains stable for this slice,
   even when the transport is local.
3. Local analyse may reuse `execution.remote.executor` as the current execution
   facade, provided transport selection is explicit.
4. Missing or unusable `local-config.yaml` should return structured `blocked`,
   not fall back to remote SSH.

## Success Criteria

- `execution.remote.executor` accepts an explicit local transport mode and runs
  existing collection scripts through local subprocesses.
- Phase 3 can invoke collection with local transport while preserving existing
  remote invocation behavior.
- Analyse incident mode uses `local-config.yaml` for
  `--execution-mode local`, and still uses `remote-config.yaml` for remote.
- Local analyse without `local-config.yaml` returns a structured blocked output.
- Remote and offline analyse behavior remains compatible.

## Commands

```bash
python3 -m pytest tests/execution/remote tests/phases/phase3 tests/tools/plugin/test_midstack_analyse.py tests/tools/plugin/test_midstack_local_workspace.py -q
python3 -m py_compile src/execution/remote/transport.py src/execution/remote/cli.py src/phases/phase3/remote_collection.py src/commands/analyse.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: keep remote SSH execution behavior compatible.
- Always: keep local analyse as live collection; offline remains existing
  artifact intake only.
- Always: keep slash-command code out of raw subprocess/kubectl details.
- Ask first: renaming `remote-executor-*` files or changing result schemas.
- Never: silently fall back from local to SSH, or from SSH to local.

## Tasks

- [x] Task: Add local transport adapter
  - Acceptance: local transport implements the existing transport protocol and
    can run shell commands plus copy files/directories under local paths.
  - Verify: `python3 -m pytest tests/execution/remote -q`
  - Files: `src/execution/remote/transport.py`, `tests/execution/remote/test_transport.py`
- [x] Task: Add explicit executor transport selection
  - Acceptance: executor CLI keeps remote default and accepts `--transport local`
    for local subprocess execution.
  - Verify: `python3 -m pytest tests/phases/phase3/test_collection.py -q`
  - Files: `src/execution/remote/cli.py`, `src/phases/phase3/remote_collection.py`, `tests/phases/phase3/test_collection.py`
- [x] Task: Route local analyse incidents through local config
  - Acceptance: local incident analyse uses `local-config.yaml`; missing local
    config blocks with a local-specific error.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_analyse.py tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/analyse.py`, `tests/tools/plugin/test_midstack_analyse.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Update runtime docs
  - Acceptance: workflow/runtime docs describe local start and local analyse as
    live collection without SSH.
  - Verify: `git diff --check`
  - Files: `docs/specs/triage-workflow.spec.md`, `docs/specs/plugin-runtime.spec.md`

## Open Questions

- Whether a later schema cleanup should rename remote-executor terms to a more
  neutral execution-run contract. This slice keeps the existing names to avoid
  broad schema churn.
