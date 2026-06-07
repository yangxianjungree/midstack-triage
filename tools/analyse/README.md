# Analyse Tools

本目录存放本地 analyse 原型工具。

## MongoDB Analyse

基于 fixture 或 incident 目录生成最小 `analysis.yaml`：

```bash
python3 tools/analyse/mongodb-analyse.py \
  --input-dir tests/fixtures/mongodb/connection-failure-sample \
  --output-file .local/replay/connection-failure.analysis.yaml
```

当前能力：

- 读取 `input.yaml`
- 读取 `signal_bundle.yaml`
- 读取 `collection_report.yaml`
- 基于 scenario 和 abnormal signals 生成初步假设与结论
- 基于 MongoDB 资产 metadata 生成匹配场景的知识沉淀候选

当前限制：

- 不连接远程环境
- 不调度采集脚本
- 不替代正式插件命令
- 规则仍是 MongoDB MVP 原型
