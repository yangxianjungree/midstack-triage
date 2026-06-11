# 过程 4: 先找真实日志源, 再从应用日志拿到根因

## 定位

- **过程性质**: 有效的排障过程
- **当时起点**: 用户提出一个更扎实的问题, 即 "为什么这个 Pod 的日志这么少"
- **这轮产出**: 用 MongoDB 自己的文件日志直接证明 WiredTiger journal 损坏
- **保真说明**: 本文尽量保留了可复核命令和关键返回结果. 少数节点侧中间步骤只保留了事实结果, 没有完整 exact inspect 命令

## 原始实际经过

### 步骤 1: 先把问题改写成 "为什么 `kubectl logs` 这么少"

拿到什么:

- 正常情况下, `mongod` 启动失败后不应该只有一小行日志

当时怎么想:

- 与其继续猜 WiredTiger, journal, 配置, 权限, 不如先回答 "日志到底写到哪里"

为什么执行下一步:

- 只要真实日志源找对了, MongoDB 通常会自己把根因写出来

实际动作:

- 把排障问题从 "猜根因" 改成 "找日志 source"

返回结果:

- 形成了后续的正确问题树: 先查配置, 再查日志文件, 再查节点侧 Pod 卷

### 步骤 2: 查 `mongod` 配置里的日志 destination 和 path

拿到什么:

- 需要知道 MongoDB 日志到底写向 stdout/stderr 还是文件

当时怎么想:

- 先从健康 Pod 里看配置最稳妥
- 配置不依赖故障容器必须常驻

为什么执行下一步:

- 如果配置本身就说明日志写文件, 那么 `kubectl logs` 很短就有解释了

实际动作:

```bash
kubectl exec -n psmdb-test bnmongo-shard1-data-0 -- sed -n '1,220p' /opt/bitnami/mongodb/conf/mongodb.conf
```

返回结果:

关键配置如下:

```yaml
systemLog:
  destination: file
  path: /opt/bitnami/mongodb/logs/mongodb.log
```

这一小步的结论:

- `mongod` 日志默认写文件, 不是只写 stdout/stderr

### 步骤 3: 验证 `mongodb.log` 不是 stdout 链接

拿到什么:

- 配置里虽然写了文件, 但还需要确认这个文件是不是被重定向到了 `/dev/stdout`

当时怎么想:

- 很多镜像会把文件路径做成符号链接, 最终还是回到容器标准输出

为什么执行下一步:

- 只有确认它不是 stdout 链接, 才能合理解释为什么 `kubectl logs` 里看不到大部分日志

实际动作:

```bash
kubectl exec -n psmdb-test bnmongo-shard1-data-0 -- ls -l /opt/bitnami/mongodb/logs/mongodb.log
```

返回结果:

- `/opt/bitnami/mongodb/logs/mongodb.log` 是普通文件
- 它不是指向 `/dev/stdout` 的符号链接

这一小步的结论:

- `kubectl logs` 很短不是因为 MongoDB 没打日志
- 更可能是因为 MongoDB 日志根本不走容器 stdout/stderr

### 步骤 4: 找到故障 Pod 的 UID 和节点

拿到什么:

- 既然日志写文件, 而故障容器又可能起得太快退得太快, 就要准备从节点侧查看 Pod 卷

当时怎么想:

- 先拿 Pod UID 和 nodeName, 才能在节点上定位 kubelet 管理的 Pod 目录

为什么执行下一步:

- Pod 的 `emptyDir` 和容器日志目录都挂在节点本地文件系统上

实际动作:

最小可复核命令如下:

```bash
kubectl get pod -n psmdb-test bnmongo-shard1-data-2 -o jsonpath='{.metadata.uid}{" "}{.spec.nodeName}{"\n"}'
```

返回结果:

- Pod UID: `43578112-2542-4760-9b81-5bfd3be8255f`
- Node: `k8s-252`

这一小步的结论:

- 节点侧日志路径已经可以被确定到一个很小的范围

### 步骤 5: 先确认容器 stdout/stderr 日志文件本身也很短

拿到什么:

- 节点侧通过 `crictl inspect` 可以拿到容器日志路径

当时怎么想:

- 先确认容器标准日志文件是不是也只有那几行
- 如果是, 就进一步证明问题不在 `kubectl logs`, 而在日志 sink

为什么执行下一步:

- 这样可以避免误会成 "只是 `kubectl logs` 命令本身没拿全"

实际动作:

- 原始实际经过里, 节点侧用 `crictl inspect` 查到了容器日志路径
- exact inspect 命令串没有单独保留

返回结果:

- 容器日志路径是 `/var/log/pods/psmdb-test_bnmongo-shard1-data-2_43578112-2542-4760-9b81-5bfd3be8255f/mongodb/81.log`
- 这个路径里的内容仍然只有很短的 stdout/stderr 输出

这一小步的结论:

- 仅看容器标准日志文件也不够

### 步骤 6: 追到 Pod `emptyDir` 里的真实应用日志文件

拿到什么:

- 日志目录来自 Pod 内的 `emptyDir`

当时怎么想:

- 如果 `mongodb.log` 在 `emptyDir` 里, 那么真正要看的不是 `/var/log/pods/...`, 而是 kubelet 管理的 Pod 卷目录

为什么执行下一步:

- 只有找到这个真实文件, 才可能拿到 MongoDB 自己写的完整报错

实际动作:

先 SSH 到节点:

```bash
PW="$(python3 scripts/env/read_ssh_password_from_local.py)"
sshpass -p"$PW" ssh root@192.168.154.252
```

然后直接读取应用日志文件:

```bash
tail -n 60 /var/lib/kubelet/pods/43578112-2542-4760-9b81-5bfd3be8255f/volumes/kubernetes.io~empty-dir/empty-dir/app-logs-dir/mongodb.log
```

返回结果:

- 找到的真实日志文件路径是:

```text
/var/lib/kubelet/pods/43578112-2542-4760-9b81-5bfd3be8255f/volumes/kubernetes.io~empty-dir/empty-dir/app-logs-dir/mongodb.log
```

这一小步的结论:

- 终于进入了 MongoDB 真正的应用日志源

### 步骤 7: 直接从 MongoDB 日志拿根因

拿到什么:

- `mongodb.log` 里的关键报错

当时怎么想:

- 到这一步已经不需要猜
- 重点是让应用自己说出它为什么起不来

为什么可以在这里收敛:

- 因为这是 MongoDB 自己的错误日志, 不是从外部现象反推

实际动作:

继续读取同一个日志文件:

```bash
tail -n 60 /var/lib/kubelet/pods/43578112-2542-4760-9b81-5bfd3be8255f/volumes/kubernetes.io~empty-dir/empty-dir/app-logs-dir/mongodb.log
```

返回结果:

关键日志如下:

```text
__log_open_verify:938:log file journal/WiredTigerLog.0000000007 corrupted: Bad magic number 4294967295
WT_TRY_SALVAGE: database corruption detected
Failed to start up WiredTiger under any compatibility version
WiredTiger metadata corruption detected
Fatal assertion
```

这一小步的结论:

- 根因已经被直接点名
- `journal/WiredTigerLog.0000000007` 损坏导致 WiredTiger 无法启动
- `mongod` 因此启动失败

## 这轮为什么成立

- 每一步都是被上一步证据推动的
- 没有一步是因为事后知道答案才去做
- 根因来自应用自己的日志, 不是外部猜测

## 这轮留给后续工程师的通用套路

可以把这轮抽成一个很通用的顺序:

1. 先定失败层, 区分 K8s 编排失败和应用进程失败
2. 不默认 `kubectl logs` 就是完整日志
3. 先查应用日志 destination 和 path
4. 必要时追到节点侧的真实日志文件
5. 先让应用自己的日志给出根因, 再决定是否下探到底层文件
