---
status: archived
last_updated: 2026-06-18
supersedes: ../specs/rs-status-collection-gap.spec.md
superseded_by: none
---

# Spec: rs.status Collection Reliability (Kubernetes Runtime Scenarios)

Status: implemented — Phase 4 complete (pending live sandbox verification)  
Incident reference: `mongodb-20260612-170221-ygxb` (midstack-cursor-sandbox)

## Objective

When triaging MongoDB Kubernetes runtime failures (e.g. ephemeral-storage eviction), the analyse pipeline must collect `rs.status` from at least one healthy replica-set member so Agent hypotheses can distinguish **Kubernetes-layer recovery** from **MongoDB-internal replica-set state** issues.

**User story:** After sandbox install, Agent produced H3 "无法采集 rs.status" during eviction triage. Operator needs to know whether this is missing capability, a bug, or expected gap — and wants the gap closed.

**Reframed success criteria:**

- When ≥1 schedulable mongod Pod can run `mongosh`/`mongo`, `mongodb.collect.replicaset.rs_status` produces `success` or `partial` with `structured_record.details.replica_members` populated.
- When the affected Pod is evicted/unreachable but a healthy peer exists, collection succeeds via peer fallback (existing script behavior).
- When collection fails, `collection_report.evidence_gaps` names the **specific** blocker (`pod_tool_missing`, `auth`, `all_peers_failed`, etc.) — not a generic "script output missing".
- For `kubernetes-runtime` scenarios, directed recollection retries `rs.status` when a `critical_gap` references it.
- Agent H3 moves from `insufficient` to `refuted` or `supported` when peer `rs.status` is present.

## Tech Stack

- Python 3 — `src/execution/remote/executor.py`, `tools/plugin/midstack-local.py`, `src/shared/skill_resolver.py`
- Shell/Python hybrid — `domains/mongodb/scripts/collect/collect-replicaset-rs-status.sh`
- YAML incident contracts — `collection_report.yaml`, `structured_record.yaml`, `analysis.yaml`

## Commands

```bash
# Validate repo (offline)
python3 tools/validators/validate-repo.py --skip-cursor

# Unit tests for routing/skill resolver
pytest tests/shared/test_scenario_router.py -q
pytest tests/shared/test_skill_resolver.py -q

# MongoDB replay (offline golden path)
python3 tools/replay/mongodb-replay.py --run-analyse

# Sandbox install + smoke (requires live cluster)
python3 plugins/cursor/plugin-install.py --upgrade --workspace-init /path/to/sandbox
python3 plugins/cursor/test-sandbox.py /path/to/sandbox

# Inspect rs.status outcome for an incident
cat .local/incidents/<id>/script_outputs/mongodb.collect.replicaset.rs_status/remote-executor-result.yaml
```

## Project Structure

```
domains/mongodb/scripts/collect/collect-replicaset-rs-status.sh  → rs.status + peer fallback
src/execution/remote/executor.py                                  → preflight (pod_tool probe)
domains/mongodb/skills/kubernetes-runtime/.../metadata.yaml        → directed recollection pool
domains/mongodb/skills/replica-set/.../metadata.yaml               → rs.status in required_assets
tools/plugin/midstack-local.py                                   → MVP batch + directed recollection
docs/specs/analyse-mvp.spec.md                                   → MVP script #7 = rs.status
```

## Code Style

- Executor preflight returns structured `capability_checks` with `error_code` (e.g. `pod_tool_missing`).
- Scripts emit `evidence_gaps` with `gap_type`: `expected_gap` | `critical_gap`.
- Skill `required_assets` uses `type: script` + `id: mongodb.collect.replicaset.rs_status`.

## Testing Strategy

| Level | What | Where |
|-------|------|-------|
| Unit | `probe_pod_tool`, `shell_candidates`, gap-driven recollection selection | `tests/execution/remote/`, `tests/shared/`, `tests/phases/phase3/` |
| Replay | MVP pipeline includes rs.status merge | `tests/golden-paths/` |
| Integration | Live PSMDB/Bitnami cluster rs.status success | manual / `PYTHONPATH=src python3 -m execution.remote.executor` |
| Regression | Incident `mongodb-20260612-170221-ygxb` fixture | new fixture once fixed |

## Boundaries

- **Always:** Preserve read-only safety; log which Pod/container/shell path was used.
- **Ask first:** Adding new dependencies; changing auth/secret contract; multi-round recollection limits.
- **Never:** Silently downgrade `critical_gap` to success; run write operations inside mongod Pods.

## Diagnosis (Sandbox Incident)

### What is already implemented

| Component | Status |
|-----------|--------|
| `collect-replicaset-rs-status.sh` | ✅ Peer fallback loop, gap classification |
| MVP script list (#7) | ✅ Runs in Phase 3 batch |
| Executor target resolution | ✅ Resolved 9 replica pods |
| Agent H3 hypothesis | ✅ Correctly `insufficient` when evidence missing |

### What failed in sandbox

From `mongodb-20260612-170221-ygxb`:

```
remote-executor-result.yaml:
  status: blocked
  error.code: pod_tool_missing
  capability_checks.pod_tool.mongosh: blocked (exit code 127)
```

- Script **never executed** — no `output.yaml`, peer fallback **not reached**.
- At collection time shard0 Pods were **Running Ready** — failure is **not** eviction blocking peer exec.
- `deployment_architecture: bitnami` in context, cluster is **PSMDB** (`psmdb-test`) — shell probe uses only `command -v mongosh|mongo` in default container PATH.
- Directed recollection ran `dns.coredns` + `network.overlay` only — `kubernetes-runtime` skill **does not** list `rs.status` in `required_assets`.

### Classification

**实现有问题 + 需要补齐适配**，不是"完全没做"。

1. **Bug / gap A — Preflight hard-block:** Executor aborts before script when all Pods fail `pod_tool` probe; no architecture-specific shell paths or multi-container `-c mongod` selection.
2. **Gap B — Skill pool:** `kubernetes-runtime` skill omits `rs.status`; gap-driven recollection does not retry after MVP failure.
3. **Gap C — Gap specificity:** `collection_report` reports generic `script output missing` instead of surfacing `pod_tool_missing` as the actionable root cause for Agent validation actions.

Peer fallback logic (evicted member → healthy peer) is implemented but **irrelevant** until the script is allowed to run.

## Success Criteria (Done Definition)

- [ ] PSMDB test cluster: `rs.status` reaches `success` or `partial` with ≥1 `replica_members` entry.
- [ ] Evicted-target scenario (replay fixture): peer fallback collects from healthy member.
- [ ] `kubernetes-runtime` + `critical_gap` mentioning rs.status → directed recollection includes `mongodb.collect.replicaset.rs_status`.
- [ ] `skill_evidence_check.missing_or_failed` no longer lists rs.status after successful recollection.
- [ ] Agent task / analysis draft references collected `replica_members` when present.

## Decisions (Human Reviewed)

### D1 — Container & shell discovery

- Mongo shell runs **inside the MongoDB workload container**, not the default container blindly.
- Container name candidates: `mongos`, `mongo`, `mongodb`, `mongod` (varies by chart/operator).
- **Heuristic:** Mongo workload container is usually the **first container** in the Pod spec; fall back to name matching above.
- Binary candidates: `mongosh` first, then legacy `mongo` (low-version images).

### D2 — Preflight behavior

- Executor **must not hard-block** on `pod_tool_missing` for rs.status / get_shard_map.
- Defer to script execution; script emits structured `blocked` / `partial` with specific `evidence_gaps` and per-Pod/container diagnostics.

### D3 — Policy lives in runtime (not skill / gap heuristics)

MongoDB in-Pod 采集策略属于 **plugin / remote-executor runtime** 的固定合同，不依赖 scenario skill 或 gap 启发式是否触发。

Runtime 负责：

- 解析 namespace 内 **所有正常运行** 的采集目标
- 为每个目标解析 Mongo workload **container** 与 **shell 二进制**
- 将目标列表写入 `context-file`，脚本按列表 fan-out 执行
- Executor 对 `pod_tool_missing` **软处理**（warning + 继续），由脚本产出结构化 `blocked`/`partial`

Skill `required_assets` 仅作 Agent 可读合同，**不驱动**「采哪些 Pod」。

### D4 — Fan-out collection targets

| Script | Runtime target rule | Command |
|--------|---------------------|---------|
| `mongodb.collect.mongos.get_shard_map` | **Every** `Running` (+ prefer `Ready`) **mongos** Pod in incident namespace | `getShardMap` |
| `mongodb.collect.replicaset.rs_status` | **Every** `Running` (+ prefer `Ready`) **mongod** Pod (configsvr + shard/data; exclude mongos/operator) | `rs.status()` |

原则：

- 不是「选一个代表 Pod」——与当前 get_shard_map 单 Pod、rs.status 依赖启发式排序不同
- 单个 Pod 失败不阻断其他 Pod；汇总为 `partial` 或 `success`
- 若 **零个** 合格目标或 **全部** exec 失败 → `blocked` + `critical_gap`

### D5 — Container & shell resolution (runtime → context)

写入 `context.yaml` 的 `mongo_exec`（或等价字段）：

```yaml
mongo_exec:
  container_name_candidates: ["<pod.spec.containers[0].name>", "mongod", "mongo", "mongodb", "mongos"]
  shell_candidates: ["mongosh", "mongo"]
  auth:
    username: root
    password_file_env: MONGODB_ROOT_PASSWORD_FILE
    auth_database: admin
targets:
  mongos_pod_refs: ["bnmongo-mongos-abc", "bnmongo-mongos-def"]   # all running mongos
  mongod_pod_refs: ["bnmongo-shard0-data-0", "..."]               # all running mongod
```

脚本 **不再** 各自重复解析逻辑；runtime 在 `build_context()` 阶段统一填充。

## Recollection: Skill `required_assets` vs Gap-Triggered Rule (superseded by D3)

These are **two different layers** in the current runtime — not interchangeable.

| Layer | What it does today | rs.status effect |
|-------|-------------------|------------------|
| MVP batch (12 scripts) | Always runs in Phase 3 | rs.status already included |
| `skill.required_assets` | Builds `recollection_script_pool` + `skill_evidence_check.missing_or_failed` | Whitelist + Agent visibility only |
| `directed_recollection_script_ids()` | Heuristic rules pick ≤3 scripts | **Does not** read `missing_or_failed` today |
| `skill_pool` filter | Intersects selected scripts with pool | Without pool entry, rs.status is dropped even if a rule selects it |

### Option A — Always in `kubernetes-runtime` skill `required_assets`

Add `mongodb.collect.replicaset.rs_status` to skill metadata.

| Pros | Cons |
|------|------|
| Documents skill contract: k8s-runtime triage **may need** replica-set state | **Alone does not schedule recollection** — only pool + reporting |
| Agent task shows rs.status in Matched Assets / missing list | Every incident flags missing if MVP failed (noise if never fixed) |
| Allows gap rule to pass skill_pool filter | Does not consume a slot by itself |

### Option B — Gap-triggered selection rule only

Add `should_run_rs_status_recollection()` when `evidence_gaps` or script status indicates rs.status blocked/failed.

| Pros | Cons |
|------|------|
| Only spends 1 of 3 directed-recollection slots when actually needed | Without skill pool entry, script is **filtered out** (sandbox hit this) |
| Prioritizes dns/logs/describe when rs.status already succeeded | Depends on gap labeling quality |
| Matches "retry on failure" semantics | Invisible in skill contract if not also in required_assets |

### Relationship to D3 (runtime fan-out)

补采仍受 `DIRECTED_RECOLLECTION_CAP=3` 约束，但 **重跑同一脚本** 时 runtime 会再次 fan-out 全量 Running Pod。Skill/gap 只决定是否重跑，不决定采哪些 Pod。

## Phase 2 — Implementation Plan

### Components

```text
src/execution/remote/mongodb_collection_runtime.py  ← target + container resolution
src/execution/remote/executor.py                    ← build_context, soft preflight
domains/mongodb/scripts/collect/
  collect-mongos-get-shard-map.sh         ← loop all mongos_pod_refs
  collect-replicaset-rs-status.sh         ← loop all mongod_pod_refs, -c container
tests/execution/remote/test_mongodb_collection_runtime.py
```

### Step 1 — Runtime target resolver

`resolve_mongodb_collection_targets(pods) -> {mongos_pod_refs, mongod_pod_refs}`

- Filter: `phase == Running`; prefer `Ready` containers when status available
- mongos: name/label match `mongos`, exclude operator
- mongod: configsvr / shard / shardsvr labels or name patterns; exclude mongos

### Step 2 — Runtime container/shell probe (per pod)

`resolve_mongo_exec_target(kubectl, namespace, pod) -> {container, shell_path}`

- Try containers in order: `spec.containers[0].name`, then name candidates
- In each container: `command -v mongosh || command -v mongo`
- Record per-pod probe artifact for blocked diagnostics

### Step 3 — Executor changes

- `build_context()` calls resolver; sets `targets.mongos_pod_refs` / `targets.mongod_pod_refs`
- `validate_script_capabilities()` for get_shard_map / rs_status:
  - Keep `target_pod.discovery` hard check (no pods at all → blocked)
  - **Remove** hard block on `pod_tool.mongosh`; emit `partial` warning, set `capabilities.mongosh_in_pod_available` from probe summary
  - **Always** stage and run script

### Step 4 — Script fan-out

**get_shard_map:** loop `mongos_pod_refs`; `structured_record_patch.details.shard_maps[]` (one entry per mongos); status `success` if ≥1 ok.

**rs_status:** loop `mongod_pod_refs` with resolved `container`; existing `replica_members[]` shape; filter non-Running removed at runtime.

### Step 5 — Downstream merge

- `normalize.signals.bundle` / `mongodb-analyse.py`: tolerate multiple shard_maps; dedupe replica_members by pod
- Golden path fixture update if output shape changes

### Verification checkpoints

| Step | Verify |
|------|--------|
| 1 | `pytest tests/execution/remote/test_mongodb_collection_runtime.py -q` |
| 2 | Sandbox incident: both scripts reach `partial` or `success`, not executor `blocked` |
| 3 | `mongodb-replay.py --run-analyse` still green |
| 4 | 3 mongos / 9 mongod cluster: collection_report shows N successful_items |

### Risks

| Risk | Mitigation |
|------|------------|
| Fan-out increases exec time | Acceptable for triage; log per-pod duration |
| Auth differs per Pod | Same secret_ref contract as today; per-pod failure → `failed_items` |
| Multiple shard_maps redundant | Keep all; analyse can compare or pick first valid |

## Success Criteria (updated)

- [ ] Runtime `context.yaml` lists all Running mongos / mongod targets
- [ ] get_shard_map collects from **every** Running mongos (≥1 success → not `blocked`)
- [ ] rs.status collects from **every** Running mongod (≥1 success → not `blocked`)
- [ ] Executor never hard-blocks before script for `pod_tool_missing`
- [ ] Sandbox incident reproduces `partial`/`success` with per-pod artifacts
- [ ] Policy documented in `docs/specs/plugin-runtime.spec.md` (MongoDB fan-out section)

## Open Questions

None blocking implementation. Ready for human Plan approval.
