# Midstack Start

Use the `midstack-triage` MCP tool `midstack_start`.

Required fields:

- `middleware`, default `mongodb`
- `customer_clue`

Optional fields:

- `namespace`
- `cluster_id`
- `incident_id`

After creating the incident, tell the user the incident directory and suggest running `/midstack:analyse`.
