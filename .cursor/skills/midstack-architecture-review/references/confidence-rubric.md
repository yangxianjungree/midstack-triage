# 置信度与误报过滤

借鉴代码审查 skill 的「宁缺毋滥」原则。架构检视同样要控制噪音，避免刷屏式低质量建议。

## 置信度评分（0–100）

| 分数 | 含义 | 是否写入报告 |
|------|------|--------------|
| 0–49 | 推测性、无法从仓库证据验证 | 否 |
| 50–69 | 可能成立，但缺少直接证据 | 仅「需人工确认」区 |
| 70–79 | 较可信，有文档或路径依据 | 是（风险/建议） |
| 80–100 | 明确违反 architecture/spec 或样例链路 | 是（阻塞/风险） |

**默认阈值：≥ 80 才作为正式 findings；50–79 进「需人工确认」。**

## 不算问题（勿标记）

- 未落地中间件（Kafka 等）尚未存在的目录——除非提案声称已落地
- 个人风格偏好，且 `docs/` 无明确规定
- 已在 `docs/architecture.md` 明确延后的事项（如 `generators/`）
- 与本次检视范围无关的目录
- 仅凭「以后可能乱」、无当前重复或断链证据

## 每条 finding 必填

```yaml
id: finding-001
severity: 阻塞 | 风险 | 建议
confidence: 85
axis: 结构合规 | 意图达成    # 双轴检视，见 SKILL.md
location: domains/mongodb/skills/.../metadata.yaml
evidence: 引用的字段、文件片段或 spec 条款
reason: 为何是问题
suggestion: 可操作的修复方向
needs_human: false
```
