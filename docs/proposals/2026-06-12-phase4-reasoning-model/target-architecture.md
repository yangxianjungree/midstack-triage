---
status: draft
last_updated: 2026-06-12
type: architecture-alignment
related:
  - ./pre-research.md
  - ./spec.md
---

# 第 4 段目标流程架构（对齐稿）

本稿综合 **Datadog Bits**（假设树 + 并行验证 + Agent Trace）、**AWS DevOps Agent**（竞争假设 + 正反证 + Investigation Journal）与 **midstack 设想**（多假设分轨、共享互补、只读补采），画出建议对齐的**目标架构**。

**用途：** 评审流程与边界，**不代表当前已实现**。

**概念展开图：** [④ 推理验证](../../concepts/diagrams/supplements/architecture-phase4-detail.png)（见 [architecture-overview.md](../../concepts/architecture-overview.md)）

---

## 1. 总览：五段中的位置

```mermaid
flowchart TB
    subgraph P3["第 3 段 · 信号采集与治理"]
        C1[远程/脚本采集]
        C2[signal_bundle / structured_record / collection_report]
    end

    subgraph P4["第 4 段 · 推理诊断与深入验证（本稿焦点）"]
        direction TB
        E0[证据上下文装载]
        H0[假设组合生成]
        subgraph ORCH["编排层 Orchestration"]
            T1[假设轨 H1]
            T2[假设轨 H2]
            T3[假设轨 Hn]
            BB[(共享推理黑板<br/>reasoning-board)]
        end
        LOOP{Evidence Loop<br/>需要补采?}
        RC[定向只读补采<br/>白名单 · 最多 1 轮]
        MERGE[Lead 合并与反证仲裁]
        DEEP{深入分支?<br/>条件触发}
    end

    subgraph P5["第 5 段 · 结论整合与知识沉淀"]
        OUT1[analysis.yaml]
        OUT2[report.md]
        OUT3[knowledge_candidates]
    end

    P3 --> E0
    E0 --> H0
    H0 --> T1 & T2 & T3
    T1 & T2 & T3 <--> BB
    T1 & T2 & T3 --> LOOP
    LOOP -->|critical_gap + 白名单动作| RC
    RC --> C2
    C2 --> E0
    LOOP -->|否 / 已达上限| MERGE
    MERGE --> DEEP
    DEEP -->|否| OUT1
    DEEP -->|代码/专家路径| DEEP
    DEEP --> OUT1
    OUT1 --> OUT2 & OUT3
```

**对齐点：**

| 外部概念 | 本架构落点 |
|----------|------------|
| Datadog hypothesis tree | 假设轨 + 黑板上的父子/分支关系 |
| Datadog Agent Trace | `reasoning-board` 步骤日志 + 可选 trace artifact |
| AWS Investigation Journal | `reasoning-board` 不可变追加式记录 |
| AWS Topology Graph | 第 3 段 `structured_record` + `signal_bundle` 对象关联 |
| midstack 定向补采 | Evidence Loop 内只读白名单补采，仍属单次 `/analyse` |

---

## 2. 第 4 段内部：O-R-A × 假设分轨（核心）

这是与 Datadog / AWS **最接近**的目标执行模型。

```mermaid
flowchart LR
    subgraph INPUT["输入 · 第 3 段证据包"]
        SR[structured_record]
        SB[signal_bundle]
        CR[collection_report]
        RD[analysis.rule-draft<br/>非权威草稿]
        KA[历史/runbook/skill<br/>假设来源 only]
    end

    subgraph LEAD["Lead · 调查指挥"]
        L1[装载上下文<br/>影响面 / 时间线 / gap]
        L2[生成假设组合<br/>2–5 条竞争假设]
        L3[分配假设轨任务]
        L8[合并 / 仲裁 / 结论 ceiling]
    end

    subgraph BOARD["共享推理黑板 reasoning-board"]
        B1[shared_findings]
        B2[cross_hypothesis_notes]
        B3[journal_steps]
        B4[open_gaps]
    end

    subgraph TRACKS["并行假设轨 · 最多 N 轨"]
        direction TB
        H1["轨 H1<br/>O→R→A 微循环"]
        H2["轨 H2<br/>O→R→A 微循环"]
        H3["轨 H3<br/>O→R→A 微循环"]
    end

    INPUT --> L1 --> L2 --> L3
    L3 --> H1 & H2 & H3
    H1 & H2 & H3 <-->|读/写 findings<br/>写 cross-refute| BOARD
    H1 & H2 & H3 --> L8
    L8 --> OUT[analysis.yaml 假设块<br/>+ conclusion_summary]
```

### 单条假设轨内的 O-R-A 微循环

（对应 Datadog「每条分支上的 observation-reasoning-action」）

```mermaid
flowchart TB
    O["Observation<br/>读黑板 + 证据包<br/>聚焦本假设"]
    R["Reasoning<br/>支持证据 / 反证 / gap<br/>是否可证伪?"]
    A["Action<br/>planned validation<br/>或请求补采项"]
    W{本轨结论?}
    S[supported]
    F[refuted]
    I[insufficient]

    O --> R --> A --> W
    W -->|支持充分| S
    W -->|反证充分| F
    W -->|证据不足| I
    S & F & I --> BOARD2[(写回黑板<br/>含 hypothesis_id)]

    style BOARD2 fill:#f9f9f9
```

**轨间「信息共享、互补」的具体含义：**

| 机制 | 作用 | 示例 |
|------|------|------|
| `shared_findings` | 避免重复采集/重复推理 | H2 已查过 CoreDNS，H1 不再重复 |
| `cross_hypothesis_notes` | 跨轨反证 | H1「DNS 故障」被 H3「overlay 分区」的反证削弱 |
| `journal_steps` | 审计轨迹（AWS Journal） | 每步 tool/推理/补采可追溯 |
| Lead 仲裁 | 解决冲突解读 | 同一日志两轨解读相反 → 结论降级 |

---

## 3. Evidence Loop：与假设轨的衔接

（midstack 已收敛：单次 analyse、最多 1 轮、只读白名单）

```mermaid
flowchart TB
    START[各假设轨标记 critical_gap<br/>+ validation_action planned]
    GATE{Lead 门禁}
    G1[仍有 insufficient 假设?]
    G2[gap 影响结论层级?]
    G3[白名单内可读动作?]
    G4[预期信息增益明确?]
    POOL[合并去重补采清单<br/>每轮 ≤ 2–3 动作]
    RUN[runner 执行定向补采]
    MERGE_A[merge 进 evidence 包]
    RELOOP[重新装载上下文<br/>假设轨继续 O-R-A]
    STOP[阶段性收尾<br/>gap + next_actions]

    START --> GATE
    GATE --> G1 & G2 & G3 & G4
    G1 & G2 & G3 & G4 -->|全满足| POOL --> RUN --> MERGE_A --> RELOOP
    G1 & G2 & G3 & G4 -->|任一不满足| STOP
    RELOOP --> START

    note1["与现状差异：<br/>补采触发应由 Lead+轨 gap 驱动，<br/>而非仅在规则 runner 之前"]
    GATE -.-> note1
```

---

## 4. 与 Datadog / AWS 的对照映射

```mermaid
flowchart TB
    subgraph DD["Datadog Bits"]
        DD1[Alert 上下文]
        DD2[假设树多分支]
        DD3[并发验证]
        DD4[Agent Trace]
        DD5[Investigation 树视图]
    end

    subgraph AWS["AWS DevOps Agent"]
        AW1[Topology Graph]
        AW2[并行竞争理论]
        AW3[正反证同时查]
        AW4[Investigation Journal]
        AW5[Triage 关联告警]
    end

    subgraph MS["midstack 目标"]
        MS1[signal_bundle + structured_record]
        MS2[假设轨 H1..Hn]
        MS3[并行 O-R-A 轨]
        MS4[reasoning-board journal]
        MS5[scenario 路由 + 历史案例]
    end

    DD1 -.-> MS1
    DD2 -.-> MS2
    DD3 -.-> MS3
    DD4 -.-> MS4
    DD5 -.-> MS4

    AW1 -.-> MS1
    AW2 -.-> MS2
    AW3 -.-> MS3
    AW4 -.-> MS4
    AW5 -.-> MS5
```

---

## 5. 深入分支（可选，非默认路径）

```mermaid
flowchart LR
    MERGE[Lead 合并后<br/>主假设仍 insufficient<br/>或怀疑平台/代码逻辑]
    Q{触发条件}
    D1[专家路径分支<br/>runbook 深步骤]
    D2[代码路径分支<br/>Git / 源码检索]
    CAP[结论 ceiling 保持<br/>不冒充已证实根因]
    OUT[写入 hypothesis 或 next_actions]

    MERGE --> Q
    Q -->|证据仍不足 + 有 playbook| D1 --> CAP --> OUT
    Q -->|明确怀疑实现缺陷| D2 --> CAP --> OUT
    Q -->|否| OUT
```

**与段名关系：** 「深入验证」在架构上 = 默认假设验证（上节 O-R-A）+ 本图条件分支；MVP 可先只实现前者。

---

## 6. 运行时角色与 artifact（实现视角）

```mermaid
flowchart TB
    subgraph RUNNER["tools/plugin · runner 侧"]
        R1[analyse 入口]
        R2[定向补采 executor]
        R3[finalize-analysis]
    end

    subgraph AGENT["Cursor Agent · 推理侧"]
        A1[Lead session]
        A2[假设轨 sub-task<br/>可选 2–3 并行]
    end

    subgraph ARTIFACTS["incident 目录 artifact"]
        direction LR
        F1[collection_report.yaml]
        F2[signal_bundle.yaml]
        F3[analysis.rule-draft.yaml]
        F4[reasoning-board.yaml<br/>新增 · 过程态]
        F5[analysis.yaml<br/>权威终态]
        F6[report.md]
    end

    R1 --> F1 & F2 & F3
    R1 -->|生成合同| TASK[agent-reasoning-task.md]
    TASK --> A1
    A1 --> A2
    A1 & A2 --> F4
    A1 --> F5 & F6
    A2 -->|请求补采| R2
    R2 --> F1 & F2
    F5 --> R3
```

| Artifact | 职责 | 类比 |
|----------|------|------|
| `reasoning-board.yaml` | 调查过程态：findings、journal、跨轨反证 | AWS Journal + Datadog Agent Trace |
| `analysis.yaml` | 调查终态：hypotheses 终局 + conclusion | Datadog Investigation 结论视图 |
| `agent-reasoning-task.md` | Lead 与轨的合同 | 编排指令 |

---

## 7. 与当前实现的差异（评审用）

```mermaid
flowchart LR
    subgraph NOW["当前实现"]
        N1[采集]
        N2[规则定向补采]
        N3[规则 rule-draft]
        N4[单次 Agent]
        N5[analysis.yaml]
        N1 --> N2 --> N3 --> N4 --> N5
    end

    subgraph TARGET["目标架构"]
        T1[采集]
        T2[rule-draft 种子]
        T3[Lead + 多假设轨]
        T4[黑板 + 并行 O-R-A]
        T5[Agent 驱动补采循环]
        T6[Lead 合并]
        T7[analysis.yaml]
        T1 --> T2 --> T3 --> T4 --> T5 --> T6 --> T7
    end

    NOW -.->|演进| TARGET
```

| # | 差异项 | 当前 | 目标 |
|---|--------|------|------|
| 1 | 假设执行 | 单 Agent 一次写完 | Lead + 2–3 并行假设轨 |
| 2 | 过程记录 | 无独立过程 artifact | `reasoning-board.yaml` |
| 3 | 轨间关系 | 仅在终稿 hypotheses 并列 | 黑板实时 cross-refute |
| 4 | 补采触发 | 规则先于 Agent | Agent/Lead 基于 gap 触发，仍 1 轮上限 |
| 5 | 深入分支 | 合同提及，无自动触发 | 条件门禁 + next_actions |

---

## 8. 建议评审问题

对齐本架构前，建议确认：

1. **假设轨数量上限：** 2 轨、3 轨，还是动态 2–5？
2. **黑板是否落盘：** 第一版要不要 `reasoning-board.yaml`，还是只在 Lead 上下文？
3. **补采顺序：** 是否接受「规则预补采（快路径）+ Agent 触发的第二轮（仍共 1 轮上限）」？
4. **深入分支：** MVP 是否只做合同/next_actions，不自动进入代码分析？
5. **Phase 5 边界：** Lead 合并时是否同时写 `knowledge_candidates`，还是拆分第二次调用？

---

## 9. 一句话定义（对齐用）

> **第 4 段 = 在共享证据上下文上，Lead 维护竞争假设组合，多条假设轨并行执行 O-R-A 微循环并通过推理黑板交换发现与反证；必要时经门禁触发一轮只读定向补采；最终由 Lead 仲裁产出受结论 ceiling 约束的 `analysis.yaml`。**
