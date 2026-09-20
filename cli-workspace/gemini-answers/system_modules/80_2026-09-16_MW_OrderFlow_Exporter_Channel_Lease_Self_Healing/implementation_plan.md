# MW Order Flow 导出器 TICK 通道冻结：永久 FileLock → 通道租约与自愈 实施计划 (Plan)

- **日期**：2026-09-16（PT）
- **归属模块**：**M05. 多源实时数据流监控与数据接入引擎**（交叉引用 M02 订单流大单与微观结构量化分析引擎、M18 交易基础设施与开发环境工具链）
- **触发场景**：当日 17:12 起 ES/NQ `*_TICKS.csv` 永久冻结（数据健康面板「最后有效 17:12:27 · 3.1 小时前 · 文件已静止」、Order Flow 延迟 183 分钟），而**同一 JVM 的 DOM 通道仍在满速写**；用户要求把这次故障的根因修复按规范落档。
- **性质**：**根因修复（严重数据丢失故障）×1 + 安全护栏新增 ×2**（热部署守卫 / 写者空转判据），另带 2 处既有缺陷的顺带修复

---

## 1. 事故时间线与现象

| 时刻（PT） | 事件 |
| :--- | :--- |
| 17:03 | `~/MotiveWave Extensions/dev/bbt` 的 class 更新时间 = **17:03** |
| 17:04:01 | `.last_updated` = **17:04:01** ⇒ 当天该时刻有人/脚本**热部署了扩展** |
| **17:12:27.995（ES）/ 17:12:29.019（NQ）** | ES 与 NQ 的 `*_TICKS.csv` 在**同秒先后停止**增长，此后永久零字节增长 |
| 17:12:31.128–17:12:31.482 | 大单 CSV 出现同一批 7 笔大单的**批量重放**（ReportTime 11:55/12:00/12:10/12:15，TradeTime 仍是 11:54–12:12）⇒ MW 在该秒**重新实例化 studies** |
| 17:15 → 20:00:53 | **ES DOM 仍在满速写**：5 分钟 ≈35 万行 ≈**1200 行/秒** |
| → 20:40:45 | NQ DOM 一直写到 20:40:45 |
| 20:25 | 巡检日志仍报「✅ 全部文件健康 / 无新增异常」（旧 `IN_PROGRESS` 口径漏报；同一日志已记录 `45/79 条信号盘口数据缺失 (57%)`） |

**关键反差**：导出器进程活着、文件流没关，DOM 通道照写，唯独 TICK 通道零字节增长，且**不会自愈**。

---

## 2. 根因链与证据

### 2.1 五条证据

| # | 证据 | 推论 |
| ---: | :--- | :--- |
| 1 | ES / NQ 两个标的**同秒**停写 | 共同原因，**不是** ES 行情问题 |
| 2 | `lsof` 显示 MW(pid 69998) 仍以**写模式**持有两个 TICKS 文件（FD **71w / 81w**），却 3 小时零字节增长 | 导出器进程活着、流没关，只是**没有数据写进去** |
| 3 | MW 自身 tick 库 `~/Library/MotiveWave/historical_data/DXFEED/ESZ26.XCME/` 有 18:00/19:00/20:00 各小时文件（mtime **18:09 / 19:07 / 20:18**，NQ 同理到 20:03） | **行情源与 MW 都正常**，丢的只是导出器 |
| 4 | `~/Documents/MyDoc/Finance/Current/MotiveWave_Data/Single_Tick_Big_Trade/MW_Tick_BigTrades-ES-2026-09-16.csv` 里同一批 7 笔大单被写了**两遍**（实时一次 + **17:12:31.128–17:12:31.482** 批量重放一次，TradeTime 仍是 11:54–12:12） | MW 在 17:12:31 **重新实例化了 studies**（= 热重载） |
| 5 | `~/MotiveWave Extensions/dev/bbt` class mtime **17:03**、`.last_updated` **17:04:01** | 当天 17:03 **确有热部署动作** |

**旁证**：同一份 big-trades CSV 在 **09-10 17:04、09-11 17:06、09-15 21:55** 也有同样的「批量重放」痕迹 ⇒ **热重载是常态**，不是当日偶发。

### 2.2 根因链（四步）

```
MW 热重载扩展
   └─ 换 classloader
        ├─ 旧代 study 实例【不会被销毁】
        │     ├─ 仍持有已打开的 gzip 文件流
        │     └─ 仍注册在共享 `Instrument` 上的 DOMListener ⇒ DOM 继续写
        └─ 但 MW 不再给旧代投递 tick 回调（TickOperation 不再到达）
              ⇒ 旧代「写 DOM、不写 TICK」
                    ↓
上午刚引入的「每标的永久 OS FileLock」
   └─ 新代 tryLock() 抛 `OverlappingFileLockException`
        ⇒ 新代永久 passive、永不开流
              ⇒ TICK 通道无法自愈，**只能完全重启 MW**
```

**没有那把锁时的旧行为**：新代能「抢过 master」继续写（代价是**多写者 / gzip 交错损坏**，即归档 72 已确诊的 `UNREADABLE` 故障）。**加了锁之后**：从「写坏」变成「彻底锁死」——故障模式从数据损坏升级为**数据全丢且静默**。

---

## 3. 方案取舍：永久 FileLock → 按 (标的, 通道) 的租约 + 数据心跳

| 方案 | 热重载后可自愈 | 多写者风险 | 结论 |
| :--- | :--- | :--- | :--- |
| (A) 无锁（原始） | ✅ 新代抢 master 继续写 | ❌ 高（gzip 交错，实测 4 写者、EI 头 ×4） | 否决（归档 72 已证伪） |
| (A′) 永久 OS FileLock（当日上午） | ❌ 新代 `tryLock()` 抛 `OverlappingFileLockException` ⇒ 永久 passive | ✅ 无 | 否决（**本次事故直接成因**） |
| **(B) 通道租约 + 数据心跳（采纳）** | ✅ 最迟 3 分钟被新代接管 | ✅ 无（同一时刻仅一个写者） | **采纳** |

### 3.1 租约模型（关键设计）

- **粒度**：按 **(标的, 通道)** 独立 —— `dom` 与 `tick` **互不影响**。
- **租约文件**：`.<SYM>_exporter_<dom|tick>.lease`，内容一行：`<epoch> <instanceId> <lastDataMs> <pid>`
  - `epoch`：本实例创建时刻(ms)，越新越大（用于「新代优先」）
  - `lastDataMs`：**数据心跳**（该通道最近一次真的写出数据的时刻，非进程存活时刻）
  - `pid`：用于「持有进程已死」判定
- **三条接管规则（须同时成立）**：
  1. 我比持有者**新**（`epoch >=`）；
  2. 租约**数据心跳陈旧**（`> 3min`）**或**持有进程已死；
  3. 我最近 **60s 内确实收到过该通道回调**（防止无数据的新代抢走健康租约）。
- **持租者每秒校验所有权**（`verifyLeasesAndFiles()`），一旦失去就**关掉自己那条通道**（旧代因此不再空写 DOM）；主动 `cleanup()` 时释放租约，下一个实例可**立即接管**、无需等 3 分钟。
- **为什么要「数据心跳」而不是「进程心跳」**：进程活着但**被 MW 抛弃、收不到回调**正是本次故障形态；只有「最近真的写出过字节」才能区分「健康持租者」与「占坑的 ghost 旧代」。

---

## 4. 三处改动清单与关键代码点

### 4.1 `BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java`（核心）

**（1）废弃永久 FileLock，改为租约 + 数据心跳**

```java
private static final long STREAM_LEASE_STALE_MS   = 180_000L;  // 租约数据心跳陈旧阈值（可被更新的实例接管）
private static final long LEASE_CHECK_INTERVAL_MS = 1_000L;    // 所有权/外部写者校验间隔
private static final long LEASE_TOUCH_INTERVAL_MS = 1_000L;    // 数据心跳续租间隔

private java.io.File leaseFile(String symbol, String stream) {
    return new java.io.File(exportPath(), "." + symbol + "_exporter_" + stream + ".lease");
}

private boolean holdsStreamLease(String symbol, String stream, long lastSeenMs) {
    Lease l = readLease(symbol, stream);
    if (leaseIsMine(l)) return true;
    boolean iAmNewer   = (l == null) || (instanceEpochMs >= l.epoch);           // ① 新代优先
    boolean leaseStale = (l == null) || !leaseOwnerAlive(l)                     // ② 心跳陈旧 or 进程已死
                       || (now - dataMs > STREAM_LEASE_STALE_MS);
    boolean iHaveData  = (now - lastSeenMs) <= 60_000L;                         // ③ 我 60s 内真收到回调
    if (iAmNewer && leaseStale && iHaveData) { writeLease(symbol, stream, now); /* 接管 */ return true; }
    return false;
}
```

配套：`touchLeaseData()`（每秒续租，写 `lastDataMs=now`）、`releaseLease()`（cleanup 主动放弃）、`verifyLeasesAndFiles()`（每秒失租关流）。

**（2）`onTick` 外层 try/catch + 限流 error**

- 原来异常**直接抛回 MW 派发线程**；`processQueues` 原来是**空 catch** ⇒ 故障全静默（本次事故无法取证的原因之一）。

```java
public void onTick(Tick tick) {
    try { /* ... */ }
    catch (Throwable t) { errorThrottled("BBT: onTick error: " + t); }
}

} catch (Throwable t) {                       // processQueues：原来是空 catch(Exception)
    errorThrottled("BBT: write loop error: " + t);
}
```

**（3）看门狗（三种指纹，60s 节流 + 5min 心跳日志）**

| 指纹 | 判据 | 日志 |
| :--- | :--- | :--- |
| ① 收到 tick 但没拿到 TICK 流 | `tickSeenRecent && tickWriter == null` | `receiving ticks but TICK stream is NOT owned ...` |
| ② 有数据却写不进 | `writer != null && seenRecent && !writing` | `TICK/DOM writer idle Ns while ... arriving` |
| ③ 有 DOM 无 tick | `!tickSeenRecent && domSeenRecent` | `DOM callbacks alive but no tick callbacks ... likely a detached (pre-reload) generation` |

**（4）外部写者字节审计（`CountingOutputStream`）**

```java
long actual   = new java.io.File(path).length();
long expected = sizeAtOpen + counter.count();   // 我真正写出的字节数
if (actual > expected) return true;             // 别人也在追加 ⇒ 关掉自己那条通道
if (actual < expected) return true;             // 文件被外部替换/截断（如回填脚本换文件）⇒ 重开
```

原则：**宁少写，不错行写坏文件**。

**（5）其余加固**

- 跨日才触发 14 天清理（原来**每次 `setup` 都起一个 python 清理进程**）；
- 缺流重试**节流 1s**（`SETUP_RETRY_INTERVAL_MS`，防每 tick 刷 I/O）；
- 修复既有缺陷 A：「**日期未变但只判 `domWriter != null` 的早退**」会挡住 TICK 流重开（**本次事故的放大器**）；
- 修复既有缺陷 B：「**为补 TICK 会把健康的 DOM 流关掉再重开**」⇒ 两通道现在完全解耦。

### 4.2 `PyTools/order_flow/deploy_bbt_study.py`（热部署护栏）

- 新增 **`live_deploy_guard(force, mw_procs)`**：**MW 正在运行 + ES 活跃时段**时**默认拒绝部署**（退出码 **2**），需显式 `--force`。
- 安全窗口 = **ES 停盘**：**周六全天 / 周日 15:00(PT) 前 / 交易日 14:00–15:00(PT) CME 日维护**。
- `--force` 后的提示给出三条出路：等安全窗口 / `--force` 并**紧接着完全退出并重开 MW**（推荐）/ 接受「最迟 3 分钟 TICK 自愈」（前提：MW 里跑的是新版租约代码）。
- 部署成功后打印「**必须完全退出并重开 MotiveWave**」及自检命令。

### 4.3 `PyTools/jobs/mw_data_health_check.py` + `bbt_data_web/static/js/bbt_signals.js`（漏报封堵）

- 新增 **L5「写者空转 `WRITER_IDLE`」**：文件**仍被进程以写模式持有**（`lsof` w）但 **mtime 静止 > `WRITER_IDLE_MIN`(15min)**、**当前处于本该有数据的时段**（排除 QUIET 13:15–15:45 与周末），且**旁证成立**（同标的另一通道或另一标的同通道 5 分钟内仍在写；用于避免节假日/停盘误报）⇒ 状态 `WRITER_IDLE`（进入「需处理异常」与邮件报警，**不再是 `IN_PROGRESS` 静默**）。
- 无写句柄时给出「**写者缺席**（典型：MW 重启后该标的图表未加载）」处置文案。
- `probe_last_valid` 增加 `writers` / `writer_idle` 字段（`lsof` 结果按 `path+mtime` 缓存 **60s**，供看板 5 秒轮询）。
- `bbt_signals.js`「最后有效」徽标在写者空转时显示**红色「写者空转」**，而不是含糊的「文件已静止」。

---

## 5. 验证方法

| # | 验证项 | 命令 / 方式 |
| ---: | :--- | :--- |
| 1 | Java 编译 | `ant -f build/build.xml compile` → **BUILD SUCCESSFUL**（交付当时刻意未部署；实际于当晚 **21:07 / 21:11 / 21:16** 三次上线，见 walkthrough §6） |
| 2 | Python 语法 | `python3 -m py_compile PyTools/order_flow/deploy_bbt_study.py PyTools/jobs/mw_data_health_check.py` |
| 3 | 前端语法 | `node --check bbt_data_web/static/js/bbt_signals.js` |
| 4 | 热部署守卫 | `deploy_bbt_study.py --dry-run` 在 **20:50 PT** 应**拒绝**（`exit=2`）；加 `--force` 应通过 |
| 5 | 新判据有效性 | 用**当晚真实故障**做回归：MW 20:42:31 重启后 **NQ 图表未加载** ⇒ NQ 应被判 `WRITER_IDLE`（写者缺席 + 旁证「ES/TICKS 0.0 分钟前仍在写」），ES 应判 `OK` |
| 6 | 不误报 | 09-16 20:25 旧日志的反例（`IN_PROGRESS` 漏报）应在新口径下**不再出现** |

---

## 6. 回滚方式

| 层 | 回滚点 |
| :--- | :--- |
| Java 源码 | `src/bbt/StudyOrderFlowDataExporter.java.bak-20260916_204459`（同目录）——**覆盖回该文件即可** |
| Java 版本控制 | `BBT_Studies` 仓库 **git**（当前 `git status`: ` M src/bbt/StudyOrderFlowDataExporter.java`；上一个提交 `84e5788 auto: 2026-09-16 07:29 · BBT_Studies · 2 files · src`）⇒ `git checkout -- src/bbt/StudyOrderFlowDataExporter.java` |
| Python 两文件 | 由项目 git 管理；`deploy_bbt_study.py` / `mw_data_health_check.py` 均未触碰数据库 |
| 生效条件 | 回滚 Java 后需**重新 `ant` 编译并在安全窗口部署**才生效；回滚 Python 立即生效（Flask reloader） |

**回滚后的状态说明**：回退到「永久 FileLock」版本会**重新引入本次故障**（热重载后 TICK 永不恢复、只能重启 MW），故回滚仅作为「新版出现更严重问题」时的应急手段，并应同时恢复「禁止运行时热重载」的人工纪律。

---

## 7. 风险与不影响面

| 项 | 说明 |
| :--- | :--- |
| 首次部署需重启一次 MW | 新版（租约）代码部署后，**仍需重启一次 MW** 以清掉「不懂租约」的旧代 ghost；此后热重载可自愈 |
| 接管延迟 | 最坏 **3 分钟**（`STREAM_LEASE_STALE_MS`）；主动 cleanup 释放则为**即时** |
| 误接管风险 | 由「③ 我 60s 内确实收到过该通道回调」封堵：无数据的新代**不会**抢走健康租约 |
| 不影响 | 不触碰下单链路、不触碰数据库；DOM 通道与 TICK 通道解耦后互不拖累 |
| 部署节奏（已执行） | 交付时**刻意只编译未部署**（避免在交易时段热重载造成二次事故）；实际于当晚用一键脚本（**先退 MW → 部署 → 启动**，非热重载）三次上线：**21:07 → 21:11 → 21:16**。首次上线暴露并修复了本修复自身引入的「DOMListener 注册死锁」（DOM 通道写者 = 0）；21:16 上线看门狗 0 基线后，每次启动的假 SEVERE 由 **2 条 → 0 条**。详见 walkthrough §6 |
