# MongoDB Asset Validator Modules

`tools/validators/mongodb_assets/` 放 MongoDB 资产校验器的正式实现。

边界：

- `validate-mongodb-scripts.py` 只保留薄 CLI 入口。
- 这里放 MongoDB 资产合同、知识资产、fixture 校验的内部实现。
- 这里只服务工程校验，不属于插件 runtime 正式实现。

当前模块：

- `common.py`
  常量、字段合同、公共报错与 list 校验 helper。
- `contracts.py`
  taxonomies、scenarios、manifest、runtime map、example contract 校验。
- `domain_assets.py`
  runbook / command / skill metadata、fixture 校验。
- `cli.py`
  参数解析与总编排入口。
