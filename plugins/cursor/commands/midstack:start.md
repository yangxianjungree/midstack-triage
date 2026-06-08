# Midstack Start

Use the `midstack-triage` MCP tool `midstack_start` directly.

Do not inspect `.cursor/mcp.json`, plugin source files, or repository code before calling the tool.

Do not manually run `tools/plugin/midstack-local.py` unless the MCP tool call is unavailable.

Extract fields from the user's natural-language request:

- `middleware`: use `mongodb` when the user says mongo, mongodb, mongos, mongod, shard, configsvr, or MongoDB.
- `environment_ips`: extract all IPv4 addresses, keep the original order, and let the first IP be the jump host.
- `username` and `password`: extract forms such as `root/123`, `账号密码是root/123`, or `username/password`.
- `customer_clue`: preserve the original symptom or fault clue from the user message.
- `port`: default to `22` unless the user provides a different SSH port.

Required fields:

- `middleware`, default `mongodb`
- `customer_clue`
- `environment_ips`, one or more remote Kubernetes environment IPs; use the first as jump host
- `username`
- `password`

Optional fields:

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
