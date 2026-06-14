# Tests

本目录存放离线回放、评分和固定测试环境闭环相关资产。

目标：

- 不依赖用户反馈作为主要优化来源
- 用真实环境采集结果冻结 fixture
- 用 fixture replay 快速验证 analyse 逻辑
- 用 score comparison 判断输出是否退化

目录：

- `fixtures/`：可离线回放的 incident 样例
- `phases/phase4/multitrack/`：第 4 段多轨推理的专属模块测试
- `replay/`：回放流程说明和后续工具入口
- `scores/`：评分样例和后续评分结果
- `unit/`：仓库级单元测试，覆盖 plugin / start / analyse / shared helpers 等稳定模块

原则：

- 不存放真实账号密码
- 不存放大段原始日志
- fixture 保存结构化摘要和期望结论
- 真实环境 smoke 结果继续保存在 `.local/`
- 运行时生成物不要回写 `tests/fixtures/`
