# Validators

本目录存放仓库结构和资产一致性校验工具。

## MongoDB Scripts

运行仓库最小回归验证套件：

```bash
python3 tools/validators/validate-repo.py
```

默认包含：

- MongoDB 资产与接口合同校验
- MongoDB fixture replay
- MongoDB replay score gate，默认要求所有评分维度至少达到 `medium`
- Fixture hygiene 检查，防止运行产物写回 `tests/fixtures/`
- Kubernetes runtime 通用分类检查，防止故障分类点对点实现
- Cursor agent-cli plugin smoke test (`plugins/cursor/test-agent-cli.py`)

可跳过 replay 或 score：

```bash
python3 tools/validators/validate-repo.py --skip-replay
python3 tools/validators/validate-repo.py --skip-score
python3 tools/validators/validate-repo.py --skip-cursor
```

校验 MongoDB 脚本 manifest、插件运行时映射、插件接口示例和知识资产 metadata：

```bash
python3 tools/validators/validate-mongodb-scripts.py
```

校验 golden path 与首个 collect 脚本合同：

```bash
python3 tools/validators/validate-golden-paths.py
```

校验 fixture 目录中没有运行期生成物：

```bash
python3 tools/validators/validate-fixture-hygiene.py
```

校验 `tools/` 与 `src/` 的结构边界没有回退：

```bash
python3 tools/validators/validate-tool-boundaries.py
```

当前校验范围：

- `core/taxonomies/` 中风险等级、状态、场景类型、能力类型和标签规范文件是否结构有效
- `script_id` 格式
- 必填字段
- `manifest.middleware` 是否为 `mongodb`
- `source` 是否为相对路径
- 脚本源文件是否存在
- `runtime` 与文件后缀是否匹配
- `phase` 是否与 `script_id` 对齐
- `mvp` 脚本数量是否为 10
- `script-runtime-map` 是否与 `default_packaged` 脚本对齐
- `runtime_path` 是否为插件包内相对路径
- `context.example.yaml` 是否满足最小 `context-file` 合同
- `output.example.yaml` 是否满足最小 `output-file` 合同
- `output-file.status` 是否为 `success` / `partial` / `blocked`
- `remote-executor-request.example.yaml` 是否满足最小请求合同
- `remote-executor-result.example.yaml` 是否满足最小结果合同
- 远程执行器请求中的 `script.runtime_path` 是否与 runtime map 对齐
- `remote executor.status` 是否为 `success` / `partial` / `blocked` / `failed`
- MongoDB 所有 runbook metadata 是否满足最小合同，且存在 `runbook.md`
- MongoDB 所有 command metadata 是否满足最小合同，且存在 `command.md`
- MongoDB 所有 skill metadata 是否满足最小合同，且存在 `skill.md`
- MongoDB runbook、command、skill 的风险等级和场景是否能匹配共性枚举
- `scenarios/*/scenario.yaml` 是否满足最小场景合同
- runbook、command、skill 引用的 scenario 是否存在对应场景定义
- runbook、command、skill 引用的 component 是否存在 MongoDB 组件入口
- skill `required_assets` 指向的资产目录是否存在
- `tests/fixtures/mongodb/*` 是否包含最小 replay fixture 文件集
- `adapter-output.example.yaml` 是否满足插件命令输出最小合同
- Kubernetes runtime signal 是否全部登记在通用 taxonomy，且 normalizer 不能发出未登记的点对点 signal
- `tools/plugin/`、`tools/analyse/`、`tools/remote-executor/`、`tools/remote-smoke/`、`tools/lib/` 是否仍保持薄壳边界
- `tools/*` 顶级子目录是否保留 README
- `src/` 是否错误反向导入 `tools/`
