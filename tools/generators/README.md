# Generators

本目录存放资产骨架生成工具。

## Asset Generator

基于 `core/templates/` 生成 runbook、command、skill 资产目录。

示例：

```bash
python3 tools/generators/generate-asset.py \
  --kind runbook \
  --middleware mongodb \
  --component replica-set \
  --scenario replica-inconsistency \
  --slug replica-member-not-healthy \
  --title "MongoDB Replica Set Member Not Healthy" \
  --dry-run
```

批量生成一个场景下的 runbook、command、skill：

```bash
python3 tools/generators/generate-asset.py \
  --kind bundle \
  --middleware mongodb \
  --component connectivity \
  --scenario connection-failure \
  --slug connection-failure \
  --title "MongoDB Connection Failure" \
  --command-slug check-mongos-connectivity \
  --skill-slug triage-connection-failure \
  --dry-run
```

默认输出路径：

- runbook: `domains/<middleware>/runbooks/<component>/<slug>/`
- command: `domains/<middleware>/commands/<component>/<slug>/`
- skill: `domains/<middleware>/skills/<component>/<slug>/`

原则：

- 默认不覆盖已有文件
- 需要覆盖时显式传 `--force`
- `--dry-run` 只打印计划写入的文件，不落盘
- `--scenario` 必须已存在 `scenarios/<scenario>/scenario.yaml`
