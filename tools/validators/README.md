# Validators

本目录存放仓库结构、资产合同、工程回归和运行时边界的校验工具。

## 边界

这里的校验器默认是“仓库侧校验”：

- 校验源码仓库里的资产、接口合同、回放数据、工具边界是否一致
- 校验本仓库打包出来的 runtime payload 是否满足预期结构
- 服务于开发、重构、提交前回归，不要求先安装 Claude 插件

这里不是“安装后插件自检”的唯一入口。

安装后的 Claude 插件完整性和本地依赖检查，走已安装 runtime 的自检：

- `plugins/claude/commands/validate.md`
- `plugins/claude/runtime/bin/selfcheck.py`

两者关系：

- `tools/validators/`
  仓库工程校验层，面向源码仓库
- `plugins/claude/runtime/bin/selfcheck.py`
  安装后插件包自检，面向已安装 runtime
- `plugins/claude/runtime/bin/validate-repo.py`
  只是把插件 bundle 内携带的 `tools/validators/validate-repo.py` 重新作为 runtime 命令入口暴露出来

## MongoDB Scripts

运行仓库最小回归验证套件：

```bash
python3 tools/validators/validate-repo.py
```

默认包含：

- MongoDB 资产与接口合同校验
- MongoDB fixture replay
- MongoDB replay score gate，默认要求所有评分维度至少达到 `medium`
- Fixture hygiene 检查，防止运行产物和敏感材料写回 `tests/fixtures/` 或 `tests/golden-paths/fixtures/`
- Kubernetes runtime 通用分类检查，防止故障分类点对点实现
- Cursor workspace-local runtime adapter 冒烟回归 (`plugins/cursor/test-agent-cli.py`)

可跳过 replay 或 score：

```bash
python3 tools/validators/validate-repo.py --skip-replay
python3 tools/validators/validate-repo.py --skip-score
python3 tools/validators/validate-repo.py --skip-cursor
```

校验已安装 Claude/Cursor 适配器的 sandbox 回归：

```bash
python3 tools/validators/validate-installed-adapters.py
python3 tools/validators/validate-installed-adapters.py --sandbox "$(realpath ../midstack-sandbox)"
```

默认 sandbox 是当前仓库的兄弟目录 `../midstack-sandbox`。该脚本只编排已有 installer、check 和 smoke 命令，不复制适配器内部检查逻辑。

校验 MongoDB 脚本 manifest、插件运行时映射、插件接口示例和知识资产 metadata：

```bash
python3 tools/validators/validate-mongodb-scripts.py
```

其中 CLI 壳保持在 `validate-mongodb-scripts.py`，正式实现位于 `tools/validators/mongodb_assets/`。

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
- `runtime_path` 是否为适配器运行时视图下的相对路径
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
- `tests/fixtures/active/mongodb/*` 是否包含最小 replay fixture 文件集
- `tests/fixtures/active/`、`tests/fixtures/legacy/` 和 `tests/golden-paths/fixtures/` 是否通过 fixture hygiene 检查
- `adapter-output.example.yaml` 是否满足插件命令输出最小合同
- Kubernetes runtime signal 是否全部登记在通用 taxonomy，且 normalizer 不能发出未登记的点对点 signal
- `tools/plugin/` 是否仍保持薄壳边界
- `tools/generators/generate-asset.py`、`tools/importers/import-runbook.py` 是否仍保持薄 CLI 边界
- `tools/validators/validate-mongodb-scripts.py` 是否仍保持薄 CLI 边界
- `tools/*` 顶级子目录是否保留 README；`tools/remote-executor/`、`tools/remote-smoke/`、`tests/replay/`、`tests/tools/analyse/` 等废弃兼容目录不得重新出现
- `src/` 是否错误反向导入 `tools/`
- `tools/lib/` 是否被重新引入
