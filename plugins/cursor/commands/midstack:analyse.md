# Midstack Analyse

Use the `midstack-triage` MCP tools to run MongoDB triage analysis.

Default fixture smoke:

- Call `midstack_analyse_fixture` with `input_dir=tests/fixtures/mongodb/connection-failure-sample` and `output_dir=.local/incidents/cursor-connection-failure`.
- Then call `midstack_review` with `incident_dir=.local/incidents/cursor-connection-failure`.
- Summarize the generated `analysis.yaml` and `review.yaml` paths.

If the user provides a remote run directory, call `midstack_analyse_remote_run` instead.

If the user provides a local remote config path such as `.local/test-envs/mongodb-k8s.yaml`, call `midstack_analyse_remote_config`.
