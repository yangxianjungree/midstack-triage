# 过程 1: 只用 K8s 表层证据做首轮分层

## 定位

- **过程性质**: 失败的排障过程
- **当时起点**: 只知道 `@test` 有一个 Mongo Pod 起不来, 并且 `kubectl logs` 很少
- **这轮产出**: 只把问题缩到 "`mongod` 启动失败", 没拿到根因
- **保真说明**: 原始 exact 命令串没有完整留档. 本文同时记录原始实际经过, 以及为了让后续工程师复现同类观察而补充的等价动作

## 原始实际经过

### 步骤 1: 先定位故障对象

拿到什么:

- 有一个 Mongo 节点无法启动
- `kubectl logs` 很少

当时怎么想:

- 先不要猜根因
- 第一件事是把故障对象收敛到具体 Pod

为什么执行下一步:

- 如果连失败 Pod 都没锁定, 后面的事件, PVC, 节点, 副本集视角都没法对齐

实际动作:

- 原始实际动作是查看命名空间下失败 Pod 的状态和名称
- exact 命令未完整留档

返回结果:

- 故障对象收敛到 `psmdb-test/bnmongo-shard1-data-2`

这一小步的结论:

- 后续所有证据都应该围绕这个 Pod 来取

### 步骤 2: 判断是 K8s 没把 Pod 拉起来, 还是 Pod 里的 `mongod` 自己失败

拿到什么:

- Pod 处于 **`CrashLoopBackOff`**
- 最近一次退出是 **`exitCode=14`**

当时怎么想:

- 这更像是容器内进程启动后又失败, 不是调度阶段就起不来

为什么执行下一步:

- 需要继续确认有没有镜像拉取, Volume 挂载, 节点异常之类的 K8s 基础设施问题

实际动作:

- 原始实际动作是查看 Pod 生命周期和最近一次退出信息
- exact 命令未完整留档

返回结果:

- `CrashLoopBackOff`
- `reason=Error`
- `exitCode=14`

这一小步的结论:

- 故障层已经从 "K8s 没把 Pod 启起来" 缩到 "`mongod` 启动后失败退出"

### 步骤 3: 排除一批基础设施类问题

拿到什么:

- PVC 已绑定
- 节点看起来健康
- 没看到调度失败, 镜像拉取失败, Volume 挂载失败

当时怎么想:

- 这些结果足以排除一批很常见的 K8s 基础设施问题

为什么执行下一步:

- 还需要从同伴视角看故障成员表现, 判断它是在网络上完全不可达, 还是只是应用端口没有监听

实际动作:

- 原始实际动作是查看 PVC, Pod 事件, 节点状态
- exact 命令未完整留档

返回结果:

- PVC 不是问题
- 节点不是问题
- 调度, 拉镜像, 挂载不是问题

这一小步的结论:

- 这仍然只是排除法, 还不是根因

### 步骤 4: 从健康成员视角看故障节点

拿到什么:

- 健康成员看故障成员时返回 **`Connection refused`**

当时怎么想:

- 这说明故障成员没有正常监听 MongoDB 端口
- 但这还不能推出为什么没监听

为什么没有继续走通:

- 到这里, 我还没有立刻把注意力切到 "真实日志落点" 这个关键问题上
- 所以这轮停在了分层, 没进入根因取证

实际动作:

- 原始实际动作是从健康节点或健康 Pod 视角确认故障节点表现
- exact 命令未完整留档

返回结果:

- **`Connection refused`**

这一小步的结论:

- 只能说明目标节点没有正常提供服务

## 这轮结束时真正成立的结论

- 可以成立: `mongod` 启动失败
- 可以成立: 不是 PVC 未绑定, 调度失败, 镜像拉取失败, Volume 挂载失败
- 不可以成立: 这是 WiredTiger, journal, 本地数据损坏, 权限, TLS, 配置中的哪一类问题

## 这轮为什么没有走通

- 因为还没有拿到 MongoDB 自己的错误日志
- 因为 `kubectl logs` 很短这个现象, 当时还没有被提升成一个独立问题去处理

## 给别人复盘用的等价动作

下面这组命令不是原始逐字历史, 但可以帮助别人复现 "过程 1 能拿到的同类事实":

```bash
kubectl get pod -n psmdb-test bnmongo-shard1-data-2 -o wide
kubectl describe pod -n psmdb-test bnmongo-shard1-data-2
kubectl get pod -n psmdb-test bnmongo-shard1-data-2 -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}'
kubectl get pvc -n psmdb-test
kubectl get pod -n psmdb-test bnmongo-shard1-data-2 -o jsonpath='{.spec.nodeName}{"\n"}'
```

如果要补 "同伴视角" 这条事实, 需要按现场拓扑, 从健康成员或业务侧对故障成员做连接测试.

原始实际命令没有留档, 这里不补造一个看起来像原始历史的命令.

## 对后续工程师的提示

如果你在这里停住了, 下一步不要直接跳到 `journal/` 或数据目录.

下一步应该先回答:

- `mongod` 的日志到底写到 stdout/stderr, 还是写到文件
- `kubectl logs` 为什么这么短
