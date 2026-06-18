---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-phase4-reasoning-convergence/proposal.md
  - ../../concepts/architecture.md
  - ../../specs/plugin-runtime.spec.md
---

# Spec: Runtime Root / Workspace Root Contract

## Assumptions

1. Runtime assets and user workspace output are separate concepts.
2. `MIDSTACK_TRIAGE_RUNTIME_ROOT` is the asset root for packaged runtime or source checkout.
3. `MIDSTACK_TRIAGE_WORKSPACE` is the user workspace root for `.local/incidents`, current incident markers, and relative user paths.
4. Engineering tools under `tools/` may keep their own repo-root helpers; this spec targets installed/runtime modules under `src/`.

## Objective

Unify runtime path resolution so executor, scenario router, skill resolver, and Phase 4 rules read assets from the same runtime root while command output continues to use workspace root.

Success means packaged runtime can set one runtime root and all runtime modules resolve:

- `core/routing/scenario-signal-map.yaml`
- `domains/<middleware>/skills/**`
- `domains/<middleware>/scripts/manifest.yaml`
- `interfaces/plugin/script-runtime-map.example.yaml`
- `domains/<middleware>/{runbooks,commands,skills}/**/metadata.yaml`

## Tech Stack

- Python runtime modules under `src/`
- Environment variables:
  - `MIDSTACK_TRIAGE_RUNTIME_ROOT`
  - `MIDSTACK_TRIAGE_WORKSPACE`
- Tests: `pytest`

## Commands

```bash
python3 -m pytest tests/shared/test_workspace_roots.py tests/shared/test_scenario_router.py tests/shared/test_skill_resolver.py tests/execution/remote/test_runtime_support.py -q
python3 -m pytest tests/phases/phase4/rules/test_mongodb_rules.py tests/tools/plugin/test_midstack_analyse.py -q
python3 tools/validators/validate-repo.py
git diff --check
```

## Project Structure

```text
src/shared/workspace.py                 -> root contract source
src/shared/scenario_router.py           -> routing map consumer
src/shared/skill_resolver.py            -> domain asset consumer
src/execution/remote/runtime_support.py -> remote runtime asset consumer
src/phases/phase4/rules/*.py            -> rules asset scanners
tests/shared/test_workspace_roots.py    -> contract tests
```

## Code Style

Prefer explicit root helpers over module-level ad hoc `parents[...]` roots:

```python
def runtime_root() -> Path:
    value = os.environ.get("MIDSTACK_TRIAGE_RUNTIME_ROOT", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return source_root()


def workspace_root() -> Path:
    value = os.environ.get("MIDSTACK_TRIAGE_WORKSPACE", "").strip()
    if value:
        return Path(value).expanduser().resolve()
    return runtime_root()
```

Module constants may cache the result at import time only when tests can reload the module after env changes.

## Testing Strategy

| Level | What | Where |
| --- | --- | --- |
| Unit | env var precedence and fallback behavior | `tests/shared/test_workspace_roots.py` |
| Integration | scenario router / skill resolver use runtime root | `tests/shared/test_scenario_router.py`, `tests/shared/test_skill_resolver.py` |
| Integration | remote executor defaults use runtime root | `tests/execution/remote/test_runtime_support.py` |
| Regression | analyse command still writes workspace outputs | `tests/tools/plugin/test_midstack_analyse.py` |

## Boundaries

- Always: Keep `MIDSTACK_TRIAGE_WORKSPACE` behavior for output paths.
- Always: Keep source checkout fallback working without env vars.
- Ask first: Renaming env vars or changing plugin wrapper contracts.
- Never: Make installed runtime depend on source checkout paths.
- Never: Move engineering `tools/` root helpers into runtime contract in this slice.

## Plan

1. Add root helpers to `src/shared/workspace.py`.
2. Update runtime modules to consume `runtime_root()` / `source_root()` instead of local ad hoc roots.
3. Add tests that simulate split runtime root and workspace root.
4. Run targeted runtime and command tests.

## Tasks

- [x] Task: Add shared root helpers
  - Acceptance: `runtime_root()`, `workspace_root()`, `source_root()` are explicit and tested.
  - Verify: `python3 -m pytest tests/shared/test_workspace_roots.py -q`
  - Files: `src/shared/workspace.py`, `tests/shared/test_workspace_roots.py`
- [x] Task: Route runtime asset consumers through shared root contract
  - Acceptance: scenario router, skill resolver, remote runtime defaults, and rules asset scanners agree on runtime root.
  - Verify: `python3 -m pytest tests/shared/test_scenario_router.py tests/shared/test_skill_resolver.py tests/execution/remote/test_runtime_support.py tests/phases/phase4/rules/test_mongodb_rules.py -q`
  - Files: `src/shared/scenario_router.py`, `src/shared/skill_resolver.py`, `src/execution/remote/runtime_support.py`, `src/phases/phase4/rules/mongodb.py`, `src/phases/phase4/rules/pulsar.py`
- [x] Task: Confirm command output remains workspace-rooted
  - Acceptance: relative output paths still resolve under `MIDSTACK_TRIAGE_WORKSPACE`.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_analyse.py tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: tests only if existing assertions need tightening

## Open Questions

None for this slice. Future work may decide whether tools should also use a formal repo-root helper.
