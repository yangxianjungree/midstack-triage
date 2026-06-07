# Midstack Start

Use the `midstack-triage` MCP tool `midstack_start`.

Required fields:

- `middleware`, default `mongodb`
- `customer_clue`
- `environment_ips`, one or more remote Kubernetes environment IPs; use the first as jump host
- `username`
- `password`

Optional fields:

- `port`, default `22`
- `namespace`
- `cluster_id`
- `incident_id`

After creating the incident, report whether it is `ready` or `blocked`.

If it is `ready`, tell the user the incident directory and suggest running `/midstack:analyse`.

If it is `blocked`, summarize the blocking items from `adapter-output.yaml`.
