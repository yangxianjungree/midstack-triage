---
status: proposed
last_updated: 2026-06-19
supersedes: none
superseded_by: none
related:
  - ../2026-06-19-local-analyse-transport-reuse/spec.md
  - ../../specs/plugin-runtime.spec.md
  - ../../specs/triage-workflow.spec.md
---

# Spec: Local Node Access Contract

## Objective

Define how `local` execution behaves when evidence requires access to Kubernetes
worker/control-plane nodes beyond the Kubernetes API.

The default contract is:

- `local` can read cluster and node state through the current machine's
  `kubectl` context.
- `local` must not SSH to Kubernetes nodes unless node access is explicitly
  configured.
- Node-host file evidence, such as kubelet-side Pod log paths, is an optional
  `node_access` capability. When enabled, SSH key/agent authentication is the
  normal path; password is optional for clusters without node-to-node trust.
  Missing capability should produce structured `blocked` / evidence-gap output
  instead of silently trying SSH.

## Assumptions

1. Kubernetes API node reads, for example `kubectl get nodes`, are already part
   of local readiness and collection.
2. `mongodb.collect.logs.node_file_tail` is the current script that may need
   node-host file access.
3. This slice should not implement Kubernetes debug pods, DaemonSet collection,
   or a full interactive node SSH intake flow.
4. Explicit node SSH can be represented in runtime config now and wired into a
   fuller Phase 2 prompt later.

## Success Criteria

- `local-config.yaml` records a default `node_access` contract with SSH disabled
  and `auth_preference=key_or_agent`.
- The executor's local access loading keeps that default when older local config
  files omit it.
- `mongodb.collect.logs.node_file_tail` does not SSH to non-local nodes in
  local mode unless `access.node_access.ssh.enabled` is true.
- Explicit node SSH without a password uses key/agent `ssh BatchMode`; password
  SSH uses `sshpass` only when a password is configured.
- When node SSH is not enabled, the node-file-tail script returns a structured
  blocked result with a clear evidence gap and recommended action.
- Existing remote/local/offline analyse behavior remains compatible.

## Commands

```bash
python3 -m pytest tests/execution/remote tests/tools/plugin/test_midstack_local_workspace.py tests/scripts/test_mongodb_node_file_tail.py -q
python3 -m py_compile src/execution/remote/cli.py src/commands/start.py
bash -n domains/mongodb/scripts/collect/collect-log-node-file-tail.sh
python3 tools/validators/validate-repo.py
git diff --check
```

## Boundaries

- Always: prefer Kubernetes API collection for ordinary node state.
- Always: make node-host access explicit.
- Always: block with evidence gaps when required node-host access is unavailable.
- Ask first: adding Kubernetes debug pods or DaemonSet collectors.
- Ask first: adding node SSH fields to the public slash-command surface.
- Never: silently SSH from local mode to a Kubernetes node using guessed
  credentials.

## Tasks

- [x] Task: Persist local node access defaults
  - Acceptance: new local incidents include `node_access.mode=kubernetes_api_only`,
    `node_access.ssh.enabled=false`, and `node_access.ssh.auth_preference=key_or_agent`.
  - Verify: `python3 -m pytest tests/tools/plugin/test_midstack_local_workspace.py -q`
  - Files: `src/commands/start.py`, `tests/tools/plugin/test_midstack_local_workspace.py`
- [x] Task: Normalize local access config defaults
  - Acceptance: older `local-config.yaml` files without `node_access` get the
    same default in executor local access loading.
  - Verify: `python3 -m pytest tests/execution/remote -q`
  - Files: `src/execution/remote/cli.py`, `tests/execution/remote/test_runtime_support.py`
- [x] Task: Gate node-file-tail node SSH
  - Acceptance: local node-file-tail refuses non-local node SSH unless explicit
    node SSH is enabled; explicit node SSH config is used when present.
  - Verify: `python3 -m pytest tests/scripts/test_mongodb_node_file_tail.py -q`
  - Files: `domains/mongodb/scripts/collect/collect-log-node-file-tail.sh`, `tests/scripts/test_mongodb_node_file_tail.py`
- [x] Task: Update docs
  - Acceptance: runtime/workflow docs explain local node API vs node-host access.
  - Verify: `git diff --check`
  - Files: `docs/specs/triage-workflow.spec.md`, `docs/specs/plugin-runtime.spec.md`

## Open Questions

- Whether the next slice should implement Kubernetes-native node access through
  debug pods, a temporary DaemonSet, or only explicit SSH.
