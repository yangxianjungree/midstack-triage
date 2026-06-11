---
status: draft
last_updated: 2026-06-11
supersedes: none
superseded_by: none
---

# 2026-06-11 排障小循环实施 TODO

本文件记录本提案目录下的过程性待办，不替代 L1。

## 已确认原则

- [x] 用户侧保持单次 `/midstack:analyse`，不扩展成多个用户可见 analyse 循环
- [x] 单次 analyse 内维护多假设，并允许最多 1 轮定向补采小循环
- [x] 定向补采只允许 catalog 白名单内的只读动作
- [x] 运行时显式区分 `expected_gap` 与 `critical_gap`
- [x] 结论需要显式受层级和置信度上限约束
- [x] `review` 加入过程偏差检查，但不新增第二套总分
- [x] 历史案例和知识资产只作为假设来源、验证路径来源或参考资料，不作为当前现场证据

## 待实施

### 推理合同和 prompt

- [x] 更新 `agent-reasoning-task.md` 生成逻辑，明确多假设、gap 分类、结论层级、来源区分、next actions 要求
- [x] 更新 `midstack_analyse_reasoning` prompt 文案，使其符合单次 analyse 内的小循环语义
- [x] 更新 Cursor 命令 / rule 文案，避免继续按一次性串行流程消费 `analysis.rule-draft.yaml`

### Review

- [x] 在现有五维评分上增加过程偏差检查
- [x] 将 `answer_led_bias`、`critical_gap_ignored`、`overconfident_conclusion` 等偏差映射到 score reasons
- [x] 为高风险过程偏差补充 `regression_risks`
- [x] 为常见过程偏差补充更具体的 `improvement_suggestions`

### MongoDB playbook

- [x] 为 `rs.status` 补齐健康 peer fallback 策略
- [x] 将 `kubectl logs --previous` 纳入明确 playbook，而不是临时动作
- [x] 设计并实现 `discover_log_sink` 的最小版本
- [x] 让“日志很短”场景能明确转化为“真实日志源未知”这类 `critical_gap`
- [x] 将 playbook 结果稳定回写为 artifact、gap 提示或 validation action 线索

### Gap 和结论 ceiling

- [x] 为 `collection_report.evidence_gaps` 补充运行时 gap 类型表达
- [x] 明确“故障 Pod 无法提供自身 `rs.status`”等典型场景的 gap 分类
- [x] 为 `analysis.yaml` 增加“最深可支持结论层级”的运行时表达
- [x] 为缺失 peer `rs.status` / fatal log / 未关闭 `critical_gap` 的场景加结论 ceiling guardrails

### Runtime 小循环

- [x] 定义单次 analyse 内部补采门禁在代码中的判定位置
- [x] 定义最多 1 轮、每轮 2 到 3 个动作的执行上限
- [x] 定义补采后 artifact / gap / signal merge 合同
- [x] 定义补采失败或证据仍不足时的阶段性收尾路径
- [x] 保持 `finalize-analysis` 与现有 incident 生命周期兼容

### L1 升级候选

- [ ] 评估是否将 `deepest_supported_level` 升级为正式模板字段
- [ ] 评估是否将 gap 类型升级为正式 taxonomy 或模板结构
- [ ] 评估是否为 `review` 增加结构化过程偏差输出字段

## 待验证

- [x] Cursor MCP smoke 覆盖更新后的 reasoning contract
- [x] 本地 `review` smoke 能反映过程偏差
- [x] MongoDB collect script validator 覆盖新 playbook
- [x] fixture / replay 不因新增运行时软字段而回归失败
- [x] 至少一个“日志很短 -> 真实文件日志源 / node-side file tail -> 根因收敛”的案例回归
- [x] 至少一个“critical_gap 未关闭 -> 正确止步而非强行根因”的案例回归
- [x] 至少一个“DNS timeout -> kube-dns Endpoint -> flannel overlay 根因”的案例回归
- [x] 保留现场验证：`k8s-253` flannel overlay partition 达到 `root_cause`，并识别并发 MongoDB storage corruption 故障线
