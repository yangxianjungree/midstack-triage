---
description: Start a MongoDB incident triage record with Midstack
argument-hint: <customer clue with host and credentials>
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

First action: run the Bash command below after parsing `$ARGUMENTS`. Do not
inspect the environment yourself before this command.

Hard boundary:

- Do not claim the incident was started until the Bash command returns and
  `adapter-output.yaml` has been read.
- Do not run `mongosh`, `mongo`, `mysql`, `psql`, or any database client.
- Do not run `pip`, `pip3`, `apt`, `yum`, or install local packages.
- Do not run raw `ssh`.
- Do not run raw `sshpass`.
- Do not run raw `scp`.
- Do not run raw `kubectl`.
- Do not run raw `grep` or `find`.
- Do not run `/midstack:analyse` from this command.
- If the Bash command fails or times out, report that `start` failed and stop.

Parse `$ARGUMENTS` for:

- `middleware`: use `mongodb` for MongoDB, mongo, mongos, mongod, shard, configsvr.
- `environment_ips`: all IPv4 addresses, original order. The first IP is the jump host.
- `username` and `password`: support forms such as `root/123` or `账号密码是root/123`.
- `customer_clue`: preserve the original symptom text.
- `port`: default `22` unless specified.

Run:

```bash
export MIDSTACK_TRIAGE_WORKSPACE="$(python3 "${CLAUDE_PLUGIN_ROOT}/runtime/bin/resolve-workspace.py")"
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
