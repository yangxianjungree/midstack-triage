---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Pulsar Support State Alignment

## Objective

Make Pulsar's support state match the implementation: assets, one golden path and a rules analyser exist, but Pulsar is not an Active MVP equal to MongoDB.

Decision: Pulsar remains `Skeleton / contract path`. It may stay registered in Phase 4 rules for replay and contract validation, but public status must not imply production Active MVP support.

## Tech Stack

- Runtime status lives in `src/phases/phase4/rules/__init__.py`.
- User-facing status lives in README, implementation status and Pulsar domain docs.

## Commands

```bash
python3 -m pytest tests/tools/plugin/test_midstack_analyse.py -q
python3 tools/replay/pulsar-replay.py --run-analyse
python3 tools/validators/validate-repo.py --skip-score
git diff --check
```

## Project Structure

- `src/phases/phase4/rules/__init__.py` exposes both registered analysers and support states.
- `README.md` and `docs/project/implementation-status.md` explain the difference between Active MVP and contract path.
- `domains/pulsar/README.md` records the current Pulsar boundary.

## Code Style

Use plain data structures for support state; do not introduce a framework.

```python
def middleware_support_state(middleware: str) -> str:
    return _SUPPORT_STATES.get(middleware, "unsupported")
```

## Testing Strategy

Add focused tests around `supported_middlewares()` and the user-facing unsupported middleware message so future changes cannot silently blur support status.

## Boundaries

- Always: distinguish "rules analyser exists" from "Active MVP".
- Ask first: promoting Pulsar to Active MVP.
- Never: remove Pulsar golden path or rules analyser as part of this status-only slice.

## Success Criteria

- Pulsar remains runnable through existing replay/contract tests.
- Docs call Pulsar `Skeleton / contract path`, not Active MVP.
- Code has a stable place to query support state.

## Open Questions

- What exact gates promote Pulsar from contract path to Active MVP? Out of scope for this slice.
