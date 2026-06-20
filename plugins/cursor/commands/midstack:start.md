# Midstack Start

Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `runtime_root`. Set `MIDSTACK_TRIAGE_WORKSPACE` to the absolute workspace path.

Cursor runs Midstack from the workspace-local bundled runtime. Use `runtime_root` from workspace state and do not `cd` into the Midstack source repository.

Command boundary: `/midstack:start` only creates or recovers an incident record. It must not run analysis.

Do not inspect plugin source files, repository code, or existing `.local/incidents` before running `start`.

First hop: run the workspace-local Midstack runtime wrapper below after parsing
the user's arguments.

The first shell command must call `<workspace>/.cursor/midstack-triage-runtime/bin/midstack-local.py`.

Do not call repository source-tree `tools/plugin/midstack-local.py`.

Do not run ad-hoc SSH, sshpass, scp, kubectl, database clients, package installers, or filesystem searches from the slash command layer.

Remote execution tools are runtime implementation details; the Midstack runtime may use SSH/sshpass/scp/kubectl internally.

Do not print passwords or tokens in the user-facing response; redact them if credentials must be mentioned.

If `start` fails or times out:

- Do not run `analyse` or `finalize-analysis`.
- Do not manually SSH to any environment node.
- Do not read `.cursor/commands/midstack:analyse.md`.
- Do not read, create, or edit `analysis.yaml`, `analysis.rules-fallback.yaml`, `agent-reasoning-task.md`, `report.md`, `signal_bundle.yaml`, or `collection_report.yaml`.
- If an incident directory was created, only read `adapter-output.yaml`, `meta.yaml`, `input.yaml`, or `object-inventory.yaml` to report the start status.

Extract fields from the user's natural-language request:

- `middleware`: use `mongodb` when the user says mongo, mongodb, mongos, mongod, shard, configsvr, or MongoDB.
- `environment_ips`: extract all IPv4 addresses, keep the original order, and let the first IP be the jump host.
- `username` and `password`: extract forms such as `root/123`, `账号密码是root/123`, or `username/password`.
- `customer_clue`: preserve the original symptom or fault clue from the user message when present.
- `port`: default to `22` unless the user provides a different SSH port.
- `artifact_source`: for offline mode, extract an existing local incident, fixture, or remote-run artifact directory when the user provides one.
- `pasted_evidence`: for offline/manual mode, pass pasted command output or screen text as raw evidence only.

Default environment mode is `remote`, which means the runtime can SSH into a jump host or fault-domain host and then use remote `kubectl`.

Use `--environment-mode local` only when the agent/runtime is already on the fault cluster or control host. The runtime validates the local kubectl context in Phase 2, writes `local-config.yaml` when ready, and later runs the same Phase 3 collection through the local transport without SSH.

Use `--environment-mode offline` when the user only has existing incident artifacts, remote-run output, logs, screenshots, or pasted command output. If the user provides an existing complete artifact directory, pass it as `--artifact-source`; if they paste command output or screen text, pass it as `--pasted-evidence`. Pasted evidence is stored raw and still returns blocked guidance.

Required CLI fields for `remote`: `middleware`, at least one `--environment-ip`, `--username`, `--password`.

Optional: `--customer-clue`, `--port` (default 22), `--namespace`, `--cluster-id`, `--incident-id`, `--environment-mode`, `--artifact-source`, `--pasted-evidence`.

If a previous `start` returned `blocked` and the user is answering its
follow-up questions, run `start` again with the same `--incident-id`. You may
omit fields already captured by that incident; the runtime merges them from the
existing record.

Example shell (replace paths and secrets):

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
python3 "/abs/path/to/workspace/.cursor/midstack-triage-runtime/bin/midstack-local.py" start \
  --middleware mongodb \
  --customer-clue "我的192.168.154.251环境的一个mongo节点有问题" \
  --environment-ip 192.168.154.251 \
  --username root \
  --password '123' \
  --port 22 \
  --output-root .local/incidents
```

After `start`, report whether the incident is `ready` or `blocked` from `adapter-output.yaml`.

If `ready`, print `user_message` from `adapter-output.yaml` verbatim. It is the fixed Markdown table for the ready response; do not rewrite it as prose.

If `blocked`, summarize blocking items. If multiple MongoDB namespaces were detected, list candidates and ask the user to choose one.

Prefer `follow_up_questions` from `adapter-output.yaml` when present; ask those questions directly instead of inventing new ones.

When asking follow-up questions, include the incident id and tell the user their
next answer will continue that same start record.
