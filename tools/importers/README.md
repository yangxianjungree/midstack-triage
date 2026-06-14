# Importers

本目录存放外部知识资产导入工具。

目录结构：

- `import-runbook.py`
  薄 CLI 入口
- `markdown_importer/`
  正式实现包；导入 metadata/body 生成逻辑都收敛在这里

## Markdown Importer

将已有 Markdown 文档导入为标准 runbook、command 或 skill 资产。

示例：

```bash
python3 tools/importers/import-runbook.py \
  --kind runbook \
  --source-file ./external-runbook.md \
  --middleware mongodb \
  --component replica-set \
  --scenario replica-inconsistency \
  --slug replica-member-not-healthy \
  --title "MongoDB Replica Set Member Not Healthy" \
  --dry-run
```

默认输出路径：

```text
domains/<middleware>/<asset-kind>/<component>/<slug>/
  metadata.yaml
  <asset-body>.md
```

原则：

- 默认不覆盖已有文件
- 需要覆盖时显式传 `--force`
- `--dry-run` 只打印计划写入的文件，不落盘
- 导入器不自动脱敏，导入前应人工确认源文档不包含敏感信息
- 不要把新的 Markdown 解析或资产写入逻辑继续写回顶层入口脚本
