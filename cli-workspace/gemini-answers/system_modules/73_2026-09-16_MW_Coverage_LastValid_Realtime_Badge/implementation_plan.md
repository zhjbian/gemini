# MW 时段覆盖行「最后确认数据有效时间点」实时徽标 实施计划 (Plan)

> 归档目录：`73_2026-09-16_MW_Coverage_LastValid_Realtime_Badge`
> 所属模块：**M05. 多源实时数据流监控与数据接入引擎**
> 日期：2026-09-16（PT）

## 1. 业务背景与用户需求
看板 `http://127.0.0.1:5005/bbt_signals` 的「时段覆盖（ES · 每格 5 分钟）」卡片中，TICK / DOM 两行
只给出**5 分钟桶粒度**的覆盖与缺失标签（如 `07:50 后写入中`），无法回答最常被问到的那个问题：
**"这份文件此刻到底写到几点了？"**

用户要求（原文）：在 TICK、DOM 文字行后添加**实时更新**的"最后确认数据有效时间点"。

现有两条数据路径都太慢，无法支撑"实时"：
| 路径 | 刷新粒度 | 问题 |
|---|---|---|
| 巡检 `PyTools/jobs/mw_data_health_check.py`（launchd） | 30 分钟一轮 | 把 `coverage_json` 写进 `bb_trade.mw_data_file_health` |
| 页面 `GET /data/mw_data_health` | 5 分钟轮询 | 只回放上面的巡检结果，5 分钟桶粒度 |

## 2. 技术难点与方案选择
### 2.1 不能全量解压（否则无法 5 秒轮询）
ES 当日 DOM 文件 390 MB，全量容错扫描 `scan_timestamps()` 需 1.3~1.9 s；若每 5 秒轮询会打满 CPU。
必须**只读尾部有限窗口**。

### 2.2 尾部解析的真实约束（实测确认）
- MW 的导出器用 `new GZIPOutputStream(fos)`（**未启用 syncFlush**）⇒ 流内**没有** `00 00 FF FF`
  同步标记，"从同步边界回解"的思路不成立（先按该思路实现，实测 0 命中后废弃）。
- MW 只在**重启/换日**时新开 gzip 成员 ⇒ 当前成员会随时间线性增长（ES DOM ≈4.7 KB/s，
  跑满 RTH 可达 ~100 MB）⇒ **单纯"尾窗找成员头"在成员变长后必然失效**。

### 2.3 选定的实现：成员头冷启动 + 增量解压
1. **冷启动**：在 1→4→16→64→128 MB 逐级放大的尾窗里找**最后一个 gzip 成员头**，
   从该处建立 `zlib.decompressobj(31)` 并解压（自动跨越多个成员，含空成员）；
2. **热路径**：把解压器与其已消费字节数**缓存在进程内**（`_GZ_STATE`），
   之后每次只把**新增字节**喂进去 ⇒ 成本与文件大小无关（实测 1~30 ms）；
3. **有效性判定**：行首时间戳必须落在 `[数据日 00:00 PT, 现在 + 5 分钟]`，
   用于过滤成员拼接产生的畸形时间戳（2026-09-16 实测文件尾出现 `17895672011789567100000`）；
4. **非活动文件不探测**：mtime 静止 > 10 分钟直接返回 `stale=True`（历史数据日由巡检 coverage 兜底），
   避免把 33 s 的全量扫描带进 5 秒轮询；
5. **失败回退**：所有窗口都没找到成员头（罕见）才退回全量扫描，并带 15 s 缓存，绝不抛异常。

## 3. 实施方案
### 3.1 后端探测函数（`PyTools/jobs/mw_data_health_check.py`）
新增 `probe_last_valid(path, now_ms=None, live_only=True)` 与内部 `_stream_feed() / _stream_bootstrap() / _rows_last_ts()`，
常量 `TAIL_WINDOWS / GZIP_MAGIC / PROBE_IDLE_MS / _GZ_STATE / _PROBE_LOCK`。
返回 `{ok, last_ms, last_hm, age_sec, rows, source, stale, size, mtime_ms, mtime_hm, error}`。

### 3.2 只读接口（`bbt_data_web/data_app/bbt_signals.py`）
新增 `GET /data/mw_file_last_valid?ticker=ES&kind=DOM&date=YYYY-MM-DD`（参数白名单校验，
路径按 `<ticker>_<YYYYMMDD>_<kind>.csv[.gz]` 在 `DEFAULT_DIR` 内解析，不接受任意路径）。

### 3.3 前端徽标与轮询（`bbt_data_web/static/js/bbt_signals.js`）
1. `mwCoverageGroup()` 里在 `TICK` / `DOM` 标签 span **之后**插入 `mwLastValidBadge(r, c)`；
2. 今天（`is_today`）→ 实时徽标（`class="mw-lastvalid"`），5 秒轮询接口 + **每秒**本地重算"多久之前"
   （不再发请求），并按新鲜度着色：≤120s 绿「实时」/ ≤600s 琥珀「滞后」/ 更久红「疑似停更」；
3. 历史数据日 → 静态徽标取巡检 `coverage.last`，明确标注"（巡检）"，不发起探测；
4. 明细收起时 `mwLastValidStop()` 停止轮询，展开/重绘时 `mwLastValidStart()` 重启。

### 3.4 缓存版本
`bbt_data_web/templates/bbt_signals.html` 的 `bbt_signals.js?v=1.2.101 → 1.2.102`（静态资源需强制刷新）。

### 3.5 第二批（用户追加）：NQ 行同样显示实时徽标
原卡片 `MW_COV_TICKERS = ['ES']`，且 `mwCoverageGroup()` 每个 label **只渲染一行**（`list[0]`），
因此 NQ 无论好坏都看不到——而今天出问题的恰恰是 NQ DOM。改法：
1. `MW_COV_TICKERS = ['ES','NQ']`；
2. `mwCoverageGroup(label, rows, bf, reqDate, onlyTicker)` 新增第 5 参数，按标的过滤后渲染；
3. 调用点按 `MW_COV_TICKERS.forEach` 分别产出 TICK / DOM 各两块（共 4 行）；
4. **id 去重**：`mw-gap-box-<label>` → `mw-gap-box-<label>-<ticker>`，`mwGapSignals()` 查表同步加 ticker；
   「一键回填」按钮只在 ES TICK 行渲染一次（其接口本就把 `tickers='ES,NQ'` 一起补），
   避免出现第二个 `id="mw-bf-btn"` 导致按钮/状态互相覆盖；
5. 卡片标题与说明改为「时段覆盖（ES / NQ · 每格 5 分钟）」；
6. 资源版本 `1.2.102 → 1.2.103`。

### 3.6 第二批（用户追加）：UNREADABLE 处置文案纠偏
旧文案把"文件在增长却完全不可解码"的根因写成 **同一 study 被部署了两份（`dev/*.class` 与 `lib/*.jar`）**，
该假设当天已被证伪（`~/MotiveWave Extensions/lib/` 为空）。两处同步改为已确诊根因与正确处置：
1. `bbt_data_web/data_app/bbt_signals.py`：`_MW_ACTIONS` 新增 `UNREADABLE:DOM` / `UNREADABLE:TICK`
   （原先落到通用兜底，只提示"打开目录检查 + 抢救"）；
2. `PyTools/jobs/mw_data_health_check.py`：`UNREADABLE` 的 `error_detail`（看板「详情」列）与
   `coverage_json.summary` 同步改写：去掉 dev/lib 误诊，补 `lsof` 写者数自检、独占写者锁部署、
   "禁止 MW 运行时 deploy/热重载"，并保留抢救命令与"当日文件只会 active(跳过)"的说明。

## 4. 验收标准
1. `GET /data/mw_file_last_valid` 对活动文件返回秒级 `last_hm`，热路径耗时 < 50 ms；
2. 无头 Chrome（CDP）展开明细后，TICK / DOM 两行文字后出现徽标，文本形如
   `最后有效 07:53:35（5 秒前 · 实时）`，且 5 秒后自动推进；
3. 历史数据日徽标显示"（巡检）"且不触发磁盘探测；
4. 非活动文件返回 `stale=True`，不进入全量扫描；
5. 不改变既有覆盖条、缺失标签、一键回填等行为。

## 5. 回滚方案
- `PyTools/jobs/mw_data_health_check.py`：删除 `probe_last_valid` 及配套常量/辅助函数（`PyTools/` 未入 git，
  改动前备份见 Walkthrough §1）；
- `bbt_data_web/data_app/bbt_signals.py`：删除 `/data/mw_file_last_valid` 路由（Flask reloader 自动重载）；
- `bbt_data_web/static/js/bbt_signals.js` + `templates/bbt_signals.html`：移除徽标调用与轮询函数、
  版本号回退 `1.2.102 → 1.2.101`（浏览器需硬刷新）。
