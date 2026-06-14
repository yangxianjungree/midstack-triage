---
description: Start a MongoDB incident triage record with Midstack
argument-hint: <customer clue with host and credentials>
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

Parse `$ARGUMENTS` for:

- `middleware`: use `mongodb` for MongoDB, mongo, mongos, mongod, shard, configsvr.
- `environment_ips`: all IPv4 addresses, original order. The first IP is the jump host.
- `username` and `password`: support forms such as `root/123` or `账号密码是root/123`.
- `customer_clue`: preserve the original symptom text.
- `port`: default `22` unless specified.

Run:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(pwd)"
python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py" start \
  --middleware mongodb \
  --customer-clue "<customer clue from arguments>" \
  --environment-ip <ip> \
  --username <username> \
  --password '<password>' \
  --port 22 \
  --output-root "$MIDSTACK_TRIAGE_WORKSPACE/.local/incidents"
```

Read `.local/incidents/<incident-id>/adapter-output.yaml` and report only the
safe fields.

When `status=ready`:

- show incident id, namespace, and output directory
- state exactly: `next run /midstack:analyse`
- do not ask a follow-up confirmation question

When `status=blocked`:

- summarize `blocking_items`
- show the read-only `next_actions`

Do not print passwords or tokens.
