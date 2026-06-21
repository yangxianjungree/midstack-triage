# Contributing

Thanks for considering a contribution. Midstack Triage is a production incident diagnosis framework, so changes must preserve evidence quality, read-only execution defaults, and adapter runtime boundaries.

## Development Setup

Use Python 3.10+.

```bash
python3 -m pip install -r requirements-dev.txt
```

Optional dependencies:

- Claude Code CLI for Claude plugin install checks
- Cursor Agent environment for Cursor adapter testing
- `sshpass`, `ssh`, `scp`, `kubectl`, and a test cluster for live remote collection checks
- `anthropic` and `ANTHROPIC_API_KEY` for real Phase 4 Claude API reasoning

## Before You Start

Read these first:

- [README.md](README.md)
- [docs/README.md](docs/README.md)
- [docs/concepts/architecture.md](docs/concepts/architecture.md)
- [docs/guides/add-domain.md](docs/guides/add-domain.md)
- [docs/specs/plugin-runtime.spec.md](docs/specs/plugin-runtime.spec.md)
- [docs/specs/README.en.md](docs/specs/README.en.md)
- [docs/project/testing-and-install-gates.md](docs/project/testing-and-install-gates.md)

If the change affects schemas, templates, taxonomy values, command behavior, incident layout, runtime compatibility, or adapter contracts, update the L1 source of truth first as described in [docs/README.md](docs/README.md).

## Validation

For normal development:

```bash
python3 tools/validators/validate-repo.py
git diff --check
```

For smaller slices, run the closest focused tests first, then run the full gate before opening a pull request when practical.

Common focused checks:

```bash
python3 -m pytest tests/plugins/claude tests/plugins/cursor -q
python3 -m pytest tests/phases tests/shared tests/execution -q
python3 tools/validators/validate-fixture-hygiene.py
python3 tools/validators/validate-scenario-routing.py
```

## Contribution Rules

- Keep changes small and scoped to one logical concern.
- Preserve the control-plane / execution-plane boundary.
- Keep slash commands and adapter rules as thin entrypoints into installed runtime wrappers.
- Do not add high-risk production mutations to default flows.
- New collection scripts must be read-only by default and must declare metadata in the script manifest.
- New incident evidence must be structured, attributable, and safe to replay.
- Do not commit generated incident directories, raw customer data, credentials, kubeconfigs, private keys, or local sandbox output.
- Prefer documentation IP ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) in public examples.

## Adding a Middleware Domain

Use the MongoDB domain as the current complete reference. Follow [docs/guides/add-domain.md](docs/guides/add-domain.md) for skeleton, contract-path, and Active MVP expectations.

## Pull Requests

Every pull request should include:

- Summary of changed behavior or documentation
- Validation commands and results
- Security or data-sensitivity notes when relevant
- Any intentional limitations or follow-up work

Do not include real incident logs, credentials, private infrastructure identifiers, or screenshots with sensitive details.
