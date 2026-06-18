---
description: Start a MongoDB incident triage record with Midstack
argument-hint: <customer clue with host and credentials>
---

Use the current workspace as the incident output root. The plugin runtime is
packaged under `${CLAUDE_PLUGIN_ROOT}`.

First hop: run the installed Midstack runtime wrapper below after parsing
`$ARGUMENTS`. Do not implement triage directly in the slash command before the
runtime command returns.

Command boundary:

- Do not claim the incident was started until the Bash command returns and
  `adapter-output.yaml` has been read.
- The first shell command must call `${CLAUDE_PLUGIN_ROOT}/runtime/bin/midstack-local.py`.
- Do not call repository source-tree `tools/plugin/midstack-local.py`.
- Do not run ad-hoc SSH, sshpass, scp, kubectl, database clients, package
  installers, or filesystem searches from the slash command layer.
- Remote execution tools are runtime implementation details; the Midstack
  runtime may use SSH/sshpass/scp/kubectl internally.
- Do not run `/midstack:analyse` from this command.
- If the Bash command fails or times out, report that `start` failed and stop.

Parse `$ARGUMENTS` for:

- `middleware`: use `mongodb` for MongoDB, mongo, mongos, mongod, shard, configsvr.
- `environment_ips`: all IPv4 addresses, original order. The first IP is the jump host.
- `username` and `password`: support forms such as `root/123` or `账号密码是root/123`.
- `customer_clue`: preserve the original symptom text.
- `port`: default `22` unless specified.
- `environment_mode`: default `remote`; use `local` only when the runtime is already on the fault cluster/control host, or `offline` when the user only has existing artifacts or pasted command output.

Default `remote` mode is the current main path and requires `--environment-ip`,
`--username`, and `--password`. `local` and `offline` are recognized by Phase 1
but currently return blocked guidance instead of running collection.

If a previous `start` returned `blocked` and `$ARGUMENTS` appears to answer its
follow-up questions, run `start` again with the same `--incident-id`. Fields
already captured in the incident may be omitted; the runtime merges them from
the existing record.

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
  --environment-mode remote \
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
- prefer `follow_up_questions` when present and ask those questions directly
- show the read-only `next_actions`
- include the incident id so the user's next answer can continue this same start record

Do not print passwords or tokens.
