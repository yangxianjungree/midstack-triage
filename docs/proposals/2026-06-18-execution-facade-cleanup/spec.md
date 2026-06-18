---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Execution Facade Cleanup

## Objective

Close the small P2 architecture debt around execution-plane import ambiguity without changing remote execution behavior.

Decision: split remote executor CLI parsing/orchestration into `src/execution/remote/cli.py`, keep `src/execution/remote/executor.py` as the compatibility facade for existing imports and `python -m execution.remote.executor`. For kubectl, keep only `src/phases/phase2/kubectl.py` as the Phase 2 compatibility wrapper over `src/execution/remote/kubectl.py`.

## Tech Stack

- Python runtime under `src/execution/remote/`.
- Existing `RemoteTransport` interface and remote executor contract files.
- Existing Phase 2 inventory tests and remote executor validator.

## Commands

```bash
python3 -m pytest tests/phases/phase2 tests/phases/phase3/test_collection.py tests/execution/remote -q
python3 tools/validators/validate-remote-executor.py
python3 -m py_compile src/execution/remote/executor.py src/execution/remote/cli.py src/phases/phase2/inventory.py src/phases/phase2/__init__.py
git diff --check
```

## Project Structure

- `src/execution/remote/executor.py`: compatibility facade plus script execution helpers.
- `src/execution/remote/cli.py`: argparse and batch executor CLI orchestration.
- `src/phases/phase2/kubectl.py`: the only Phase 2 kubectl compatibility wrapper.
- `src/phases/phase2/inventory.py`: consumes the wrapper directly, no extra local forwarding function.

## Code Style

Keep compatibility wrappers explicit and lazy to avoid circular imports:

```python
def main(argv=None):
    from execution.remote.cli import main as cli_main
    return cli_main(argv)
```

## Testing Strategy

Reuse existing remote executor validator and Phase 2/3 tests. No live remote execution is required because this slice changes module boundaries only.

## Boundaries

- Always: preserve `python -m execution.remote.executor`.
- Ask first: changing remote executor request/result schema or error status semantics.
- Never: refactor capability checks or script execution flow in this slice.

## Success Criteria

- CLI code no longer lives in `executor.py`.
- Phase 2 kubectl has one compatibility wrapper layer.
- Existing remote executor and phase tests pass.

## Open Questions

- Further splitting of `run_script()` and capability validation remains a larger execution-plane refactor and needs live remote regression planning.
