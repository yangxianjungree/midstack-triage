# Tests

本目录存放离线回放、评分和固定测试环境闭环相关资产。

目标：

- 不依赖用户反馈作为主要优化来源
- 用真实环境采集结果冻结 fixture
- 用 fixture replay 快速验证 analyse 逻辑
- 用 score comparison 判断输出是否退化

目录：

- `fixtures/`：可离线回放的 incident 样例
- `phases/phase1/`：第 1/2 段启动与盘点测试
- `phases/phase3/`：第 3 段采集与信号治理测试
- `phases/phase4/multitrack/`：第 4 段多轨推理的专属模块测试
- `phases/phase5/`：第 5 段 finalize / review 测试
- `plugins/claude/`：Claude 插件安装与检查逻辑测试
- `plugins/cursor/`：Cursor 插件安装与命令投影测试
- `shared/`：`src/shared/*` 共享运行时测试
- `tools/plugin/`：本地 CLI 入口与工作区路径行为测试
- `tools/analyse/`：analyse CLI 兼容壳及其背后的 `src/phases/phase4/rule_drafts/*` 测试
- `replay/`：回放流程说明和后续工具入口
- `scores/`：评分样例和后续评分结果

原则：

- 不存放真实账号密码
- 不存放大段原始日志
- fixture 保存结构化摘要和期望结论
- 真实环境 smoke 结果继续保存在 `.local/`
- 运行时生成物不要回写 `tests/fixtures/`
- 新测试优先放到与实现 ownership 对齐的目录，不再新增新的 `tests/unit/`
