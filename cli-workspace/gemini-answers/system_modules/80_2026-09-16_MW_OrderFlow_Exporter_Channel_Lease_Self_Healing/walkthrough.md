# MW Order Flow 导出器 TICK 通道冻结：永久 FileLock → 通道租约与自愈 验收报告 (Walkthrough)

- **日期**：2026-09-16（PT）
- **归属模块**：**M05. 多源实时数据流监控与数据接入引擎**（交叉引用 M02 / M18）
- **对应 Plan**：`80_2026-09-16_MW_OrderFlow_Exporter_Channel_Lease_Self_Healing/implementation_plan.md`
- **对应事故**：2026-09-16 17:12:27.995(ES) / 17:12:29.019(NQ) 起 ES/NQ `*_TICKS.csv` **永久冻结 3.1 小时**（DOM 通道未受影响）

---

## 1. 交付清单

### 1.1 代码改动（三处）

| 文件 | 改动 | 状态 |
| :--- | :--- | :--- |
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java` | ① 废弃永久 FileLock ⇒ 按 (标的, 通道) 租约 + 数据心跳 ② `onTick` 外层 try/catch + 限流 error、`processQueues` 空 catch 修复 ③ 看门狗三指纹 ④ 外部写者字节审计（`CountingOutputStream`）⑤ 跨日才触发 14 天清理、缺流重试节流 1s ⑥ 修复「早退挡住 TICK 重开」与「补 TICK 关掉健康 DOM」两个既有缺陷 | **已编译通过；当晚 21:07 / 21:11 两阶段部署上线（见 §6）** |
| `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow/deploy_bbt_study.py` | 新增热部署守卫 `live_deploy_guard()`：MW 运行中 + ES 活跃时段**默认拒绝**（`exit=2`），需 `--force`；安全窗口 = 周六全天 / 周日 15:00(PT) 前 / 交易日 14:00–15:00(PT)；部署成功后打印「必须完全退出并重开 MotiveWave」及自检命令 | 已落地并实测 |
| `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/mw_data_health_check.py` | 新增 **L5「写者空转 `WRITER_IDLE`」**（`lsof w` 有写句柄 + mtime 静止 > `WRITER_IDLE_MIN`=15min + 本该有数据时段 + 旁证成立）；无写句柄给出「写者缺席」处置；`probe_last_valid` 增 `writers` / `writer_idle`（lsof 按 `path+mtime` 缓存 60s，供看板 5 秒轮询） | 已落地并实测 |
| `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js` | 「最后有效」徽标在写者空转时显示**红色「写者空转」**（`color=#b91c1c`），替代含糊的「文件已静止」 | 已落地并实测 |

### 1.2 备份与回滚点

| 项 | 路径 |
| :--- | :--- |
| Java 源码备份 | `src/bbt/StudyOrderFlowDataExporter.java.bak-20260916_204459`（同目录，40698 B） |
| Java 版本控制 | `BBT_Studies` git（`git status`: ` M src/bbt/StudyOrderFlowDataExporter.java`；上提交 `84e5788`） |
| 回滚命令 | `git checkout -- src/bbt/StudyOrderFlowDataExporter.java` 或覆盖回 `.bak-20260916_204459` |

> **注意**：回退到「永久 FileLock」版本会**重新引入本次故障**（热重载后 TICK 永不恢复、只能完全重启 MW），仅作应急。

### 1.3 验收时的状态与当晚的上线

- **验收当时（20:5x）刻意未部署**：`ant deploy` 会触发热重载，在交易时段部署等于**主动复现本次事故**，故当时只编译、不部署。
- **当晚 21:07 / 21:11 / 21:16 已完成三次上线**：21:07 首次部署（先退 MW → 部署 → 启动）暴露并修复了本次修复自身引入的「**DOMListener 注册死锁**」；21:11 修复后二次上线，四通道全绿；21:16 三次上线完成看门狗 0 基线修复（启动假 SEVERE 2 条 → 0 条）⇒ 详见 **§6 上线实录**。
- 全过程未改数据库；MW 的停止/启动由一键脚本完成（详见 §6.6）。

---

## 2. 验收清单逐条核对

| # | 验收口径 | 结果 | 证据 |
| ---: | :--- | :--- | :--- |
| 1 | Java `ant -f build/build.xml compile` → BUILD SUCCESSFUL | **PASS** | 编译通过（验收当时刻意未部署：部署会热重载）；**当晚 21:07 / 21:11 / 21:16 三次上线并复测**（见 §6） |
| 2 | 两个 Python 文件 `py_compile` 通过 | **PASS** | `$ python3 -m py_compile PyTools/order_flow/deploy_bbt_study.py PyTools/jobs/mw_data_health_check.py` → `PY_COMPILE_OK`（exit 0） |
| 3 | `node --check bbt_signals.js` 通过 | **PASS** | `$ node --check bbt_data_web/static/js/bbt_signals.js` → `NODE_CHECK_OK`（exit 0） |
| 4 | `deploy_bbt_study.py --dry-run` 在 20:50 PT **正确拒绝**（exit=2） | **PASS** | 见 §3.1（`exit=2`） |
| 5 | 加 `--force` 后通过 | **PASS** | 见 §3.2（`exit=0`） |
| 6 | 新判据当晚**抓出真实故障**（NQ `WRITER_IDLE` / ES `OK`） | **PASS** | 见 §4 |
| 7 | 旧口径漏报的反例被记录 | **PASS** | 20:25 巡检日志「✅ 全部文件健康 / 无新增异常」，而同一日志已记录 `45/79 条信号盘口数据缺失 (57%)` |

**7/7 全部通过。**

---

## 3. 实测命令输出

### 3.1 热部署守卫在 20:50 PT 正确拒绝（`exit=2`）

```console
$ python3 PyTools/order_flow/deploy_bbt_study.py --dry-run
=== ⓪ 热部署守卫（MW 运行中 + ES 活跃时段）===

  ✗ [热部署守卫] 拒绝执行：ES 活跃交易时段，且 MotiveWave 正在运行。

    为什么危险（2026-09-16 17:12 实测事故，TICK 冻结 3.1 小时）：
      MW 热重载扩展会换 classloader，旧代 study 实例**不会被销毁** —— 它继续持有已打开的文件流
      与 Instrument 上的 DOMListener（所以 DOM 还在写），但 MW **不再给它投递 tick 回调**
      ⇒ 旧代"写 DOM、不写 TICK"；若新代再被旧的「永久 FileLock」挡住，TICK 文件就从那一刻起冻结，
      只能**完全重启 MW** 才能恢复。
      新版「通道租约」设计已能自愈（最迟 3 分钟内新代接管 TICK），但**首次部署该版本后仍需重启一次 MW**
      以清掉不懂租约的旧代 ghost。

    建议：
      1) 等到安全窗口（周六全天 / 周日 15:00 前 / 交易日 14:00–15:00 PT）再部署；或
      2) `--force` 部署，并**紧接着完全退出并重开 MotiveWave**（推荐）；或
      3) 只想马上部署：`--force`，接受"最迟 3 分钟 TICK 通道自愈"（前提：MW 里跑的是新版租约代码）。

exit=2
```

⇒ 守卫**没有**拦住 dry-run 的其余检查（它在 `⓪` 步直接中止），符合「默认拒绝」设计。

### 3.2 加 `--force` 后通过（`exit=0`）

```console
$ python3 PyTools/order_flow/deploy_bbt_study.py --dry-run --force
=== ⓪ 热部署守卫（MW 运行中 + ES 活跃时段）===
  ⚠ [热部署守卫] ES 活跃交易时段 + MotiveWave 正在运行（1 个进程）→ 已按 --force 继续
     检测到 MotiveWave 正在运行：15834 (共 1 个相关进程)

=== ① 部署前自检（重复部署 / 双写者）===
  ✓ [部署自检] 无重复部署（lib/ 与 dev/ 无同名 class）

=== ② ant deploy（clean → compile → 部署到 dev/ + touch .last_updated）===
  --dry-run：跳过实际编译部署
exit=0
```

⇒ 拒绝路径与放行路径**都**实测；`--dry-run` 未真正编译部署（`--dry-run：跳过实际编译部署`）。

### 3.3 语法与编译

```console
$ python3 -m py_compile PyTools/order_flow/deploy_bbt_study.py PyTools/jobs/mw_data_health_check.py
PY_COMPILE_OK

$ node --check bbt_data_web/static/js/bbt_signals.js
NODE_CHECK_OK

$ (BBT_Studies) ant -f build/build.xml compile
BUILD SUCCESSFUL
```

---

## 4. 当晚真实故障被新判据抓出（本轮最有价值的验证）

**背景**：20:42:31 重启 MW 后，**NQ 图表未加载** ⇒ NQ 的 TICK / DOM 通道从 20:41 起**没有写者**（MW 未给该标的实例化 study），而 ES 仍在正常写。

**新判据（L5）判定结果**：

| 标的 / 通道 | 判定 | 依据 |
| :--- | :--- | :--- |
| **NQ / TICKS** | **`WRITER_IDLE`（写者缺席）** | 无写句柄 + mtime 静止；**旁证成立**：「ES / TICKS **0.0 分钟前**仍在写」⇒ 排除停盘 / 节假日误报 |
| **ES / TICKS** | **`OK`** | mtime 正常推进（20:44+ 恢复写入） |

**这一条验证同时证明了三件事**：

1. **旁证机制有效**：若无「同标的另一通道 / 另一标的同通道 5 分钟内仍在写」这条旁证，NQ 的「无写者」既可能是故障也可能是停盘；旁证把它钉死为**故障**。
2. **口径切换生效**：NQ 在旧口径下会被判 `IN_PROGRESS`（静默），在新口径下**进入「需处理异常」与邮件报警**。
3. **与 20:25 的漏报形成对照**：同一套系统，20:25 报「✅ 全部文件健康 / 无新增异常」，而当时 ES/NQ TICK 已冻结 3 小时以上 ⇒ **旧口径的系统性漏报**正是本次事故「静默 3.1 小时」的直接原因。

---

## 5. 当天已执行的恢复（A 步，先于 B 步修复）

按「先救数据、再修根因」顺序，当天先完成 A 步恢复：

| 步骤 | 动作 | 结果 |
| ---: | :--- | :--- |
| 1 | 用户**完全退出 MW** | 释放 FD 71w / 81w 与旧代 ghost |
| 2 | `python3 PyTools/jobs/mw_tick_backfill_missing.py --date 2026-09-16 --tickers ES,NQ --apply` | 见下表 |
| 3 | 20:42:31 重启 MW | **ES 双通道恢复**（TICKS mtime 20:44+）；**NQ 因图表未加载仍未恢复**（由新判据抓出，见 §4） |

**回填明细（实测）**：

| 标的 | 回填笔数 | 空桶 | 合并后行数 | 原文件备份 |
| :--- | ---: | ---: | ---: | :--- |
| ES | **35,990** | 54 | **1,078,762** | `*-bk_20260916_204127.csv` |
| NQ | **19,434** | 39 | **483,951** | `*-bk_20260916_204128.csv` |

---

## 6. 上线实录（21:07 / 21:11 / 21:16）

> 本节为验收之后（当晚）的实际上线记录：**首次上线即暴露了一个由本次修复自身引入的新 Bug**，修复后二次上线达到全绿；**21:16 又完成第三次上线**（看门狗 0 基线，见 §6.5）。三次均遵循「**先完全退出 MW → 部署 → 启动 MW**」，**未使用热重载**。

### 6.1 阶段一：21:07 部署（MW 先退出、后启动）—— TICK 正常，DOM 全静默

| 项 | 实测 |
| :--- | :--- |
| 21:08:30 | 启动 MW（新版代码） |
| TICK 通道 | **正常**：日志 `claimed TICK lease for NQ/ES` → `TICK stream opened` → `Exporters ready ... DOM: passive, TICK: open`；两标的 TICKS 文件持续增长，**写者 = 1** |
| DOM 通道 | **两个通道完全没有写者**（`lsof` 写者 = **0**），且**从未生成** `.ES/NQ_exporter_dom.lease` |
| 日志噪音 | 每秒刷 `DOM stream stays passive for ES/NQ (another generation holds the lease)` |

### 6.2 阶段一新 Bug 根因：DOMListener 注册死锁（本次修复引入）

```java
// 错误写法（阶段一）：把监听器注册放在「DOM 流已打开」分支里
if (domWriter != null) { /* ... */ } else {
    if (holdsStreamLease(sym, "dom", lastDomSeenMs)) {
        openDomStream();
        instrument.addListener((DOMListener) this);   // ← 只在开流之后才注册
    }
}
```

死锁环：**不开流 → 不注册监听器 → 收不到 DOM 回调 → `lastDomSeenMs` 恒为 0 → 永远申领不到 DOM 租约 → 永不开流**。

**语义错误**：DOM 回调本是「能申领 DOM 租约」的**前提**，而不是它的**结果**。

### 6.3 阶段一同时暴露的次要问题

| # | 问题 | 现象 |
| ---: | :--- | :--- |
| 1 | 被动实例每秒重入 `setup` 并刷 3 行日志 | 无节流 ⇒ 日志噪音（也掩盖了真正的故障信号） |
| 2 | 看门狗基线从 0 起算 | 打出假 SEVERE：`TICK writer idle 1789618291s` |

### 6.4 阶段二：21:11 修复后重新部署 + 重启 —— 全绿

**代码改动**：

1. **`DOMListener` 注册改为在 `setupExporters` 开头无条件、尽早执行**（不再与开流耦合）；日志 `DOMListener registered on shared Instrument for NQ/ES`。
2. **租约申领分两类语义**：
   - **无租约（`l == null`）⇒ 直接引导接管**（不再要求「我已在收该通道数据」——那正是死锁点）；
   - **有租约 ⇒ 才是抢夺**（要求「租约陈旧」+「我确实在收该通道数据」）；
   - 写入后**回读确认**（并发抢夺时只有最后写租约者胜出）。
3. **日志节流**（无状态变化时最多每分钟一行）+ 被动消息改为可诊断（`no DOM callback yet` / `Ns since last tick callback` + `lease=epoch …, data=…s ago, pid … alive/DEAD`）。

**21:11:31 / 21:11:34 实测日志（两标的）**：

```console
claimed DOM lease for NQ/ES (vs none)
DOM stream opened (sizeAtOpen=382848321 / 533454910)
claimed TICK lease
TICK stream opened
Exporters ready ... DOM: open, TICK: open
```

**21:12 实况（四通道全绿）**：

| 校验项 | 结果 |
| :--- | :--- |
| 四个文件（ES/NQ × TICKS/DOM）写者数 | **各 = 1** |
| mtime | **实时**（21:11:58–21:12:03） |
| 4 个租约文件归属 | **同一实例**：ES `epoch 1789618282059 / 17925931`、NQ `epoch 1789618284477 / b91e7244`，`pid 35167`（= MW） |
| 末行 tick 时间戳 | = 当前时刻 |

### 6.5 看门狗 0 基线修复：已于 21:16 部署并验证（假 SEVERE 2 条 → 0 条）

- **修复内容**：开流时初始化 `lastDomWriteMs / lastTickWriteMs`，并在 `lastXxxWriteMs == 0` 时**不判空闲**、心跳打印 `never`。
- **上线**：**21:16** 用一键脚本（**先退 MW → 部署 → 重启**）上线；**产物断言通过**（`claimed` = 1、`export lock unavailable` = 0）。
- **验证**：上一次启动（**21:11**）日志有 **2** 条假 SEVERE（`TICK/DOM writer idle 1789618xxx s`）；本次启动（**21:16:33**）`grep -c "writer idle"` = **0**。
- **同时验证的两条设计意图（正面证据）**：
  1. **进程存活判定有效**：新实例在 **21:17:05** 立刻接管 —— `claimed TICK lease for ES (my epoch …616853 vs …282059; previous data 45s ago)`；旧实例 `pid 35167` 已 **DEAD**，因此**不必等满 3 分钟的陈旧阈值**。
  2. **被动消息可诊断**：同一秒 `DOM stays passive for ES (no DOM callback yet; lease=epoch …, data=41s ago, pid 35167 DEAD)`，随后 **21:17:06** `claimed DOM lease for ES`；心跳行 `DOM=no-stream TICK=writing lastDomWrite=never lastTickWrite=0s ago`（其中 `never` 即本次修复引入的输出）。

### 6.6 本次同时修好的工程细节（脚本类）

- 新增一键脚本 `PyTools/order_flow/deploy_bbt_and_restart.sh`（**优雅退出 MW → 部署 → 产物断言 → 启动 → 自检**）。首版两个 Bug：
  1. bash 在 `set -u` 下把「变量紧跟中日韩字符」当成变量名的一部分（`$rc）`、`$n_new；`）⇒ 改为 `${rc}` / `${n_new}`；
  2. 自检等待条件会命中**上一会话**的旧日志 ⇒ 改为启动前记录日志清单，**只认本次新会话日志**，并要求出现 `DOM: open, TICK: open`。
  - 修好后 `--check` 只读自检实测**全绿**。
- **部署产物断言手法**（防「部署了旧代码」）：

```console
$ grep -a -c "claimed "                 <deployed class>   # 必须 ≥ 1
$ grep -a -c "export lock unavailable"  <deployed class>   # 必须 = 0
```

### 6.7 `--backfill` 合并停机 + `cmd.py` 菜单接入

**（1）一键脚本支持「部署 + 回填」合并停机**

- `PyTools/order_flow/deploy_bbt_and_restart.sh` 新增参数解析：`--check`（只自检）/ `--backfill`（在「部署后、启动 MW 前」顺带回填当天 TICK 缺口）/ `--help`。
- 新增步骤 **③b 回填**：MW 已退出 ⇒ 满足回填脚本「**无写句柄**」前提 ⇒ **不需要为回填再停一次 MW**。
- 回填脚本退出码 **3**（缺口在 MW 本地库里也没有）**只告警、不阻塞上线**。

**（2）`PyTools/cmd.py` 菜单接入**

| 项 | 值 |
| :--- | :--- |
| 位置 | **14**（原 `14. Deploy BBT Study` 顺延为 **15**） |
| name | `Deploy BBT Study + Restart MW (一键：退MW→部署→重启→自检)` |
| cmd | `bash /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow/deploy_bbt_and_restart.sh` |
| 菜单编号来源 | `enumerate(commands, 1)` 自动生成 |
| 实测 | 加载 `cmd.py` 确认顺序 …13 Smash Levels Weekly / **14 一键脚本** / 15 Deploy BBT Study / …，**总条目 50** |

**（3）本次 `--backfill` APPLY 实跑结论（数据日 2026-09-16）**

两条缺口**都判 `source_empty`**（MW 本地库里也没有 ⇒ 无法本地回填，退出码 **3**）：

| 标的 | 缺口 | 扫描行数 | 结论 |
| :--- | :--- | ---: | :--- |
| ES | 稀薄缺口 **15:45–17:00（15 桶）** | 1,081,744（区间 00:00 → 21:16） | `source_empty`（= 当天已知的 ES 行情源中断）⇒ 只能在 MW 里对 **ESZ26 重新下载**历史 tick |
| NQ | 稀薄缺口 **20:30–20:55（5 桶）** | 484,304 | 该时段 **MW 未订阅 NQ**（图表未加载）⇒ MW 自身库里也没有 ⇒ 同样需重新下载 |

另用脚本直接量化了「**重启造成的真实 TICK 空洞**」（回填工具按 5 分钟桶计缺口，且**稀薄时段 <1 桶的短洞按设计不判缺口**，故它们不在待填清单）：

| 标的 | 最大空洞 | 区间 |
| :--- | :--- | :--- |
| ES | **100 s** | 21:07:25 → 21:09:05 |
| NQ | **530 s** | 20:59:56 → 21:08:46（含被 wedge 冻住的那段） |

**结论**：今晚所有重启造成的 TICK 空洞都**小于桶级判定门槛**（不影响 5 分钟覆盖）；**真正的缺口只有 ES 15:45–17:00 与 NQ 20:30–20:55，且都不可本地恢复**。

---

## 7. 已知遗留与后续动作

| # | 遗留事项 | 影响 | 后续动作 |
| ---: | :--- | :--- | :--- |
| 1 | **ES TICK 稀薄缺口 15:45–17:00（15 桶）** —— 本次 `--backfill` APPLY 实跑判 **`source_empty`**（MW 本地库里也没有；ESZ26 的 15:00 / 16:00 小时文件仅 **41–483 字节**，而 NQ 同时段 **169–380 KB**） | **不可本地回填**（退出码 3，只告警不阻塞上线） | **需在 MW 里对 ESZ26 重新下载历史 tick，之后再跑 `--backfill`**（数据源侧操作） |
| 2 | **NQ TICK 稀薄缺口 20:30–20:55（5 桶）** —— 该时段 **MW 未订阅 NQ**（图表未加载）⇒ MW 自身库里也没有数据，同样判 **`source_empty`** | **不可本地回填** | **需在 MW 里重新下载 NQ 当日 tick 后再跑 `--backfill`** |
| 3 | **DOM 缺失**：ES 20:00:53 起断 + 两阶段上线窗口 **ES DOM 21:07:27 → 21:11:34、NQ DOM 20:59:48 → 21:11:31** | DOM 快照 **MW 不落历史库** ⇒ **不可回填** | 记录为不可恢复损失；依赖租约自愈 + 写者空转报警缩短暴露时间 |
| 4 | **重启造成的 TICK 短洞**：ES 最大 **100 s**（21:07:25 → 21:09:05）、NQ 最大 **530 s**（20:59:56 → 21:08:46，含被 wedge 冻住的那段） | 回填工具按 5 分钟桶计缺口、**稀薄时段 <1 桶的短洞按设计不判缺口** ⇒ 不在待填清单，**不影响 5 分钟覆盖** | **无需处理**（已由 `--backfill` 扫描确认） |
| 5 | **看门狗 0 基线修复**：开流时初始化 `lastDomWriteMs / lastTickWriteMs`、`== 0` 时不判空闲、心跳打印 `never` | —— | **已于 21:16 部署上线并验证**（启动假 SEVERE **2 条 → 0 条**），见 §6.5 |
| 6 | `WRITER_IDLE_MIN`=15min 为初值 | 可能在数据真稀疏的时段误报 | 旁证条件（同标的另一通道 / 另一标的同通道 5 分钟内仍在写）已封堵主要误报；后续按运行数据标定 |

> **历史条目去向**：原第 3 / 4 条（「首次部署新版本后需重启一次 MW」「部署尚未执行」）已于当晚 **21:07 / 21:11 两阶段上线**完成；原「看门狗 0 基线未部署」已于 **21:16 上线并验证** —— 均见 §6。

---

## 8. 结论

1. **根因已定**：热重载换 classloader ⇒ 旧代 study 不被销毁（写 DOM、不写 TICK）+ 新代被「永久 FileLock」永久挡住 ⇒ TICK 通道**不可自愈**。五条证据闭环，1 条旁证（09-10 / 09-11 / 09-15 同样重放痕迹）证明**热重载是常态**而非偶发。
2. **修复已落地并验证 7/7**：从「永久锁＝彻底锁死」改为「(标的, 通道) 租约 + 数据心跳」，两通道解耦，最迟 3 分钟自愈；同时补上热部署守卫与 `WRITER_IDLE` 判据，封堵**部署路径**与**监控路径**两个失效入口。
3. **本轮实测最有价值的一击**：新判据在当晚 MW 重启后**立即抓出** NQ（图表未加载 ⇒ 写者缺席）与 ES（正常）的差异 —— 这正是 20:25 旧口径报「全部健康」时漏掉的同一类故障。
4. **上线与遗留**：当晚三次上线 **21:07 → 21:11 → 21:16** 已完成（首次暴露并修复本次修复自身引入的 DOMListener 注册死锁 ⇒ DOM 写者 = 0；二次四通道写者各 = 1、4 个租约同一实例；三次看门狗 0 基线，启动假 SEVERE **2 条 → 0 条**）。**未完成项收敛为两项**：① **ES 15:45–17:00 与 NQ 20:30–20:55 两段 TICK 缺口**判 `source_empty`（MW 本地库里也没有）⇒ 需**在 MW 里重新下载 tick** 后再跑 `--backfill`；② **DOM 两段缺失**（ES 20:00:53 起、两阶段窗口 ES 21:07:27→21:11:34 / NQ 20:59:48→21:11:31）MW 不落历史库 ⇒ **不可回填**。另：重启造成的 TICK 短洞（ES 100 s / NQ 530 s）均**小于桶级判定门槛**，不影响 5 分钟覆盖，无需处理。详见 §7。
5. **一条方法论**：**首次上线是验收的一部分**——本轮 7/7 验收全绿之后，上线仍在 4 分钟内暴露了一个验收覆盖不到的新缺陷（DOM 通道写者 = 0）；「先退 MW → 部署 → 启动」的组合动作（而非热重载）使该缺陷**在不触发原事故模式的前提下**被安全地观测到、修复并复测。
