---
status: completed
last_updated: 2026-06-18
supersedes: none
superseded_by: none
---

# Spec: Asset Metadata Version/Status Pilot

## Objective

Start metadata governance without forcing a full-repository migration.

Decision: pilot `version` and `status` on `domains/mongodb/skills/**/metadata.yaml` first. This is the smallest high-value asset family because skills are the Agent-facing workflow layer and already drive runtime asset resolution.

## Tech Stack

- YAML metadata in `domains/mongodb/skills/**/metadata.yaml`.
- Skill schema in `core/models/skill.schema.yaml`.
- Status taxonomy in `core/taxonomies/status-types.yaml`.
- MongoDB asset validator in `tools/validators/mongodb_assets/domain_assets.py`.

## Commands

```bash
python3 tools/validators/validate-mongodb-scripts.py
python3 -m pytest tests/tools/validators/test_validate_mongodb_scripts.py -q
python3 tools/validators/validate-repo.py --skip-replay --skip-score --skip-cursor
git diff --check
```

## Project Structure

- MongoDB skill metadata gets `version` and `status`.
- Skill spec/schema document these fields.
- Validator enforces only the MongoDB skill pilot.

## Code Style

Keep validation direct and explicit:

```python
if data.get("status") not in taxonomies["asset_status"]:
    fail(errors, "%s status must be one of ..." % metadata_path)
```

## Testing Strategy

Use the existing MongoDB asset validator tests and add a regression fixture for missing/invalid skill governance fields.

## Boundaries

- Always: require `version` and `status` for MongoDB skills after this slice.
- Ask first: expanding the requirement to runbooks, commands, Pulsar or all domains.
- Never: migrate every metadata family in this pilot.

## Success Criteria

- Every MongoDB skill metadata file has `version` and `status`.
- MongoDB asset validation fails if a MongoDB skill omits either field or uses an unknown status.
- Skill schema/spec and taxonomy document the governance fields.

## Open Questions

- Whether `status` should later distinguish `active` from `deprecated`, `draft` and `experimental` across all asset families.
