# Midstack Start

Use **Agent CLI + shell** only.

Read `.cursor/midstack-triage.workspace.json` for `engine_root`. Set `MIDSTACK_TRIAGE_WORKSPACE` to the absolute workspace path.

Hard boundary: `/midstack:start` only creates or recovers an incident record. It must not run analysis.

Do not inspect plugin source files, repository code, or existing `.local/incidents` before running `start`.

Do not run raw `ssh`, `sshpass`, `kubectl`, `grep`, or `find` for `/midstack:start`; `start` owns remote validation and incident creation.

Do not print passwords or tokens in the user-facing response; redact them if credentials must be mentioned.

If `start` fails or times out:

- Do not run `analyse` or `finalize-analysis`.
- Do not manually SSH to any environment node.
- Do not read `.cursor/commands/midstack:analyse.md`.
- Do not read, create, or edit `analysis.yaml`, `analysis.rule-draft.yaml`, `agent-reasoning-task.md`, `report.md`, `signal_bundle.yaml`, or `collection_report.yaml`.
- If an incident directory was created, only read `adapter-output.yaml`, `meta.yaml`, `input.yaml`, or `object-inventory.yaml` to report the start status.

Extract fields from the user's natural-language request:

- `middleware`: use `mongodb` when the user says mongo, mongodb, mongos, mongod, shard, configsvr, or MongoDB.
- `environment_ips`: extract all IPv4 addresses, keep the original order, and let the first IP be the jump host.
- `username` and `password`: extract forms such as `root/123`, `账号密码是root/123`, or `username/password`.
- `customer_clue`: preserve the original symptom or fault clue from the user message when present.
- `port`: default to `22` unless the user provides a different SSH port.

Required CLI fields: `middleware`, at least one `--environment-ip`, `--username`, `--password`.

Optional: `--customer-clue`, `--port` (default 22), `--namespace`, `--cluster-id`, `--incident-id`.

Example shell (replace paths and secrets):

```bash
export MIDSTACK_TRIAGE_WORKSPACE="/abs/path/to/workspace"
cd "/abs/path/to/midstack-triage" && python3 tools/plugin/midstack-local.py start \
  --middleware mongodb \
  --customer-clue "我的192.168.154.251环境的一个mongo节点有问题" \
  --environment-ip 192.168.154.251 \
  --username root \
  --password '123' \
  --port 22 \
  --output-root .local/incidents
```

After `start`, report whether the incident is `ready` or `blocked` from `adapter-output.yaml`.

If `ready`, give the incident directory and suggest `/midstack:analyse`.

If `blocked`, summarize blocking items. If multiple MongoDB namespaces were detected, list candidates and ask the user to choose one.
