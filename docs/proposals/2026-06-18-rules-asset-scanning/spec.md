---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Shared Domain Asset Candidate Scanner

## Objective

Remove duplicate domain asset scanning from Phase 4 rules analyzers while keeping rules responsible only for analysis decisions.

Decision: add a small shared helper that returns knowledge candidates for a `(middleware, scenario)` pair by scanning runbook, command and skill metadata. MongoDB and Pulsar rules call that helper instead of each having local copy-pasted scanning code.

## Tech Stack

- Shared helper under `src/shared/`.
- Existing YAML IO via `shared.io.load_yaml_object`.
- Existing runtime root contract via `shared.workspace.runtime_root()`.

## Commands

```bash
python3 -m pytest tests/shared tests/phases/phase4/rules -q
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
python3 tools/replay/pulsar-replay.py --run-analyse
git diff --check
```

## Project Structure

- `src/shared/asset_resolver.py` owns metadata candidate scanning.
- `src/phases/phase4/rules/mongodb.py` keeps only scenario fallback mapping and delegates scanning.
- `src/phases/phase4/rules/pulsar.py` delegates scanning.
- Tests live under `tests/shared/` and rules tests.

## Code Style

Keep the helper narrow:

```python
def knowledge_candidates_for_scenario(middleware: str, scenario: str) -> List[Dict[str, str]]:
    ...
```

## Testing Strategy

Add shared helper tests for ordering, filtering and unknown/baseline scenarios. Existing replay/score gates prove generated `analysis.yaml` shape stays compatible.

## Boundaries

- Always: preserve existing candidate output fields.
- Ask first: replacing hard-coded rules logic with data-driven domain assets.
- Never: move causal analysis rules out of `src/phases/phase4/rules/` in this slice.

## Success Criteria

- MongoDB and Pulsar rules no longer implement their own metadata-directory scan.
- Shared scanner is covered by focused tests.
- MongoDB score and Pulsar replay still pass.

## Open Questions

- Whether future rules should be fully represented as domain assets remains out of scope.
