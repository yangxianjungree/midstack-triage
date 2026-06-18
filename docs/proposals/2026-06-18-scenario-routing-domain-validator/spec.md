---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
related:
  - ../2026-06-18-phase4-reasoning-convergence/proposal.md
  - ../../specs/scenario-routing.spec.md
  - ../../concepts/architecture.md
---

# Spec: Scenario / Routing / Domain Assets Validator

## Assumptions

1. `scenarios/<scenario>/scenario.yaml` declares which middleware a scenario applies to.
2. `core/routing/scenario-signal-map.yaml` declares which scenario/middleware pairs can be routed automatically.
3. `domains/<middleware>/runbooks|skills|commands/**/metadata.yaml` declares implemented domain assets for a scenario.
4. A scenario/middleware pair may be skeleton only, but it must say so explicitly instead of becoming an implicit routing dead end.

## Objective

Add a repository validator that checks scenario metadata, routing map, and domain assets are mutually consistent.

The first bug it must catch is the `queue-backlog` mismatch: scenario metadata declares MongoDB applicability, but routing and MongoDB domain assets do not implement that scenario.

## Tech Stack

- Python validator under `tools/validators/`
- YAML parsing via existing `tools/support/common.py`
- Tests via `pytest`

## Commands

```bash
python3 -m pytest tests/tools/validators/test_validate_scenario_routing.py -q
python3 tools/validators/validate-scenario-routing.py
python3 tools/validators/validate-repo.py
git diff --check
```

## Project Structure

```text
tools/validators/validate-scenario-routing.py        -> thin CLI wrapper
tools/validators/scenario_routing_validator.py       -> validator implementation
tests/tools/validators/test_validate_scenario_routing.py -> validator unit tests
scenarios/*/scenario.yaml                            -> scenario applicability source
core/routing/scenario-signal-map.yaml                -> routing source
domains/<middleware>/{runbooks,skills,commands}/     -> domain asset source
```

## Code Style

Return structured findings from pure functions, and keep CLI printing simple:

```python
def validate_contract(root: Path) -> list[str]:
    errors: list[str] = []
    ...
    return errors
```

Use YAML parsing and metadata fields; do not infer support from directory names alone when metadata exists.

## Testing Strategy

| Level | What | Where |
| --- | --- | --- |
| Unit | mismatched scenario/middleware pair is reported | `tests/tools/validators/test_validate_scenario_routing.py` |
| Unit | route without scenario metadata is reported | `tests/tools/validators/test_validate_scenario_routing.py` |
| Unit | implemented pairs in current repo pass | `tests/tools/validators/test_validate_scenario_routing.py` |
| Integration | validator runs in repo gate | `tools/validators/validate-repo.py` |

## Boundaries

- Always: Detect scenario metadata ↔ routing map ↔ domain assets mismatch.
- Always: Keep existing scenario router tests in the validator command.
- Ask first: Adding new schema fields to every scenario.
- Never: Silently remove middleware from scenario metadata to make the validator pass without an architectural decision.
- Never: Require every scenario/middleware pair to be fully routed if explicitly marked skeleton.

## Contract

A scenario/middleware pair is valid when at least one of the following is true:

1. It has a route in `core/routing/scenario-signal-map.yaml` and at least one domain asset references that scenario.
2. It is explicitly listed as skeleton / unrouted in validator policy.

For the initial slice, explicit skeleton / unrouted pairs live in validator policy to avoid editing every scenario schema at once.

## Plan

1. Extract validator implementation from the current test-runner wrapper.
2. Add contract checks for:
   - scenario metadata pair missing routing;
   - scenario metadata pair missing domain assets;
   - routing pair missing scenario metadata;
   - routing pair missing domain assets.
3. Decide current repo mismatches explicitly:
   - remove incorrect MongoDB applicability from `queue-backlog`, because MongoDB has no queue-backlog route or assets today.
   - remove Pulsar routes from `kubernetes-runtime` and `resource-exhaustion`, because Pulsar scenario metadata and domain assets do not implement those pairs today.
4. Keep existing unit test execution as part of the validator command.

## Tasks

- [x] Task: Add validator implementation and tests
  - Acceptance: synthetic mismatch fixtures produce actionable errors.
  - Verify: `python3 -m pytest tests/tools/validators/test_validate_scenario_routing.py -q`
  - Files: `tools/validators/scenario_routing_validator.py`, `tests/tools/validators/test_validate_scenario_routing.py`
- [x] Task: Wire validator into existing CLI
  - Acceptance: `python3 tools/validators/validate-scenario-routing.py` runs contract checks and existing router/analyse tests.
  - Verify: `python3 tools/validators/validate-scenario-routing.py`
  - Files: `tools/validators/validate-scenario-routing.py`
- [x] Task: Fix current repo mismatch
  - Acceptance: `queue-backlog` no longer declares MongoDB until MongoDB route and assets exist; Pulsar routes only declare scenarios that Pulsar metadata and assets implement.
  - Verify: `python3 tools/validators/validate-repo.py`
  - Files: `scenarios/queue-backlog/scenario.yaml`, `core/routing/scenario-signal-map.yaml`

## Open Questions

Future work should decide whether skeleton/unrouted pairs belong in scenario metadata schema rather than validator policy.
