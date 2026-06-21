---
status: stable
last_updated: 2026-06-21
supersedes: none
superseded_by: none
---

# Specs Overview

The authoritative specs are currently written in Chinese. This page is an English index for contributors who need to understand which document controls which part of the system.

When this page conflicts with a Chinese spec, the Chinese spec wins.

## Authority Model

Midstack uses a layered documentation model:

- L1 source of truth: `docs/specs/`, `core/models/`, `core/templates/`, and `core/taxonomies/`
- L2 explanation: `docs/concepts/` and `docs/analysis/`
- L3 project status: `docs/project/`
- L4 archive: `docs/decisions/`

For the full authority rules, see [docs/README.md](../README.md).

## Core Specs

| Spec | Purpose |
| --- | --- |
| [triage-workflow.spec.md](triage-workflow.spec.md) | Defines the five-phase troubleshooting workflow, incident timing semantics, environment modes, evidence rules, and conclusion boundaries. |
| [plugin-runtime.spec.md](plugin-runtime.spec.md) | Defines plugin command behavior, runtime first-hop rules, execution modes, remote executor contracts, script calling conventions, dependency boundaries, and error/status handling. |
| [plugin-usage.spec.md](plugin-usage.spec.md) | Defines user-facing plugin usage expectations and command flow. |
| [incident-record.spec.md](incident-record.spec.md) | Defines incident directory layout, file responsibilities, reasoning history, logs, and artifact boundaries. |
| [analyse-mvp.spec.md](analyse-mvp.spec.md) | Defines the current analyse MVP scope, expected collection inputs, report output, and acceptance criteria. |
| [incident-patch-merge.spec.md](incident-patch-merge.spec.md) | Defines how script outputs and structured patches are merged into incident records. |
| [asset-reference.spec.md](asset-reference.spec.md) | Defines cross-asset reference semantics for domains, scenarios, runbooks, commands, skills, and scripts. |
| [scenario-routing.spec.md](scenario-routing.spec.md) | Defines scenario routing inputs, middleware applicability, and routing contracts. |
| [runbook.spec.md](runbook.spec.md) | Defines runbook metadata and content expectations. |
| [command.spec.md](command.spec.md) | Defines command asset metadata and boundaries. |
| [skill.spec.md](skill.spec.md) | Defines skill metadata and orchestration boundaries. |
| [sandbox-minimal-dependencies.spec.md](sandbox-minimal-dependencies.spec.md) | Defines minimal dependency expectations for installed sandbox/workspace use. |

## Field Contracts

For exact fields and allowed values, prefer these machine-readable sources:

- `core/models/*.schema.yaml`
- `core/templates/*.yaml`
- `core/taxonomies/*.yaml`

Specs may summarize fields for readability, but schema/template/taxonomy files are the better place to verify exact names and enum values.

## Contributor Pointers

- Adding a middleware domain: [docs/guides/add-domain.md](../guides/add-domain.md)
- Runtime dependency boundary: [plugin-runtime.spec.md](plugin-runtime.spec.md)
- Test and install gates: [docs/project/testing-and-install-gates.md](../project/testing-and-install-gates.md)
- Current implementation status: [docs/project/implementation-status.md](../project/implementation-status.md)
