---
status: stable
last_updated: 2026-06-21
supersedes: none
superseded_by: none
---

# Add a Middleware Domain

This guide explains the practical path for adding a new middleware domain to Midstack. MongoDB is the current complete reference implementation; Pulsar is a skeleton/contract example.

Use this guide as a checklist, not as a replacement for the L1 specs. Field contracts, command behavior, incident layout, and runtime semantics remain defined by `docs/specs/`, `core/models/`, `core/templates/`, and `core/taxonomies/`.

## Choose the Support Level

Start by deciding the intended support level:

| Level | What it means |
| --- | --- |
| Skeleton | Directory shape, metadata, one or two sample assets, and validator path exist. Not a production `analyse` path. |
| Contract path | Scripts, manifest, runtime-map entries, sample fixtures, and basic rules exist. Useful for integration work but still limited. |
| Active MVP | `start -> analyse` main path can collect evidence, reason, produce reports, and pass replay/score checks for at least one realistic scenario. |

Do not mark a domain production-ready just because it has runbooks. Midstack needs executable evidence collection and replayable validation.

## Directory Shape

Create the domain under `domains/<middleware>/`:

```text
domains/<middleware>/
├── README.md
├── metadata.yaml
├── commands/
├── runbooks/
├── scripts/
│   ├── README.md
│   └── manifest.yaml
└── skills/
```

Use `domains/mongodb/` as the complete reference. Keep product-specific content in the domain. Top-level `scenarios/` must stay thin and cross-middleware.

## Asset Responsibilities

| Asset | Responsibility |
| --- | --- |
| Scenario | Cross-middleware symptom definition and routing hints. No product-specific runbook body. |
| Runbook | Human-readable troubleshooting knowledge for the middleware. |
| Command | A small reusable command snippet without control flow. |
| Script | Executable read-only collection or normalization logic with control flow. |
| Skill | Agent orchestration text that references runbooks, commands, and scripts without copying their full bodies. |
| Rule analyzer | Production Phase 4 fallback logic under `src/phases/phase4/rules/<middleware>.py` when the domain enters the main `analyse` path. |

## Minimal Skeleton Checklist

1. Add `domains/<middleware>/metadata.yaml`.
2. Add a domain `README.md` that states support level and known limitations.
3. Add at least one runbook or command asset with metadata.
4. Add or reuse a top-level scenario under `scenarios/<scenario>/scenario.yaml`.
5. Add scenario routing only when the domain has enough assets to support it.
6. Run the relevant validators and update docs only as summaries, not as parallel specs.

## Contract Path Checklist

1. Add read-only collection scripts under `domains/<middleware>/scripts/`.
2. Add script entries to `domains/<middleware>/scripts/manifest.yaml`.
3. Add runtime-map entries in `core/interfaces/plugin/script-runtime-map.example.yaml`.
4. Ensure script outputs follow `core/models/script-output.schema.yaml`.
5. Add fixtures or golden paths that can be replayed without live customer data.
6. Add validator coverage for manifest, runtime-map, context, output, and routing consistency.

Remote Phase 3 scripts should avoid unnecessary dependencies. If a script runs on a jump host or inside a constrained environment, keep the Python 3.6/no-default-PyYAML boundary unless a specific script contract raises it.

## Active MVP Checklist

Before a domain is treated like MongoDB in the production `analyse` path:

1. Add or update `src/phases/phase4/rules/<middleware>.py`.
2. Route the middleware in the analyse command path.
3. Add realistic fixtures under `tests/fixtures/active/<middleware>/`.
4. Add replay and scoring support if the domain needs quality gates comparable to MongoDB.
5. Add tests for the rule analyzer and any normalization scripts.
6. Update `docs/project/implementation-status.md` and README support matrix.
7. Run the full repository gate.

## Evidence and Safety Rules

- Collection scripts must be read-only by default.
- Do not add production mutations to default flows.
- Do not commit raw customer evidence, generated `.local/incidents/`, kubeconfigs, private keys, or real credentials.
- Use documentation IP ranges such as `192.0.2.0/24`, `198.51.100.0/24`, and `203.0.113.0/24` for public examples.
- If a fixture needs private Kubernetes-style IPs to model service networking, keep the data synthetic and explain why.

## Validation

Run focused checks while developing, then the full gate before opening a pull request:

```bash
python3 tools/validators/validate-repo.py
python3 -m pytest tests -q
git diff --check
```

For a small skeleton domain, it is acceptable to start with focused validators, but production `analyse` support needs replayable evidence and tests.

## Common Mistakes

- Putting product-specific procedures into top-level `scenarios/`.
- Adding runbook text without metadata.
- Adding scripts but forgetting manifest or runtime-map entries.
- Depending on local developer paths or sandbox directories.
- Treating historical experience or runbooks as current incident evidence.
- Marking a domain as supported before `analyse` can produce a replayable result.
