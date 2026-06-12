# Midstack Start

Use the `midstack-triage` MCP tool `midstack_start` directly as the first action.

Do not inspect `.cursor/mcp.json`, plugin source files, repository code, or existing `.local/incidents` before calling the tool.

Do not manually run `tools/plugin/midstack-local.py` for `/midstack:start`.
Do not run raw `ssh`, `sshpass`, `kubectl`, `grep`, or `find` commands for `/midstack:start`; the tool owns remote validation and incident creation.
Do not print passwords or tokens in the user-facing response; redact them if credentials must be mentioned.

Hard boundary: `/midstack:start` only creates or recovers an incident record. It must not run analysis.

Even if the MCP call times out or appears unavailable:

- Do not call `midstack_analyse_current`, `midstack_analyse_incident`, or `midstack_finalize_analysis`.
- Do not manually SSH to any environment node.
- Do not read `.cursor/commands/midstack:analyse.md`.
- Do not read, create, or edit `analysis.yaml`, `analysis.rule-draft.yaml`, `agent-reasoning-task.md`, `report.md`, `signal_bundle.yaml`, or `collection_report.yaml`.
- If an incident directory was created, only read `adapter-output.yaml`, `meta.yaml`, `input.yaml`, or `object-inventory.yaml` to report the start status.
- If the start status cannot be recovered, tell the user the start request timed out and ask them to rerun `/midstack:start`; do not continue to analyse automatically.

Extract fields from the user's natural-language request:

- `middleware`: use `mongodb` when the user says mongo, mongodb, mongos, mongod, shard, configsvr, or MongoDB.
- `environment_ips`: extract all IPv4 addresses, keep the original order, and let the first IP be the jump host.
- `username` and `password`: extract forms such as `root/123`, `账号密码是root/123`, or `username/password`.
- `customer_clue`: preserve the original symptom or fault clue from the user message when present.
- `port`: default to `22` unless the user provides a different SSH port.

Required fields:

- `middleware`, default `mongodb`
- `environment_ips`, one or more remote Kubernetes environment IPs; use the first as jump host
- `username`
- `password`

Optional fields:

- `customer_clue`; high-value but not required
- `port`, default `22`
- `namespace`; if omitted, the plugin will try to auto-detect a single MongoDB candidate namespace from Kubernetes pods, StatefulSets, and Services
- `cluster_id`
- `incident_id`

Example:

User says:

```text
/midstack:start 我的192.168.154.251环境的一个mongo节点有问题，账号密码是root/123，你帮我看一下吧
```

Call:

```json
{
  "middleware": "mongodb",
  "customer_clue": "我的192.168.154.251环境的一个mongo节点有问题，账号密码是root/123，你帮我看一下吧",
  "environment_ips": ["192.168.154.251"],
  "username": "root",
  "password": "123",
  "port": 22
}
```

After creating the incident, report whether it is `ready` or `blocked`.

If it is `ready`, tell the user the incident directory and suggest running `/midstack:analyse`.

If it is `blocked`, summarize the blocking items from `adapter-output.yaml`. If multiple MongoDB namespaces were detected, list the candidate namespaces and ask the user to choose one.
