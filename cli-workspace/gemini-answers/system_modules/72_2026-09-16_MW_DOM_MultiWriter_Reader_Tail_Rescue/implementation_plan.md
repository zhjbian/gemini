# MW DOM 多写者损坏 —— 容错读取器尾部救援与 `--date` 归一化 实施计划 (Plan)

> 归档目录：`72_2026-09-16_MW_DOM_MultiWriter_Reader_Tail_Rescue`
> 所属模块：**M05. 多源实时数据流监控与数据接入引擎**
> 日期：2026-09-16（PT）

## 1. 背景与问题

2026-09-16 早盘，MotiveWave（MW）导出的当日 DOM 文件出现"文件在增长但完全不可解码"故障：

| 文件 | 大小（07:10 实测） | 引擎可读行数 | 现象 |
|---|---|---|---|
| `ES_20260916_DOM.csv.gz` | 383 MB | **0** | 健康看板 `UNREADABLE`；`order_flow_signals.dom_metrics` 全天为 NULL |
| `NQ_20260916_DOM.csv.gz` | 279 MB | 306,933（仅 07:01 起） | 看板误判 `OK`（coverage 仅 1.2%） |

连锁影响：当日 `2026-09-16` 的 6 条 order flow 信号中 **5 条盘口数据缺失（83%）**，按项目既有认知属"静默降级"，是必须消除的失效模式。

## 2. 根因诊断（三类，按处置优先级）

### 2.1 多写者交错写同一文件（数据侧根因，本计划不修文件、只修读取器）
证据链：
1. 文件头是 **4 个连续的 10 字节空 gzip 成员头**（偏移 0/10/20/30）⇒ 文件为空时先后有 4 个 `GZIPOutputStream` 写入头；
2. 两份文件的**首个损坏点都在输入偏移 61,470**（≈ 一个 64 KB 缓冲）⇒ 之后是多个 deflate 流交错；
3. 体积速率：01:53→06:30 期间 ES 从 108 MB → 357 MB（≈15.6 KB/s），而 09-15 **全天**单写者文件仅 377 MB（≈4.4 KB/s）⇒ **≈3.6 倍**，与 4 写者吻合；
4. `lsof` 重启后每文件仅 1 个写 fd、速率回落到 5.0 KB/s（单写者）⇒ 交错发生在 00:00–07:00 之间；
5. 配置侧：活动工作区 `~/Library/MotiveWave/workspaces/dxFeed/config/windows.json` 内 `BBT_ORDER_FLOW_EXPORTER` 存在**多个 figure 实例**（id 24/28/32/37/38），`EXPORT_PATH` 指向同一 `MotiveWave_OrderFlow_Data/Raw` 的有 3 处（fig 24=ES 250ms、fig 32=NQ 500ms、fig 38=NQ ctxMap[5] 500ms）；09-14 备份里是 ES 2 个 + NQ 3 个。`~/MotiveWave Extensions/lib/` 已为空 ⇒ **不是**"dev/*.class + lib/*.jar 重复部署"。

### 2.1b 真正的根因：master 选举跨 classloader 失效（MW 日志铁证）
读取 MW 自身日志 `~/Library/MotiveWave/output/output (Sep-15 184111).txt`（夜盘会话）：

```
00:00:00 INFO BBT Order Flow Data Exporter: BBT: Initializing exporters for date: 20260916
00:00:00 INFO BBT Order Flow Data Exporter: BBT: Exporters ready for date 20260916 (Master: true, GZIP: true)
   ⋮  （同一秒内共 **8 条**，全部自称 Master: true）
```

即 **2026-09-16 00:00:00 同一秒内有 8 个导出器实例各自打开当日文件**。成因（代码级）：

- `masterId` / `masterLastActivity` 是 **`static`** ⇒ **每个 classloader 一份**；MW 热重载扩展会换 classloader ⇒ 静态表在新代里**是空的**，而旧代实例仍自认 master 且 `GZIPOutputStream` 保持打开 ⇒ 新旧代互不可见、**同时写同一文件**；
- 日志同时显示 18:41、18:43、21:18、21:45、21:55（= `ant deploy` 触达 `.last_updated` 的时刻）各出现一次 "Stole Master exporter"，即**每热重载一代就多一个永久写者**，累积到午夜共 8 个；
- `checkAndInitExporters` 的 `synchronized` 是**实例级**锁（不同实例互不互斥），`setupExporters` 内部还可在 2 s 阈值下自行夺取 master 并打开流；夺取时**不会关闭前任已打开的流** —— 于是交错写入持续整夜，最终 ES/NQ 当日文件从头部起不可解码。

这解释了全部观测：文件头 4 个连续空 gzip 头（多代 open）、两个标的首坏点同为 61,470（同一段逻辑同一毫秒作用于两个文件）、体积 3.6 倍（多代各写一份）、07:00 完整重启后回归单写者（同一 JVM 内只剩一代）。

### 2.1c 结论
- **数据侧**：00:00–06:48 的 ES 盘口数据永久丢失（dxFeed 无历史深度回放），只能接受；
- **代码侧（本次修复对象 2）**：让"唯一写者"判定**不依赖 classloader**。

### 2.2 容错读取器 `py_lib/mw_gzip.py` 的两处缺陷（本次修复对象）
`open_text()` 是 DOM 全链路的唯一读取入口（`dom_sentinel_evaluator` / `dom_features` / `dom_extremes` / 健康巡检均经它），实测对 ES 当日文件返回 **0 行**，而文件尾部其实有 **31.5 MB + 38.4 MB** 两段可用数据：

- **缺陷 A（分块过大 ⇒ 输出全丢 + 跳过后续成员）**
  `CHUNK_BYTES = 4 MB`。当成员中途损坏时，那一次 `decompress()` 会**丢弃该调用已解出的全部输出**（zlib 抛错即丢），且失败点 `p` 已越过 4 MB ⇒ 紧随其后的活成员被跳过。实测：成员 @378,651,997 有 31.5 MB 可用数据，失败点落在首个 4 MB 块内 ⇒ `got=False` ⇒ `pos = max(p, st+MIN_SKIP) = 382,846,311`，**直接跳过 382,159,420 的活成员**（该成员本身完全可读）。
- **缺陷 B（无尾部救援）**
  主扫描失败预算 `MAX_FAILS=500` 在超长交错坏区中耗尽后，不再尝试文件末尾——而 MW 的活成员永远在文件末尾。

### 2.3 抢救/重算脚本的日期格式缺陷
`PyTools/jobs/mw_dom_recover_and_recompute.py` 把 `--date` 的值**原样**拼进文件名：`--date 2026-09-16` → `ES_2026-09-16_DOM.csv.gz`（不存在）⇒ `salvage_and_replace()` 返回 `missing` ⇒ 抢救、替换、重算**全部静默空跑**（用户以为已处理，实际一行未动）。该脚本 help 写的是 `YYYYMMDD`，但没有任何归一化或格式校验。

## 3. 实施方案

### 3.1 `PyTools/py_lib/mw_gzip.py`
1. `CHUNK_BYTES`：`4 << 20` → `256 << 10`（把"单次丢弃"与"越界距离"限制在 256 KB，配合既有 `st + 1` 重扫逻辑即可接上后续成员）；
2. 新增**尾部救援**：主扫描一行未产出时，从「文件末尾 `TAIL_SCAN_BYTES`（64 MB）窗口内的第一个 gzip 头」重做一遍同样的容错扫描，独立失败预算 `TAIL_RESCUE_MAX_FAILS=128`；
3. 原主扫描算法**逐行保持**（含 2026-09-14 的 `pos = st + 1 if got` 修复与空成员跳过），仅抽出为内层生成器 `_scan(start, max_fails)`，`state["emitted"]` 跨两轮共享。

### 3.2 `PyTools/jobs/mw_dom_recover_and_recompute.py`
1. 新增 `_norm_date(s)`：只保留数字并校验长度 8，`20260916` / `2026-09-16` / `2026/09/16` 一律归一为 `YYYYMMDD`；格式非法则 `ap.error()` **大声失败**（不静默）；
2. `main()` 解析参数后统一归一化 `args.date`，覆盖 `--recompute-only` 与 `--all/--date` 两条路径。

### 3.3 `Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java`（多写者根因修复）
新增**每标的「唯一写者」OS 级独占锁**，与 classloader 无关：

1. 新字段 `exportLockChannel` / `exportLock` / `exportLockKey`；
2. `acquireExportLock(pathStr, symbol)`：对 `<EXPORT_PATH>/.<SYMBOL>_exporter.lock` 执行 `FileChannel.tryLock()`。
   - 同一 JVM 内第二次 tryLock 抛 `OverlappingFileLockException` ⇒ **连旧 classloader 的实例也能挡住**；
   - 跨进程返回 `null` ⇒ 顺带挡住多进程写者；
   - 锁机制自身异常时 **fail-safe 返回 true**（退回原有 master 选举语义），不让锁故障停掉整条导出管道。
3. `setupExporters()` 在 `Files.createDirectories(pathStr)` 之后、**打开任何流之前**调用；拿不到锁即 `return` 保持被动（不开流、不写，下次 tick 重试 ⇒ 前任释放后可自动接管）；
4. `cleanup()` 末尾 `releaseExportLock()`，保证实例被 MW 销毁时把写者名额让出；
5. 原 master 选举逻辑**保留不动**（日志与兼容性）。

### 3.4 运维硬规则（必须与 3.3 同时遵守）
**禁止在 MW 运行时做 `ant deploy` / 触碰 `.last_updated` 热重载** —— 热重载正是多代 classloader 的来源。
正确流程：**退出 MW → `deploy_bbt_study.py`（含重复 jar 自检）→ 启动 MW**。

### 3.5 可选加固（同 JVM 内的重复 study 实例）
活动工作区 `dxFeed` 的 NQ 图（tab3）仍有 4 个 `BBT_ORDER_FLOW_EXPORTER` figure（28/32/37/38，其中 fig 38 的 ctxMap[5] 上下文也指向 Raw）。已生成并校验"每标的只留一个"的配置补丁 `/tmp/windows.single-exporter.json`（移除 6 个节点；校验：每标的仅剩 1 个 exporter、其他 study 计数不变、无下标型字段错位风险）。**只能在 MW 关闭时替换**（MW 退出时会重写该文件）。

### 3.6 明确不做（避免二次事故）
- **不对当日活跃文件做任何 `rename`/替换**：MW 以写模式长期持有 fd，2026-09-10 已因此发生过"抢救快照替换活文件、当天 RTH 数据错位"的事故；
- 不尝试"分离交错流"抢救 00:00–06:48 数据（deflate 流交错后无法可靠切分，属永久丢失）。

## 4. 验收标准
1. `open_text()` 读 `ES_20260916_DOM.csv.gz` **不再返回 0 行**，且首行时间戳落在 06:48 附近；
2. 健康巡检 `scan_timestamps()` 对两个文件能给出 5 分钟桶覆盖（ES 自 06:45 起、NQ 自 07:00 起）；
3. **无回归**：完好文件（`ES_20260915_DOM.csv.gz` / `NQ_20260915_DOM.csv.gz`）行数不减、耗时同量级；纯 CSV（TICKS）路径不变；
4. `PyTools/jobs/test_mw_reader.py` 7 项自带测试全绿；
5. `--date 2026-09-16 --dry-run` 输出 `active(跳过: 正被 MotiveWave 写入…)`（不再是 `missing`），且**不修改任何文件**；
6. 重算仅补 `dom_metrics IS NULL` 的行，不覆盖既有值；
7. （Java 修复）`ant -f build/build.xml compile` 通过；部署+重启 MW 后：`lsof` 每个标的数据文件**恰好 1 个写 fd**，30 分钟增量回到单写者量级（ES ≈ 8 MB、NQ ≈ 6.5 MB），且 MW 日志只出现 1 条 `Another exporter holds the export lock ... passive`（若有多余实例）。

## 5. 回滚方案
`PyTools/` 未纳入 git 跟踪（`git status` 显示为未跟踪目录），故改动前已留同目录带时间戳备份：
- `PyTools/py_lib/mw_gzip.py.bak-20260916_071501`
- `PyTools/jobs/mw_dom_recover_and_recompute.py.bak-20260916_071501`

`BBT_Studies` 是 git 仓库（自动提交），Java 改动前另存了 `src/bbt/StudyOrderFlowDataExporter.java.bak-20260916_072706`：
- 回滚源码：`git -C ~/Intellj-workspace/BBT_Studies checkout -- src/bbt/StudyOrderFlowDataExporter.java`（或复制上面的 .bak）；
- 回滚已部署产物：重新 `deploy_bbt_study.py` 部署回滚后的源码，或从 `~/MotiveWave Extensions/dev/` 恢复。
- 回滚 MW 工作区配置：`cp ~/Library/MotiveWave/workspaces/dxFeed/config/windows.json.pre-multiwriter-fix-20260916_072340` 覆盖回去（须在 MW 关闭时）。
