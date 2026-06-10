# Midstack Review

Use the `midstack-triage` MCP tool `midstack_review`.

If the user did not provide `incident_dir`, call `midstack_review` without `incident_dir`; it will use the current incident selected by `start` or `analyse`.

Return the `analysis.yaml` path and summarize the five score dimensions from its `review` block.
