# MW DOM 多写者损坏 —— 容错读取器尾部救援与 `--date` 归一化 验收报告 (Walkthrough)

> 归档目录：`72_2026-09-16_MW_DOM_MultiWriter_Reader_Tail_Rescue`
> 所属模块：**M05. 多源实时数据流监控与数据接入引擎**
> 验收时间：2026-09-16 07:15–07:22（PT）

## 1. 改动清单

| 文件 | 类型 | 改动要点 |
|---|---|---|
| `PyTools/py_lib/mw_gzip.py` | 缺陷修复 | ① `CHUNK_BYTES` `4MB → 256KB`；② 新增尾部救援（`TAIL_SCAN_BYTES=64MB`、`TAIL_RESCUE_MAX_FAILS=128`）；③ 主扫描算法原样抽为内层生成器 `_scan()`，`state["emitted"]` 跨两轮共享 |
| `PyTools/jobs/mw_dom_recover_and_recompute.py` | 缺陷修复 | ① 新增 `_norm_date()`（`20260916`/`2026-09-16`/`2026/09/16` 统一归一，非法格式 `ap.error()` 大声失败）；② `main()` 解析后归一化 `args.date`（覆盖 `--recompute-only` 与 `--all/--date`）；③ `import re` |
| `Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java` | 缺陷修复（**已实现+编译通过，未部署**） | 新增每标的「唯一写者」OS 级独占锁（`FileChannel.tryLock()` on `.<SYMBOL>_exporter.lock`）：`setupExporters()` 打开任何流之前先取锁，取不到即保持被动；`cleanup()` 释放；锁机制异常时 fail-safe 退回原 master 选举。原 master 选举逻辑保留 |

备份（回滚点）：
```
PyTools/py_lib/mw_gzip.py.bak-20260916_071501
PyTools/jobs/mw_dom_recover_and_recompute.py.bak-20260916_071501
~/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java.bak-20260916_072706
~/Library/MotiveWave/workspaces/dxFeed/config/windows.json.pre-multiwriter-fix-20260916_072340
```

未改动、未新建任何 MW 数据文件（见 §5 副作用核查）。

## 2. 验收结果

### 2.1 当日损坏文件：可读行数（`py_lib.mw_gzip.open_text`，引擎同一入口）

| 文件 | 修复前 | 修复后 | 耗时（后） |
|---|---|---|---|
| `ES_20260916_DOM.csv.gz` | **0 行** | **1,982,534 行**（首行 06:48:43） | 1.7 s |
| `NQ_20260916_DOM.csv.gz` | 306,933 行（仅 07:01 起） | **595,570 行**（首行 07:01:17） | 3.2 s |

### 2.2 5 分钟桶覆盖（健康巡检 `scan_timestamps`，同一读取器）

| 文件 | 行数 | 可读 5m 桶 | 丢失区间 |
|---|---|---|---|
| `ES_20260916_DOM.csv.gz` | 2,078,968 | `06:45 06:50 06:55 07:00 07:05 07:10 07:15` | 00:00–06:45（含 RTH 头 18 分钟） |
| `NQ_20260916_DOM.csv.gz` | 648,161 | `07:00 07:05 07:10 07:15` | 00:00–07:00（含 RTH 头 31 分钟） |

> 注：ES 另有一个时间戳被交错破坏的畸形行（桶键 `17895672011789567100000`）。引擎按窗口过滤，不会进入任何指标窗口；仅说明尾部仍残留个别坏行。

### 2.3 无回归（完好文件 / 纯 CSV 路径）

| 文件 | 修复前行数 / 耗时 | 修复后行数 / 耗时 | 判定 |
|---|---|---|---|
| `ES_20260915_DOM.csv.gz` | 62,457,090 / 23.1 s | **63,266,943 / 18.7 s** | 行数增加（旧分块丢弃的成员尾部被找回），更快 |
| `NQ_20260915_DOM.csv.gz` | 35,107,026 / 12.0 s | **35,218,220 / 14.2 s** | 行数增加，耗时同量级 |
| `ES_20260916_TICKS.csv` | 194,422 / 0.1 s | 195,852 / 0.1 s（文件在持续增长） | 纯 CSV 路径不变 |

### 2.4 自带回归测试

```
/usr/local/bin/python3 PyTools/jobs/test_mw_reader.py
Ran 7 tests in 0.032s — OK
```
（含 `test_undecodable_file_is_zero_lines_not_crash`：真正无可解码成员的文件仍必须是 0 行且不抛异常——尾部救援未破坏该契约。）

### 2.5 抢救/重算脚本：日期归一化与活跃保护

```
$ python3 PyTools/jobs/mw_dom_recover_and_recompute.py --date 2026-09-16 --dry-run
[dry-run] 待处理 1 个文件：
  ES 20260916
== 阶段 1/2：抢救 + 替换 ==
  ES 20260916: active(跳过: 正被 MotiveWav(pid 52035, fd 92w) 写入, 未抢救未替换)
== 阶段 3：重算盘口指标 ==
  20260916: 5 空 -> 重算 2 成功 / 3 无数据 / 0 失败
```

- 修复前该命令输出 `ES 2026-09-16: missing`（拼出 `ES_2026-09-16_DOM.csv.gz`，文件不存在）⇒ 全流程静默空跑；
- 修复后正确识别为当日活跃文件 ⇒ **拒绝替换**（规避 2026-09-10 事故模式）。

### 2.6 盘口指标重算（只写 `dom_metrics IS NULL` 的行）

```
$ python3 PyTools/jobs/mw_dom_recover_and_recompute.py --date 2026-09-16 --recompute-only
20260916: 5 空 -> 重算 2 成功 / 3 无数据 / 0 失败
```

| 信号桶 | dom_metrics | dom_snapshots | dom_max_gap_sec |
|---|---|---|---|
| 06:35 / 06:40 / 06:45 | 仍为 NULL（落在永久丢失区间，无数据可算） | — | — |
| 06:50 | **已写入** | 223 | 223.4（该桶只有部分窗口有数据，连续性问题已被如实记录在 payload 中） |
| 06:55 | **已写入** | 991 | 1.4 |

### 2.7 端到端：活管道自动恢复

`bbt_data_web`（5005）Flask reloader 在改动落盘后自动重启（新进程 PID 60749，启动于 **07:15:18**）。此后每个 5 分钟桶自动带上盘口指标，无需人工干预：

```
07:15 snapshots=911  max_gap=2.7  wi=0.017
07:20 snapshots=851  max_gap=2.9  wi=0.02   ← 修复后由活管道自动计算
```
（修复前这些桶全部为 NULL —— 健康巡检日志 07:01 已记录"5/6 条信号盘口数据缺失（83%）"。）

### 2.8 Java 修复部署后的验收（2026-09-16 07:29 部署 / 07:30:20 重启 MW）

| 验收项 | 期望 | 实测 | 结论 |
|---|---|---|---|
| 部署产物 | 新代码已上线 | `build/classes` 与 `dev/bbt/` 的 `StudyOrderFlowDataExporter.class` **md5 一致**（26,751 B），且含新锁标记串 | ✅ |
| 独占锁建立 | 每标的 1 个锁文件被 MW 持有 | `.ES_exporter.lock` / `.NQ_exporter.lock`（07:30 创建），`lsof` 各 1 个写 fd（PID 69998） | ✅ |
| 唯一写者 | 每数据文件 1 个写 fd | ES DOM/NQ DOM/ES TICKS/NQ TICKS 各 **1**（修复前热重载会累积到 8 个流） | ✅ |
| 写入速率 | ES≈4.4 KB/s、NQ≈3.5 KB/s | **ES 4,694 B/s、NQ 3,162 B/s** | ✅ |
| 重启切换是否干净 | 追加**独立新成员**，不再交错进坏区 | ES 新增成员 @389,608,638、NQ @283,404,730，均为独立可解成员 | ✅ |
| 数据连续性 | 首行不变、末行追到当前 | ES 3,154,783 行（06:48:43 → 实时）、NQ 1,268,305 行（07:01:17 → 实时） | ✅ |
| MW 日志 | 每标的仅 1 条 `Exporters ready (Master: true)` | 07:30:42(ES) / 07:30:59(NQ) 各 1 条；无异常、无 master 争抢、无 passive 记录 | ✅ |
| 管道端到端 | 各 5m 桶自动带盘口指标 | 07:15/07:20/07:25/07:30/07:35 全部落库；13 桶中仅剩 3 个 NULL（= 06:35/06:40/06:45 永久丢失区间） | ✅ |

**期间一次瞬时停滞（07:34:31 → 07:38，已自恢复）**，判定为 MW 自身背压而非本次改动：
- MW 日志 `07:36:04 WARNING Service::postQuote() unable to post quote! queue size: 10000 remaining: 0`，同时段伴随大量历史数据抓取与 `DXService::getBars() elapsed: 11582`（11.6 s）调用；
- **锁死锁不会自恢复**，而本次是自恢复的（四个文件在 07:38:26–07:38:31 全部恢复增长）；
- 旧代码时期同一会话的 07:05 桶已有 `max_gap=78.3s` DOM 间断，说明 MW 侧偶发间断是既有现象。
- 该间断被如实记录进盘口指标的连续性字段（07:30 桶 `max_gap=58.9`（重启窗口）、07:35 桶 `max_gap=42.3`）。

## 3. 根因与仍未闭环的部分

1. **多写者交错写坏（数据侧，未修）**：~~当日 00:00–07:00 期间有 ≈4 个导出流写同一文件~~ → **已升级为铁证结论**：MW 日志显示 **2026-09-16 00:00:00 同一秒内 8 条 `Exporters ready ... (Master: true, GZIP: true)`** ⇒ 8 个导出器实例各自打开当日文件。成因是 `masterId`/`masterLastActivity` 为 `static`（**每 classloader 一份**），MW 热重载扩展换 classloader 后静态表清空 ⇒ 新旧代实例互不可见、同时写同一文件；每次 `ant deploy`（18:41/18:43/21:18/21:45/21:55 及更多）多留一代写者，累积到午夜 8 个。
2. **代码侧已修（未部署）**：给导出器加 **OS 级独占锁**（`FileChannel.tryLock()`，JVM 级登记 ⇒ 跨 classloader 有效），`setupExporters()` 取不到锁即不开流、保持被动；`ant -f build/build.xml compile` **BUILD SUCCESSFUL**（19 源文件）；`~/MotiveWave Extensions/dev/bbt/` 仍是旧 class（未部署，避免盘中热重载再加一代写者）。
3. **已永久丢失**：ES 00:00–06:48、NQ 00:00–07:01 的盘口数据（dxFeed 无历史深度回放，无法重导）。
4. **健康巡检仍会误判**：多写者文件只要尾部可读就会被判 `OK`（当日 NQ 即如此，coverage 仅 1.2%）；`status` 与 `coverage` 未联动，也**尚未**加入"多写者指纹"（文件头连续空 gzip 头 > 1）告警。
5. **本次锁设计的残留风险（建议下一步加固）**：独占锁是"先到先得、仅在 `cleanup()` 释放"。若持锁实例后续不再收到 DOM/Tick 回调（图表停更 / 实例被 MW 静默弃用）而另一个实例成为 master，理论上会出现"持锁者不写、master 取不到锁"的停摆，需要重启 MW 才能恢复（本次 07:34 的瞬时停滞已排除为该机制所致，但风险仍然存在）。加固方向：
   - ① `checkAndInitExporters` 中检测到 `!isMaster() && exportLock != null` 时**主动 `releaseExportLock()` 并关闭自身流**；
   - ② 锁文件内写"持有者标识 + 心跳时间戳"并每 1 秒续期；取锁失败方在租约过期（建议 30 s）后视为死锁并接管（`tryLock` 失败 → 读租约 → 过期则记录告警并按旧行为兜底）。
   - 建议在收盘后窗口实施并复验，避免盘中引入新变量。

## 4. 部署与验收流程（需 MW 关闭窗口，用户执行/授权）

```bash
# ① 完全退出 MotiveWave（不是隐藏窗口）
# ② 部署 Java 修复（自带重复 jar 自检）
cd ~/Documents/Workplace/PycharmProjects/BBTrading
python3 PyTools/order_flow/deploy_bbt_study.py
# ③（可选）收敛同 JVM 内的重复 study 实例
cp /tmp/windows.single-exporter.json ~/Library/MotiveWave/workspaces/dxFeed/config/windows.json
# ④ 启动 MotiveWave
# ⑤ 运维硬规则：此后**禁止**在 MW 运行时 deploy/热重载
```

验收（启动 5 分钟后）：

```bash
lsof "/Users/zhijiebian/Documents/MyDoc/Finance/Current/MotiveWave_OrderFlow_Data/Raw/ES_20260916_DOM.csv.gz" | grep -c w
# 期望 = 1（每标的一个写 fd；修复前热重载后会变多）
# 30 分钟增量：ES ≈ 8 MB、NQ ≈ 6.5 MB（单写者量级）
```

## 5. 回滚方式

```bash
cd ~/Documents/Workplace/PycharmProjects/BBTrading
cp PyTools/py_lib/mw_gzip.py.bak-20260916_071501 PyTools/py_lib/mw_gzip.py
cp PyTools/jobs/mw_dom_recover_and_recompute.py.bak-20260916_071501 PyTools/jobs/mw_dom_recover_and_recompute.py
```
（`bbt_data_web` reloader 会自动重载。）

## 5. 副作用核查

- 无 `.broken` 文件产生，无 `Recovered/` 新产物（`Recovered/` 目录 mtime 仍为 2026-09-10，今日无任何写入）；
- 当日 4 个 MW 文件仅由 MW 自身（PID 52035）持续写入，未被执行任何 rename/替换；
- 数据库仅新增 2 行 `dom_metrics`（`--recompute-only` 走 `dom_metrics IS NULL` 过滤，不覆盖既有值）。
