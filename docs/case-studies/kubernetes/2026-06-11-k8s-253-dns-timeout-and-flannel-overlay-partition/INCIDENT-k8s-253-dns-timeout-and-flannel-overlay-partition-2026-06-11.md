# `k8s-253` DNS 超时与 Flannel Overlay 失联案例归档

事件日期: 2026-06-11
记录人: Codex
适用环境: `192.168.154.0/24` 三节点 control-plane 实验集群
故障节点: `k8s-253`
涉及组件: `flannel`、`kube-dns`、`kube-proxy`、`mongodb-sharded`

说明:

- 本文只记录只读巡检、证据链和分析路径
- 本次未执行任何修复动作
- 本文目标不是给出操作 SOP，而是沉淀一个可复盘、可投喂排障工具的分析 case

## 1. 最终结论

本次表面现象是 Mongo 启动时大量报 DNS 超时，但真正根因不是 CoreDNS 进程故障，而是:

- `k8s-253` 在 2026-06-11 启动窗口中，`flannel.1` VXLAN 设备被创建出来了，但没有进入 `UP` 工作态
- 结果是 `k8s-253` 对应的 Pod 网段 `10.244.1.0/24` 从集群 overlay 中脱离
- 该节点上的 Pod 只能访问本机 Pod，无法访问 `k8s-251` 与 `k8s-252` 上的 Pod
- 其他节点也无法访问 `10.244.1.0/24`
- `kube-dns` Service `10.96.0.10` 的一个后端正好在 `k8s-253`，因此整个集群都会出现随机 DNS 超时

额外确认:

- `psmdb-test/bnmongo-shard0-data-2` 还存在一条独立故障线:
  - WiredTiger 校验错误
  - `WT_PANIC`
  - `mongod` `SIGSEGV`
- 该问题与 DNS 故障并列存在，不是 DNS 导致的连带现象

## 2. 适合工具先输出的结论摘要

- 故障类型: `节点级 Pod 网络分区`
- 直接表象: `Pod 内 DNS 查询到 10.96.0.10:53 超时`
- 实际根因层级: `flannel overlay / VXLAN 设备未拉起`
- 故障范围:
  - `k8s-253` 本机 Pod 到远端 Pod 全断
  - 远端 Pod 到 `k8s-253` Pod 全断
  - 所有依赖 `10.244.1.x` 作为 Service 后端的 ClusterIP 可能出现失败
- 为什么容易误判成 DNS 故障:
  - 业务日志里直接报的是 `lookup ... on 10.96.0.10:53: i/o timeout`
  - 但 DNS Pod 本身是 Running
  - 真问题在 Service 后端与跨节点 Pod 路由

## 3. 现场现象

### 3.1 集群表面状态

- `kubectl get nodes -o wide`: `k8s-251`、`k8s-252`、`k8s-253` 都是 `Ready`
- `kube-flannel`、`kube-proxy`、`coredns` 都是 `Running`
- 控制面整体可访问，`kubectl` 可正常工作

这说明:

- 故障不是控制面整体不可用
- 故障具备较强迷惑性，因为节点和系统 Pod 都“看起来活着”

### 3.2 Mongo 业务表象

主要异常 Pod:

- `psmdb-test/bnmongo-mongos-6dc67fdd8f-dm6vx`
- `psmdb-test/bnmongo-shard0-data-0`
- `psmdb-test/bnmongo-shard0-data-2`

典型日志:

- `cannot resolve host "...": lookup ... on 10.96.0.10:53: i/o timeout`
- `timeout reached before the port went into state "inuse"`
- `MongoNetworkError: getaddrinfo EAI_AGAIN ...`

需要注意:

- `bnmongo-shard0-data-2` 的最终崩溃形态不是 DNS，而是 `ExitCode 139`
- 该 Pod 对应的是另一条存储损坏故障线

## 4. 关键证据链

### 4.1 `k8s-253` 的 `flannel.1` 明显异常

健康节点 `k8s-251` / `k8s-252`:

- `flannel.1` 状态为 `UP,LOWER_UP`
- 有本地 `/32` 地址:
  - `10.244.0.0/32`
  - `10.244.3.0/32`
- 有远端 PodCIDR 路由
- 有 FDB 邻居项
- 有正常收发计数

异常节点 `k8s-253`:

- `flannel.1` 状态为 `DOWN`
- flags 为 `0x1002`
- 缺少 `UP` 标志
- 没有 `10.244.1.0/32` 地址
- 没有远端 PodCIDR 路由
- 没有 FDB 邻居项
- RX/TX 计数均为 `0`

这组证据说明:

- VXLAN 设备不是“转发差”，而是根本没有进入工作态
- 故障位置早于 DNS 和业务连接阶段

### 4.2 Flannel 启动日志直接指向 VXLAN 路由安装失败

`k8s-253` 上 `kube-flannel` 的关键时间点:

- `2026-06-11 07:24:53Z`: 识别默认接口 `ens33`
- `2026-06-11 07:24:59Z`: `Interface flannel.1 mac address set`
- `2026-06-11 07:25:06Z`: 写入 `/run/flannel/subnet.env`
- `2026-06-11 07:25:06Z` 到 `07:26:49Z`: 持续报 `network is down`
- 最终报:
  - `failed to add vxlanRoute (10.244.0.0/24 -> 10.244.0.0)`
  - `failed to add vxlanRoute (10.244.3.0/24 -> 10.244.3.0)`

关键含义:

- `flannel.1` 已创建
- `subnet.env` 已写出
- 但在处理远端 subnet lease 时，VXLAN 路由无法安装
- 故障发生在 flannel 启动窗口，而不是业务 Pod 后续自行触发

### 4.3 节点状态被错误标绿

`kubectl get node k8s-253 -o yaml` 可见:

- `NetworkUnavailable=False`
- reason 为 `FlannelIsUp`
- 时间点是 `2026-06-11T07:25:06Z`

但同一时间窗口内，`flannel.1` 实际未 `UP`，且后续仍持续报 `network is down`。

这说明:

- 节点条件并不能代表 overlay 已真正恢复
- 工具如果只看 `Node Ready` 或 `NetworkUnavailable=False`，会误判

### 4.4 连通性实测证明 `10.244.1.0/24` 整段孤岛化

从 `k8s-253` 上的业务 Pod 发起探测:

- 能访问本机 `10.244.1.x`
- 无法访问 `10.244.0.x`、`10.244.3.x`

从 `k8s-251` / `k8s-252` 上的业务 Pod 发起探测:

- 无法访问 `10.244.1.9`
- 无法访问 `10.244.1.11`
- 无法访问 `10.244.1.13`
- 无法访问 `10.244.1.15`
- 无法访问 `10.244.1.17`

而且被测端口横跨:

- `27017`
- `9100`
- `3100`

都统一超时。

这说明:

- 问题不是单个进程监听失败
- 而是整个 `10.244.1.0/24` Pod 网段对外不可达

### 4.5 Underlay 正常，问题不在物理网络

在 `k8s-253` 的 `kube-flannel` Pod 内验证:

- `ping 192.168.154.251` 正常
- `ping 192.168.154.252` 正常
- `nc -vz 192.168.154.251 6443` 正常
- `nc -vz 192.168.154.252 6443` 正常

同时:

- `ens33` 为 `UP`
- `cni0` 为 `UP`
- 未看到专门拦截 `8472` 的 iptables / nft 规则

这说明:

- 物理网卡和节点间 underlay 联通是好的
- 控制面访问也是好的
- 故障聚焦在 flannel 的 overlay 层

## 5. 为什么它表现成 DNS 故障

### 5.1 `kube-dns` 后端池被坏节点污染

`kube-dns` Service:

- ClusterIP: `10.96.0.10`
- Endpoint 包含:
  - `10.244.0.24` on `k8s-251`
  - `10.244.1.10` on `k8s-253`

`kube-proxy` 规则显示:

- `10.96.0.10:53` 会在这两个后端之间随机分发
- `10.96.0.10:9153` 也同样随机分发

因为 `10.244.1.10` 所在网段已孤岛化，所以:

- 命中 `10.244.0.24` 时成功
- 命中 `10.244.1.10` 时超时

因此整个集群看到的是:

- `kube-dns` Pod 还活着
- `kube-dns` Service 有时成功，有时超时
- 日志里自然就变成 DNS 超时

### 5.2 为什么 `k8s-253` 上最严重

`k8s-253` 上的业务 Pod 同时叠加了两层问题:

1. 它们访问 `10.96.0.10` 时也可能随机命中坏 DNS 后端
2. 即使 DNS 偶尔成功，它们访问远端 Mongo Pod 也仍然失败，因为本机已经失去跨节点 Pod 路由

所以:

- 其他节点是“随机 DNS 失败”
- `k8s-253` 上是“DNS 不稳定 + 远端 Pod 全断”

## 6. 影响半径

### 6.1 直接受影响的 Mongo 组件

- `psmdb-test/bnmongo-mongos-6dc67fdd8f-dm6vx`
- `psmdb-test/bnmongo-shard0-data-0`

这两个实例的主要问题是:

- 启动阶段依赖 DNS 与远端 Mongo 成员发现
- 又恰好都落在 `k8s-253`
- 因此在 overlay 故障下无法完成初始化

### 6.2 运行中但实际上对外不可用的 Pod

位于 `k8s-253` 的下列 Pod 虽然是 `Running`，但对外等价于失联:

- `kube-system/coredns-66f779496c-sc4ht`
- `monitoring/loki-5b7bd6f78c-jnfnj`
- `monitoring/node-exporter-qsf6x`
- `monitoring/promtail-hj45v`
- `local-path-storage/local-path-provisioner-7666dfb7dd-jgt6s`
- `psmdb-test/bnmongo-configsvr-1`

### 6.3 受污染的 ClusterIP Service

已确认的典型例子:

- `kube-system/kube-dns`
  - 两个后端之一在 `k8s-253`
  - 远端访问表现为随机失败
- `monitoring/node-exporter`
  - 三个后端之一在 `k8s-253`
  - 远端访问表现为随机失败
- `monitoring/loki`
  - 唯一后端在 `k8s-253`
  - 远端访问表现为稳定失败

### 6.4 仍相对不受影响的组件

依赖宿主机网络的 `hostNetwork` 组件大多仍正常:

- `etcd-k8s-253`
- `kube-apiserver-k8s-253`
- `kube-controller-manager-k8s-253`
- `kube-scheduler-k8s-253`
- `kube-proxy-n7n59`
- `kube-flannel-ds-sbtsn`

这也是本案容易误判的原因之一:

- 控制面正常
- 节点 Ready
- flannel Pod Running
- 但 Pod overlay 已经坏掉

## 7. 与 Mongo 存储损坏的区分

本案中最重要的分层动作之一，是把 DNS/overlay 故障与 `shard0-data-2` 的数据损坏拆开。

`psmdb-test/bnmongo-shard0-data-2` 的关键证据:

- `ExitCode 139`
- `Got signal: 11 (Segmentation fault)`
- `WT_PANIC`
- `file:sizeStorer.wt: potential hardware corruption, read checksum error`

结论:

- `shard0-data-2` 不是“因为 DNS 坏了所以 CrashLoop”
- 它即使在网络恢复后，仍可能继续因为 WiredTiger 损坏而失败

工具在分析这类现场时，应避免把所有 Mongo 异常都归因到 DNS。

## 8. 推荐分析路径

适合排障工具的推理顺序:

1. 先看业务日志是否集中报 `lookup ... on 10.96.0.10:53: i/o timeout`
2. 不要立刻下结论为 CoreDNS 进程故障
3. 检查 `kube-dns` Pod 是否 Running
4. 检查 `kube-dns` Endpoint 是否含有位于异常节点的 Pod IP
5. 从业务 Pod 分别探测:
   - `10.96.0.10:53` 或 `:9153`
   - 本机 Pod IP
   - 远端 Pod IP
6. 检查故障节点上的:
   - `ip -d link show flannel.1`
   - `ip route | grep 10.244`
   - `bridge fdb show dev flannel.1`
   - `ip neigh show dev flannel.1`
7. 对照健康节点比较:
   - `flannel.1` 是否 `UP`
   - 是否有本地 `/32`
   - 是否有远端 PodCIDR 路由
8. 再看 flannel 日志中是否存在:
   - `network is down`
   - `failed to add vxlanRoute`

如果同时满足以下条件，应优先归因为 overlay 故障而不是 DNS 本身:

- `coredns` Pod Running
- `kube-dns` Endpoint 含有故障节点上的后端
- `flannel.1` 为 `DOWN`
- 故障节点缺少远端 PodCIDR 路由
- 远端节点访问该节点 `10.244.x.0/24` 全超时

## 9. 为什么知道下一步该往哪里查

这部分用于回答“为什么不是猜, 而是顺着证据走到下一步”。

### 9.1 为什么看到 DNS 超时后，没有先认定是 CoreDNS 崩溃

触发证据:

- 业务日志报的是 `lookup ... on 10.96.0.10:53: i/o timeout`

这条报错的含义不是“名字不存在”，而是:

- 请求已经发往 `kube-dns` Service `10.96.0.10`
- 失败模式是超时, 不是 `NXDOMAIN`
- 因此更像是查询链路失败, 而不是域名写错

所以这一步的自然下一跳是:

- 先查 `kube-dns` Pod、Service、Endpoint
- 而不是先查应用配置

### 9.2 为什么看到 CoreDNS Pod 还活着后，要继续查 Service 后端

触发证据:

- `coredns` Pod 是 `Running`
- CoreDNS 自身日志没有明显启动失败

这说明:

- “DNS 超时”不足以证明 DNS 进程坏了
- 还有很大概率是:
  - Service 后端池里有坏实例
  - kube-proxy 转发到不可达后端
  - Pod 网络本身断了

所以这一步的自然下一跳是:

- 看 `kube-dns` Endpoint 里到底有哪些后端 IP
- 再分别测 Service IP 和后端 Pod IP

### 9.3 为什么看到 `kube-dns` 有两个后端后，就知道要测“随机失败”模式

触发证据:

- `kube-dns` Endpoint 包含:
  - `10.244.0.24`
  - `10.244.1.10`
- 其中一个后端在故障节点 `k8s-253`

在 Kubernetes 里，这通常意味着:

- 如果两个后端都健康，Service 应该稳定成功
- 如果其中一个后端坏，Service 常见表现就是“有时成功，有时超时”

所以这一步我去测:

- `10.96.0.10:9153`
- 多次重复

结果确实出现成功与超时混合，这就把判断进一步压缩到:

- 不是整个 DNS Service 不存在
- 而是后端池质量有问题

### 9.4 为什么从这里会继续查 Pod 到 Pod，而不是继续盯 kube-dns

触发证据:

- `kube-dns` 有坏后端
- 坏后端位于 `10.244.1.10`

这时候要回答的问题就变成:

- 是 `10.244.1.10` 这个 CoreDNS 进程单点坏了
- 还是 `10.244.1.0/24` 整段 Pod 网络坏了

区分方法最直接的是:

- 从其他节点上的 Pod 去测多个 `10.244.1.x`
- 端口不要只测 53
- 最好横跨业务和监控端口

结果是:

- `27017`
- `9100`
- `3100`

对多个 `10.244.1.x` 都统一超时。

因此下一步就很明确:

- 这不是 CoreDNS 单点故障
- 这是节点级 Pod 网段故障

### 9.5 为什么节点级 Pod 网段故障会直接指向 flannel

触发证据:

- 本机 Pod 可达
- 远端 Pod 不可达
- 节点本身仍然 `Ready`
- 集群使用的是 flannel VXLAN

这类模式在 CNI 排查里非常典型:

- 本地 bridge 正常
- 跨节点 overlay 异常

所以最直接的证据位一定是:

- `flannel.1`
- PodCIDR 路由
- FDB / 邻居项

也就是:

- `ip -d link show flannel.1`
- `ip route | grep 10.244`
- `bridge fdb show dev flannel.1`

### 9.6 为什么还要再验证 underlay

即便看到 `flannel.1` 异常，也不能立即跳到“整机网络坏了”。

因为还需要区分:

- 是宿主机物理网络坏
- 还是仅 overlay 坏

因此必须补这一步:

- `ping 192.168.154.251/252`
- `nc 192.168.154.251/252 6443`

结果 underlay 正常，于是结论才能收敛成:

- `ens33` 正常
- API 正常
- 坏的是 flannel overlay

### 9.7 为什么把 `shard0-data-2` 单独拆出来

触发证据:

- `ExitCode 139`
- `WT_PANIC`
- checksum error
- `SIGSEGV`

这类证据和 DNS 超时完全不属于同一层。

所以这里必须做一次分叉:

- DNS / overlay 线
- WiredTiger 数据损坏线

否则会把“网络型故障”和“数据型故障”错误并案。

### 9.8 可供工具复用的判断模板

可以把本案的“下一步该查什么”简化成如下规则:

1. 如果日志是 `i/o timeout` 到 `10.96.0.10:53`, 先判断为“查询链路问题”，不要先判为名字不存在。
2. 如果 `coredns` Pod `Running`, 下一步必须查 Service 后端池，不要停在进程状态。
3. 如果 Service 访问结果是随机成功/失败，优先怀疑 Endpoint 池里混入坏后端。
4. 如果多个 `10.244.1.x` 地址、多个端口统一超时，优先怀疑节点级 Pod 网段分区。
5. 如果本机 Pod 通、跨节点 Pod 不通，优先查 overlay，不要先查业务配置。
6. 如果 `flannel.1` 存在但 `DOWN`，且缺少远端 PodCIDR 路由，应直接上升为 CNI/overlay 根因。

## 10. 排除项

本案中已明确排除:

- CoreDNS 进程直接崩溃
- 控制面 API 不可达
- 节点物理链路中断
- `ens33` 整机断网
- 业务单点监听故障
- 单纯 `Service` 规则缺失

证据基础:

- `coredns` Pod 为 `Running`
- `kube-proxy` 规则存在
- `ens33` `UP`
- underlay `ping` 与 API `6443` 探测正常
- 多个不同端口对同一网段统一超时

## 11. 适合投喂排障工具的 case 输入

### 11.1 一句话描述

`Kubernetes 节点 k8s-253 重启后 flannel VXLAN 设备 flannel.1 未进入 UP 态，导致 PodCIDR 10.244.1.0/24 从 overlay 脱离；因为 kube-dns 的一个后端位于该节点，整个集群表现为随机 DNS 超时。`

### 11.2 结构化摘要

```yaml
case_id: k8s-253-dns-timeout-flannel-overlay-2026-06-11
primary_symptom:
  - pod logs show "lookup ... on 10.96.0.10:53: i/o timeout"
root_cause:
  layer: cni_overlay
  component: flannel_vxlan
  node: k8s-253
  detail: flannel.1 exists but never enters UP state; remote podcidr routes not installed
cluster_impact:
  - k8s-253 pod subnet 10.244.1.0/24 isolated
  - kube-dns service randomly fails because one backend is 10.244.1.10 on k8s-253
  - services with only 10.244.1.x backends fail completely from remote nodes
key_evidence:
  - flannel.1 state DOWN on k8s-253
  - no 10.244.1.0/32 on flannel.1
  - no routes to 10.244.0.0/24 and 10.244.3.0/24 on k8s-253
  - flannel logs contain "network is down" and "failed to add vxlanRoute"
  - probes from healthy nodes to multiple 10.244.1.x pod IPs all timeout
false_leads:
  - coredns pod still running
  - node Ready and NetworkUnavailable=False
  - host underlay network is healthy
independent_secondary_issue:
  - bnmongo-shard0-data-2 has WiredTiger corruption and SIGSEGV
```

### 11.3 推荐判定规则

- 如果业务日志报 DNS 超时，但 `coredns` Pod 正常，先检查 `kube-dns` Endpoint 是否包含故障节点上的后端
- 如果故障节点的 `flannel.1` 为 `DOWN`，且缺少远端 PodCIDR 路由，应优先判断为 overlay 故障
- 如果远端到该节点多个 Pod IP、多个端口统一超时，应判断为 Pod 网段孤岛，而非业务单点故障
- 如果同批业务里既有 DNS 超时又有 `SIGSEGV`/数据校验错误，应拆成两条故障线分析

## 12. 本案留给排障工具的思路要求

工具在分析类似现场时，输出不应只停留在:

- `DNS timeout`
- `CoreDNS 异常`

而应该继续向下追问:

1. 这个 Service 的后端是否有节点级网络孤岛
2. 故障是发生在:
   - DNS 进程
   - kube-proxy 转发
   - Pod overlay
   - 宿主机 underlay
3. 当前错误是否只有一条根因，还是存在独立并发故障

本案的正确分析路径是:

`业务报 DNS 超时` -> `核实 kube-dns Pod/Endpoint` -> `发现后端含 10.244.1.10` -> `对比 flannel.1 与 PodCIDR 路由` -> `确认 k8s-253 overlay 脱离` -> `再把 shard0-data-2 的存储损坏单独分离`

## 13. 结论

- 本案不能简单归档为“CoreDNS 故障”
- 更准确的归档名称应是:
  - `k8s-253 flannel overlay 分区导致的集群随机 DNS 超时`
- 对业务最有价值的经验不是“重启 CoreDNS”
- 而是学会在 DNS 超时场景下优先检查:
  - 节点级 Pod 网络
  - Service 后端分布
  - CNI overlay 状态
  - 是否存在独立并发故障
