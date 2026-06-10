---
status: authoritative
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# References

本文件用于归档项目在流程设计、排障方法、架构思路上的外部参考资料，便于后续遇到瓶颈时回看和借鉴。

## 使用原则

- 优先记录官方文档、权威方法论和可长期访问的参考资料
- 不要求完全照搬外部流程，而是提炼其中对本项目有价值的部分
- 每条参考资料尽量记录“可借鉴点”，避免只留链接不留结论

## 流程与方法论参考

### Google SRE - Effective Troubleshooting

链接：

- https://sre.google/sre-book/effective-troubleshooting/

可借鉴点：

- 强调结构化问题报告
- 强调 triage / examine / diagnose 的分层处理
- 强调 hypothesis-driven investigation
- 强调保留证据，避免将相关性误判为因果

### Google SRE - Incident Management Guide

链接：

- https://sre.google/resources/practices-and-processes/incident-management-guide/

可借鉴点：

- 故障处理中需要角色清晰、信息同步及时
- 适合后续借鉴其事件管理和协作机制

### Microsoft Learn - Root cause analysis in Azure SRE Agent

链接：

- https://learn.microsoft.com/en-us/azure/sre-agent/root-cause-analysis

可借鉴点：

- 强调 evidence gathering → hypothesis generation → validation → conclusion
- 强调应回忆和复用历史相似事件

### Azure Architecture Center - Monitoring and diagnostics guidance

链接：

- https://learn.microsoft.com/en-us/azure/architecture/best-practices/monitoring

可借鉴点：

- 强调跨日志、指标、追踪、基础设施事件的证据关联
- 强调时间线重建和 correlation 思维

### IBM - Techniques for troubleshooting problems

链接：

- https://www.ibm.com/support/pages/techniques-troubleshooting-problems

可借鉴点：

- 强调完整描述问题
- 强调回答 symptom / where / when / conditions / reproducible
- 强调检查最近变更

### Datadog - Incident Investigation

链接：

- https://docs.datadoghq.com/service_management/incident_management/incident_details/

可借鉴点：

- 强调 incident identification / categorization
- 强调全面数据收集
- 强调在服务、依赖、信号之间快速切换视角

### Datadog - Timeline

链接：

- https://docs.datadoghq.com/service_management/incident_management/investigate/timeline

可借鉴点：

- 强调时间线作为调查主轴
- 对“信号治理”和“结论整合”有直接借鉴意义

### PagerDuty - Probable Origin

链接：

- https://support.pagerduty.com/main/docs/probable-origin

可借鉴点：

- 可利用历史事件模式推断 probable origin
- 有助于缩小影响半径和减少无效排查

### PagerDuty - Past Incidents

链接：

- https://support.pagerduty.com/main/docs/past-incidents

可借鉴点：

- 历史事件的归档和引用机制值得借鉴
- 有助于构建项目自己的历史经验检索能力

### Amazon OpenSearch Service - Investigation Agent

链接：

- https://docs.aws.amazon.com/opensearch-service/latest/developerguide/application-investigation-agent.html

可借鉴点：

- 生成结构化假设
- 假设可同时保留主假设和备选假设
- 每条假设附带 data evidence
- 支持对假设执行 `Accept` / `Rule out`
- 适合借鉴到第 4 段的多假设与验证闭环

## 当前对本项目的启发

当前已确认对本项目有直接价值的方向包括：

- 在排障主流程中显式加入“信号治理”
- 在排障过程中重视时间线重建
- 在推理诊断中采用假设驱动方法
- 在结论阶段加入知识沉淀，而不是只停在一次性结论
- 将历史案例和历史经验作为正式输入，而不是临时参考

与第 3 段“信号采集与治理”实现方式相关的方案对比，见 [docs/SIGNAL_GOVERNANCE_PATTERNS.md](concepts/signal-governance.md)。

## 后续可继续扩展的参考方向

- 更多中间件厂商官方故障诊断手册
- Kubernetes 生产排障方法论
- 事件管理、RCA、Postmortem 规范
- 面向 Agent 的诊断工作流设计资料
