# Midstack Analyse

Use the `midstack-triage` MCP tools to run MongoDB triage analysis.

If the user just ran `/midstack:start` and does not provide an incident directory, call `midstack_analyse_current`.

If the user provides an incident directory from `/midstack:start`, call `midstack_analyse_incident`.

Default fixture smoke:

- Call `midstack_analyse_fixture` with `input_dir=tests/fixtures/mongodb/connection-failure-sample` and `output_dir=.local/incidents/cursor-connection-failure`.
- Then call `midstack_review` with `incident_dir=.local/incidents/cursor-connection-failure`.
- Summarize the generated `analysis.yaml` path; review results live in its `review` block (no separate `review.yaml`).

If the user provides a remote run directory, call `midstack_analyse_remote_run` instead.

If the user provides a local remote config path such as `.local/test-envs/mongodb-k8s.yaml`, call `midstack_analyse_remote_config`.
