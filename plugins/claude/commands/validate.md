---
description: Validate the Midstack repository and Claude plugin wrapper
---

Validate the bundled Midstack Claude runtime from `${CLAUDE_PLUGIN_ROOT}`.
This command does not depend on the source repository checkout or repository
test fixtures.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/selfcheck.py"
```

Report pass/fail status and first actionable failures.
