# Taxonomies

本目录用于存放通用分类和枚举。

当前已定义：

- `risk-levels.yaml`：只读、低风险、高风险动作分级
- `status-types.yaml`：脚本输出、远程执行器、插件输出、资产治理、review 评分、incident 生命周期和假设验证结果状态
- `candidate-types.yaml`：知识沉淀候选类型
- `scenario-types.yaml`：跨中间件故障场景类型
- `triage-surface-types.yaml`：runbook/skill/command metadata 中 `component` 字段使用的排查面类型；不要与 `domains/<middleware>/metadata.yaml` 的产品逻辑组件混用
- `capability-types.yaml`：远程执行与观测能力类型
- `kubernetes-runtime-signal-types.yaml`：跨中间件复用的 Kubernetes runtime 异常信号类型
- `tag-guidelines.yaml`：标签使用原则和示例
