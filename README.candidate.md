# Midstack Triage

Midstack Triage is an AI-assisted incident triage framework for PaaS middleware.
It turns production troubleshooting knowledge for MongoDB, Pulsar, and similar
systems into reusable runbooks, commands, scripts, skills, and agent-facing
plugins.

The project is built for the gap between "an alert fired" and "someone has a
defensible diagnosis". It does read-only evidence collection, signal
normalization, hypothesis-driven analysis, and structured incident reporting.

## What It Does

- Standardizes middleware incident triage into a repeatable workflow
- Packages expert knowledge as runbooks, commands, skills, and scripts
- Exposes the workflow through agent plugins such as Claude Code and Cursor
- Preserves structured incident records for replay, review, and knowledge reuse
- Keeps LLM usage behind curated evidence rather than raw production exhaust

## What It Does Not Do

- It is not a monitoring or alerting system
- It is not a middleware control plane
- It does not auto-remediate production by default
- It does not assume unrestricted agent access to production environments
- It does not try to cover every middleware or every failure mode at once

## Current Support


| Middleware | Status     | Notes                                                                                  |
| ---------- | ---------- | -------------------------------------------------------------------------------------- |
| MongoDB    | Active MVP | End-to-end triage path, remote read-only collection, structured analysis, review loop  |
| Pulsar     | Skeleton   | Domain layout and sample assets exist, but the full diagnosis path is not yet complete |


Detailed status, validation scope, and in-progress work live in
[docs/project/implementation-status.md](docs/project/implementation-status.md).

## Runtime Architecture

Midstack exposes a small command surface and keeps the runtime split between a
control plane for orchestration and an execution plane for remote evidence
collection.

![Midstack runtime architecture](docs/concepts/diagrams/architecture-overview.png)

| Command | Phases | Execution? | Result |
| ------- | ------ | ---------- | ------ |
| `/midstack:start` | P1–P2 | No | `ready` / `blocked` |
| `/midstack:analyse` | P3–P5 | P3 + P4 | `report.md`, `knowledge_candidates` |
| `/midstack:review` | — | No | feedback score |

- Control plane: incident intake, state transitions, signal governance, phase-4 reasoning, and report assembly
- Execution plane: remote access, read-only script execution, artifact collection, and verification callbacks
- Future retrieval path: `knowledge_candidates` can feed a vector-backed recall layer without becoming a base runtime dependency

More detail:
- [docs/concepts/architecture-overview.md](docs/concepts/architecture-overview.md)
- [docs/concepts/architecture.md](docs/concepts/architecture.md)

## Quick Start

Current local testing paths:

### Claude Code

```bash
python3 plugins/claude/plugin-install.py install --workspace /path/to/sandbox
python3 plugins/claude/plugin-install.py check --workspace /path/to/sandbox
```

### Cursor

```bash
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /path/to/sandbox
python3 plugins/cursor/plugin-install.py --check-workspace /path/to/sandbox
```

### In the Agent

Use a real clue, host, and credentials hint, for example:

```text
/midstack:start 我的192.168.154.251环境的mongo节点可能有问题，账号密码是root/123，你帮我看一下吧
/midstack:analyse
/midstack:review
```

If `/midstack:start` returns `blocked`, fix the missing inputs or remote access
first, then rerun.

## Repository Guide

- `docs/`: concepts, specs, proposals, and project tracking
- `core/`: shared models, templates, and taxonomies
- `src/`: runtime implementation used by plugins and shared entrypoints
- `domains/`: middleware-specific knowledge assets
- `scenarios/`: reusable failure-pattern definitions
- `plugins/`: agent-specific adapters
- `tools/`: validators, replay tools, generators, and thin engineering entrypoints
- `tests/`: fixtures, golden paths, replay coverage, and runtime tests

## Documentation

- [docs/README.md](docs/README.md): document map and authority rules
- [docs/concepts/architecture-overview.md](docs/concepts/architecture-overview.md): runtime diagrams
- [docs/concepts/architecture.md](docs/concepts/architecture.md): structure and boundary design
- [docs/concepts/triage-workflow.md](docs/concepts/triage-workflow.md): workflow explanation
- [docs/specs/plugin-runtime.spec.md](docs/specs/plugin-runtime.spec.md): runtime contract
- [docs/project/implementation-status.md](docs/project/implementation-status.md): current support and progress

## Contributing

Run the repository checks before proposing changes:

```bash
python3 tools/validators/validate-repo.py
```

For replay-based validation:

```bash
python3 tools/replay/mongodb-replay.py --run-analyse
python3 tools/replay/mongodb-score.py --run-analyse --min-level medium
```

If a change affects schemas, taxonomies, command behavior, incident structure,
or cross-module contracts, start with
[docs/proposals/README.md](docs/proposals/README.md) and update the L1 sources
under `docs/specs/` and `core/` before adjusting downstream documentation.
