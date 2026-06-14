---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Incident Patch Merge Spec

本文件定义第 3 段脚本 `output-file` 如何合并进 incident 记录。

相关实现：

- [src/shared/patch_merge.py](../../src/shared/patch_merge.py)
- [core/models/incident-patch-merge.schema.yaml](../../core/models/incident-patch-merge.schema.yaml)

## 1. 合并对象

| 脚本 patch 字段 | incident 文件 |
|-----------------|-----------------|
| `structured_record_patch` | `structured_record.yaml` |
| `signal_bundle_patch` | `signal_bundle.yaml` |
| `collection_report_patch` | `collection_report.yaml` |

## 2. 合并顺序

`/plugin:analyse` 按脚本执行顺序依次应用 patch：

1. 先初始化空记录或已有记录
2. 每个脚本产出 `output.yaml`
3. 按 `manifest.yaml` 中 MVP 执行顺序逐个 merge
4. 写回 incident 目录

## 3. `structured_record_patch`

### 3.1 对象字段

- `summary`：递归深合并
- `details`：递归深合并，但对列表字段使用专门规则

### 3.2 `details` 列表规则

按稳定键合并（后者更新前者）：

| 字段 | 合并键 |
|------|--------|
| `pods` | `name` |
| `statefulsets` | `name` |
| `services` | `name` |
| `nodes` | `name` |
| `replica_members` | `source_pod_ref` |
| `components` | `component_id` |

直接追加：

- `raw_logs`
- `processed_logs`

未配置的列表字段：后写覆盖前写。

### 3.3 示例

先执行 `mongodb.collect.pods.state`，再执行 `mongodb.collect.replicaset.rs_status`：

- `details.pods` 保留
- `details.replica_members` 追加
- 不会互相覆盖

## 4. `signal_bundle_patch`

列表字段追加：

- `abnormal_signals`
- `object_signal_links`
- `timeline_summary`
- `processed_log_highlights`

其他对象字段递归深合并。

## 5. `collection_report_patch`

以下列表字段始终追加：

- `collection_actions`
- `successful_items`
- `failed_items`
- `blank_items`
- `evidence_gaps`

这样多个脚本的成功、失败和缺口都会保留。

## 6. 校验

```bash
python3 tools/validators/validate-patch-merge.py
python3 tools/validators/validate-golden-paths.py
```
