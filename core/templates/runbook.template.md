# <Runbook Title>

## 适用场景

- <symptom or trigger>

## 目标

- <diagnosis goal>

## 前置条件

- <required access, tool, context, or safety confirmation>

## Step 1: <first diagnostic step>

执行：

```bash
<command>
```

检查：

- <expected signal>
- <abnormal signal>

## Step 2: <second diagnostic step>

执行：

```bash
<command>
```

判断逻辑：

- 如果 <condition>，则优先考虑 <cause>
- 如果 <condition>，则继续检查 <next area>

## 结论输出

```text
异常对象: <object>
当前状态: <state>
影响范围: <impact>
一级归因: <category>
下一步建议: <next action>
```

## 安全说明

- <readonly, low-risk, or high-risk boundary>
- <operation requiring explicit confirmation>
