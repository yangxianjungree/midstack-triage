# Midstack Analyse

Use the `midstack-triage` MCP tools to run MongoDB triage analysis.

If the user just ran `/midstack:start` and does not provide an incident directory, call `midstack_analyse_current`.

If the user provides an incident directory from `/midstack:start`, call `midstack_analyse_incident`.

After the analyse tool returns `completed`:

- Open the generated incident directory and read `agent-reasoning-task.md`.
- Read `input.yaml`, `structured_record.yaml`, `signal_bundle.yaml`, and `collection_report.yaml`.
- Treat `analysis.rule-draft.yaml` as a fallback draft only, not the final diagnosis.
- Update `analysis.yaml` so it reflects Agent-led phase-4 hypotheses and phase-5 conclusion.
- Update `report.md` so it matches the final `analysis.yaml`.
- Then summarize the final conclusion, confidence, evidence gaps, and output paths.

Default fixture smoke:

- Call `midstack_analyse_fixture` with `input_dir=tests/fixtures/mongodb/connection-failure-sample` and `output_dir=.local/incidents/cursor-connection-failure`.
- Then call `midstack_review` with `incident_dir=.local/incidents/cursor-connection-failure`.
- Summarize the generated `analysis.yaml` path; review results live in its `review` block (no separate `review.yaml`).

If the user provides a remote run directory, call `midstack_analyse_remote_run` instead.

If the user provides a local remote config path such as `.local/test-envs/mongodb-k8s.yaml`, call `midstack_analyse_remote_config`.
