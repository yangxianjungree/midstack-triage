---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Python Runtime Version Contract

## Objective

Close the Python 3.8 compatibility ambiguity from the Phase 4 architecture review by declaring one project runtime floor.

Decision: Midstack local/plugin runtime requires Python 3.10+. Remote third-stage collection scripts keep their stricter jump-host compatibility rule and remain Python 3.6-compatible where documented.

## Tech Stack

- Python 3.10+ for repository tools, `src/` runtime, validators, replay tools and plugin-local runtime wrappers.
- Remote collection scripts may run on constrained jump hosts and continue to avoid Python 3.7+ syntax unless a script contract explicitly raises that floor.

## Commands

```bash
python3 tools/validators/validate-repo.py
python3 -m py_compile $(find src tools plugins/claude/runtime/bin plugins/cursor -type f -name '*.py')
git diff --check
```

## Project Structure

- `README.md` declares the local/plugin Python floor.
- `docs/project/testing-and-install-gates.md` declares the same gate.
- `plugins/*/README.md` declare adapter install prerequisites.
- `docs/specs/plugin-runtime.spec.md` keeps remote script compatibility separate from local/plugin runtime compatibility.

## Code Style

No compatibility backport in this slice. PEP 604 type syntax is allowed in local/plugin runtime code:

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ...
```

## Testing Strategy

Use repository validators and Python bytecode compilation to catch syntax/runtime drift under the declared interpreter.

## Boundaries

- Always: keep local/plugin runtime and remote jump-host script requirements documented separately.
- Ask first: lowering the local/plugin runtime floor below Python 3.10.
- Never: imply remote collection scripts can use PyYAML or Python 3.10-only syntax by default.

## Success Criteria

- README and install-gate docs explicitly state Python 3.10+ for local/plugin runtime.
- Plugin runtime spec continues to state Python 3.6-compatible remote script constraints.
- No code is backported solely for Python 3.8 in this slice.

## Open Questions

- None for this slice.
