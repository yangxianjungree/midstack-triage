---
status: stable
last_updated: 2026-06-10
supersedes: none
superseded_by: none
---

# Signal Governance Patterns

本文件用于记录“信号采集与治理”阶段可参考的实现模式，便于后续在脚本、规则、LLM 和人工协作之间做设计取舍。

## 背景

当前已知有团队采用：

- 脚本聚合
- LLM 分类
- 评分循环

这种方式可以快速形成初版结果，但不是唯一方案，也未必适合所有中间件故障场景。

因此，本文件用于补充其他常见做法，并给出对本项目的建议。

## 模式 1：规则 / 阈值驱动

### 核心思路

先把信号标准化，再按规则、阈值或状态机判断异常。

### 典型特征

- 结构稳定
- 可解释性强
- 结果一致性高
- 对已知场景效果好

### 适合本项目的信号

- Pod 重启次数
- Node 状态
- PVC 异常
- 主从同步时延
- 成员角色状态

### 优点

- 稳定
- 易审计
- 易自动化

### 缺点

- 对未知场景适应性弱
- 规则维护成本会逐渐上升

### 参考

- Azure Monitor health model signals
  - https://learn.microsoft.com/en-us/azure/azure-monitor/health-models/signals

## 模式 2：时间线驱动

### 核心思路

先不急着分类结论，而是先把所有信号按时间组织成调查时间线。

### 典型特征

- 适合排查复杂连锁故障
- 强调先后顺序
- 适合和变更事件结合

### 适合本项目的信号

- Pod 创建时间
- Pod 上一次重启时间
- 选举时间
- 告警时间
- YAML 变更时间

### 优点

- 有助于判断因果路径
- 有助于重建故障演化过程

### 缺点

- 如果对象关联没做好，时间线会很乱

### 参考

- Datadog Timeline
  - https://docs.datadoghq.com/incident_response/incident_management/investigate/timeline/
- Amazon CloudWatch Investigations
  - https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Investigations.html

## 模式 3：实体 / 拓扑关联驱动

### 核心思路

先把信号挂到对象图上，再看异常沿着哪些实体关系传播。

### 典型特征

- 强调对象之间的关系
- 适合多组件、多节点、多依赖场景
- 适合中间件和 Kubernetes 场景

### 适合本项目的对象

- Pod
- Node
- StatefulSet
- Service
- PVC
- mongos
- mongod
- replica set
- shard

### 优点

- 很适合 MongoDB、Kafka、Redis 这类有明确拓扑关系的系统
- 有助于缩小排障范围

### 缺点

- 前期需要把对象模型整理清楚

### 参考

- Google Security Operations Investigate
  - https://cloud.google.com/security/products/security-operations/investigate
- Amazon CloudWatch Investigations
  - https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Investigations.html

## 模式 4：AI 建议 + 人工确认

### 核心思路

AI 给出建议、观察或假设，再由人工接受、丢弃或修正。

### 典型特征

- 不让 AI 直接决定最终结论
- 保留人工兜底
- 适合高风险生产环境

### 优点

- 比纯 LLM 自动结论更稳
- 容易逐步上线

### 缺点

- 需要设计人工确认接口或工作流

### 参考

- Amazon CloudWatch Investigations
  - https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Investigations.html

## 模式 5：先过滤，再用 LLM 做轻理解

### 核心思路

先用脚本或规则把原始信号压缩成较小集合，再让 LLM 做摘要、关键词提取、轻分类或候选假设生成。

### 典型特征

- 不让 LLM 直接面对全部原始日志
- 先做降噪、抽取、裁剪
- 更适合成本和效果平衡

### 适合本项目的场景

- Pod 日志量大
- 多副本日志重复
- 需要快速形成 `normalized_summary`
- 需要快速提取 `keywords`

### 优点

- 比“全量日志直接喂给 LLM”更稳
- 更容易控制成本和输出质量

### 缺点

- 前置过滤质量会直接影响 LLM 效果

### 参考

- COMET: Large Language Models Can Provide Accurate and Interpretable Incident Triage
  - https://www.microsoft.com/en-us/research/publication/large-language-models-can-provide-accurate-and-interpretable-incident-triage/

## 对本项目的建议

当前不建议把“脚本聚合 + LLM 分类 + 评分循环”作为唯一主方案。

更稳的组合是：

1. 脚本聚合原始信号
2. 用规则和对象模型做第一轮标准化
3. 做时间线和拓扑关联
4. 用规则先筛出高优先级异常
5. 再让 LLM 做以下事情：
   - 线索分类
   - 日志摘要
   - 候选场景归类
   - 假设生成
   - 证据链总结
6. 由人工或规则对 LLM 建议做确认、丢弃或修正

## 当前倾向

本项目在第 3 段更适合采用混合模式：

- 规则 / 阈值驱动
- 时间线驱动
- 实体 / 拓扑关联驱动
- 轻量 LLM 理解
- 人工确认

而不是把全部治理逻辑直接交给 LLM。
