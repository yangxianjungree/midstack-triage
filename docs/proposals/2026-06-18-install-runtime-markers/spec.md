---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Shared Install Runtime Markers

## Objective

Close the Claude/Cursor install gate drift where each adapter owns a separate runtime marker list.

Decision: common runtime payload markers live in `plugins/support/install_common.py`. Claude and Cursor may prepend adapter-specific wrapper markers, but shared `src/`, `tools/`, `domains/`, `core/` and `interfaces/` files must come from one helper.

## Tech Stack

- Python installer helpers under `plugins/support/`.
- Claude installer prefixes the common markers with `runtime/`.
- Cursor installer uses the common markers directly.

## Commands

```bash
python3 -m pytest tests/plugins/test_install_common.py tests/plugins/claude/test_claude_plugin_install.py tests/plugins/cursor/test_cursor_plugin_install.py -q
python3 plugins/cursor/plugin-install.py --check-manifest
git diff --check
```

## Project Structure

- `plugins/support/install_common.py` owns common marker constants and prefix helper.
- `plugins/claude/plugin-install.py` keeps only Claude wrapper markers plus prefixed common markers.
- `plugins/cursor/plugin-install.py` keeps only Cursor wrapper markers plus common markers.

## Code Style

Use immutable tuples and simple helpers:

```python
def prefixed_runtime_markers(prefix: str = "") -> Tuple[str, ...]:
    ...
```

## Testing Strategy

Extend existing install-common tests to prove prefixing and required shared markers. Reuse existing Claude/Cursor installer tests.

## Boundaries

- Always: common runtime implementation markers have one source of truth.
- Ask first: changing installed runtime directory layout.
- Never: change install commands or workspace state schema in this slice.

## Success Criteria

- Claude/Cursor marker checks share the same common runtime marker list.
- New shared runtime dependencies are included in marker checks.
- Existing plugin installer tests pass.

## Open Questions

- Whether Claude `runtime/bin/selfcheck.py` should import this helper at runtime is left for a later installer selfcheck consolidation.
