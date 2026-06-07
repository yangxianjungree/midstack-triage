# Golden Paths

本目录存放端到端路由与合同级验收用例，用于验证「场景 → 资产 → 脚本合同」是否闭环。

与 `tests/fixtures/` 的区别：

- `fixtures/`：离线 replay analyse 逻辑
- `golden-paths/`：验证资产引用、场景路由、脚本最小合同

## 运行

```bash
python3 tools/validators/validate-golden-paths.py
```

可选 live 模式（需要本机 `kubectl` 与可访问集群）：

```bash
python3 tools/validators/validate-golden-paths.py --live
```

## 当前用例

- `mongodb-analyse-minimal.yaml`
  - `replica-inconsistency` 场景路由
  - skill / runbook / command 结构化引用
  - `mongodb.collect.pods.state` 合同测试（默认 blocked 场景，不依赖真实 K8s）
