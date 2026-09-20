# MW 时段覆盖行「最后确认数据有效时间点」实时徽标 验收报告 (Walkthrough)

> 归档目录：`73_2026-09-16_MW_Coverage_LastValid_Realtime_Badge`
> 所属模块：**M05. 多源实时数据流监控与数据接入引擎**
> 验收时间：2026-09-16 07:47–07:56（PT）

## 1. 改动清单

| 文件 | 类型 | 改动要点 |
|---|---|---|
| `PyTools/jobs/mw_data_health_check.py` | 新增能力 | 新增 `probe_last_valid()` + `_stream_feed()` / `_stream_bootstrap()` / `_rows_last_ts()` 与常量 `TAIL_WINDOWS`(1→128MB) / `GZIP_MAGIC` / `PROBE_IDLE_MS`(10min) / `_GZ_STATE` / `_PROBE_LOCK`；`import threading`、`import zlib` |
| `bbt_data_web/data_app/bbt_signals.py` | 新增接口 | `GET /data/mw_file_last_valid?ticker=&kind=&date=`（参数白名单校验 + 目录内文件名解析，不接受任意路径） |
| `bbt_data_web/static/js/bbt_signals.js` | UI | `mwCoverageGroup()` 在 TICK/DOM 标签后插入 `mwLastValidBadge()`；新增 `mwLastValidPaint/Poll/Start/Stop` + `mwHmsFromMs`；明细展开启动 5s 轮询＋1s 本地重算年龄、收起停止；两处 `renderMwHealthDetail()` 调用点同步重启轮询 |
| `bbt_data_web/templates/bbt_signals.html` | 缓存 | `bbt_signals.js?v=1.2.101 → 1.2.102`（静态资源需硬刷新） |

**回滚点**：三处代码落在**未纳入 git** 的文件里，改动前未留时间戳备份，因此改为提供**经验证的回滚脚本**
`73_.../rollback.py`（`--apply` 时先备份 `<file>.bak-<ts>`）：
- dry-run 已确认锚点命中：切除 `mw_data_health_check.py` 7,509 字符、`bbt_signals.py` 1,976 字符、`bbt_signals.js` 4,571 字符 + 4 行零散行 + 第二批 9 处（NQ 行 wiring）+ 模板版本号；
- **在临时副本上实跑**（含第二批）：回滚后 `mwLastValid / probe_last_valid / mw_file_last_valid / onlyTicker / 1.2.10x`
  残留均为 **0 个文件**，`MW_COV_TICKERS` 回到 `['ES']`、gap-box id 回到无 ticker 后缀，Python/JS 语法校验通过；
- **幂等**：二次运行全部报"未找到起始锚点（跳过）"。
- **不需要回滚的部分**：第二批的**处置文案**（`_MW_ACTIONS` 两个新条目 + 巡检 `error_detail`）只影响文字提示、
  不含行为逻辑；`rollback.py` 不动它们（旧文案已证伪，没有回退价值）。

## 2. 验收结果

### 2.1 后端探测性能（实测，ES/NQ 当日文件 390MB / 284MB）
| 文件 | 结果 | 来源路径 | 耗时 |
|---|---|---|---|
| `ES_20260916_DOM.csv.gz` | 首行命中 | `gz-tail(cold)` 首次 350 ms | 之后 `gz-incr` **0.7~30 ms** |
| `ES_20260916_TICKS.csv` | 尾行命中 | `csv-tail` | 29~39 ms |
| `NQ_20260916_DOM.csv.gz` | 首行命中 | `gz-tail(cold)` 249 ms | 之后增量 |
| `ES_20260915_DOM.csv.gz`（历史日） | `ok=false, stale=true` | 不探测（mtime 静止 >10 分钟） | **0 ms** |

接口实测（Flask 进程内，含 HTTP 开销）：`gz-incr` 请求 88~346 ms；`last_hm` 与文件最后修改时间同秒。

### 2.2 参数与边界
```
ticker=ES&kind=FOO   -> 400 {"error": "kind 只能是 DOM / TICKS"}
ticker=ES&date=2026-13 -> 400 {"error": "date 需为 YYYY-MM-DD 或 YYYYMMDD"}
ticker=XX&kind=DOM&date=2026-09-16 -> 200 {"ok": false, "error": "文件不存在", "file": "XX_20260916_DOM"}
ticker=NQ&kind=DOM&date=2026-09-16 -> 200 ok（last_hm 与 mtime 同秒）
```

### 2.3 前端（无头 Chrome + CDP 实测，非人工目测）
展开「时段覆盖」后 DOM 读取到的徽标（`class="mw-lastvalid"`）：

```
id=mw-lv-ES-TICKS  "最后有效 07:53:35（5 秒前 · 实时）"
    title: ES_20260916_TICKS.csv · 来源 csv-tail · 尾部有效行 123354 · 文件最后修改 07:53:35
id=mw-lv-ES-DOM    "最后有效 07:53:28（11 秒前 · 实时）"
    title: ES_20260916_DOM.csv.gz · 来源 gz-incr · 尾部有效行 1097765 · 文件最后修改 07:53:30
```

视觉截图（浅色主题、徽标紧跟在 `TICK` / `DOM` 文字之后）：
`73_.../lastvalid_badge_screenshot.png`（已随本报告归档）

| 行 | 渲染结果 |
|---|---|
| TICK | `TICK [最后有效 07:53:35（5 秒前 · 实时）] ES 覆盖 100%（93/93） 活跃时段无缺失` |
| DOM | `DOM [最后有效 07:53:28（11 秒前 · 实时）] ES 覆盖 11.8%（11/93） RTH 缺失 06:30–06:45（15min）▾ THIN 缺失 00:00–06:35（395min）▾ 07:50 后写入中` |

- 绿色「实时」= 距最后有效数据 ≤120 s；120~600 s 转琥珀「滞后」；>600 s 转红「疑似停更」；
- 历史数据日渲染为灰色虚线徽标 `最后有效 HH:MM（巡检）`，**不发起磁盘探测**；
- 收起明细即停止轮询（`mwLastValidStop()`），展开/重绘自动重启。

### 2.4 关键技术事实（实测得出，写入代码注释）
1. **MW 未启用 gzip syncFlush**：`new GZIPOutputStream(fos)` 的 `flush()` 只做 NO_FLUSH，
   流内没有 `00 00 FF FF` 同步标记 ⇒ "从同步边界回解"不可行（先按此法实现，实测 0 命中后废弃）；
2. **当前 gzip 成员会持续增长**（ES DOM ≈4.7 KB/s，跑满 RTH 可达 ~100 MB）⇒ 每 5 秒重找成员头
   必然退化为"重解压几十 MB"，因此必须做**增量解压状态缓存**（本实现的核心）；
3. 文件尾存在成员拼接产生的**畸形时间戳**（实测 `17895672011789567100000`）⇒ 用 `[数据日 00:00, now+5min]`
   区间过滤，避免把垃圾值当成"最后有效时间"。

## 3. 已知限制
1. 若 Flask 进程重启（改 `.py` 触发 reloader）且当时**当前成员已大于 128 MB**，冷启动会退回全量扫描
   （带 15 s 缓存，单次约 30 s）；表现是首次请求慢、徽标短暂显示"探测中"，不影响既有功能。
2. 健康明细面板本身仍只在**展开时**渲染（5 分钟轮询不重绘明细，属既有行为）；但本徽标由**独立 5 秒轮询**
   持续刷新，不依赖面板重绘。
3. ~~`MW_COV_TICKERS` 决定该卡片只展示 ES~~ → **第二批已扩展为 ES / NQ 四行**（见 §5）。

## 5. 第二批交付（10:03–10:05 验收，NQ 行 + 处置文案纠偏）

### 5.1 改动
| 文件 | 改动 |
|---|---|
| `bbt_data_web/static/js/bbt_signals.js` | `MW_COV_TICKERS=['ES','NQ']`；`mwCoverageGroup()` 新增 `onlyTicker` 过滤；调用点改为按标的分块渲染（4 行）；`mw-gap-box-<label>-<ticker>` 去重 id；回填按钮只在 ES TICK 行渲染；卡片标题/说明改为「ES / NQ」；版本 `1.2.103` |
| `bbt_data_web/templates/bbt_signals.html` | `?v=1.2.103` |
| `bbt_data_web/data_app/bbt_signals.py` | `_MW_ACTIONS` 新增 `UNREADABLE:DOM`(483 字) / `UNREADABLE:TICK`(268 字)，替换原通用兜底；删除 dev/lib 重复部署误诊 |
| `PyTools/jobs/mw_data_health_check.py` | `UNREADABLE` 的 `error_detail` 与 `coverage_json.summary` 同步纠正为"多代 classloader 各自成 master ⇒ gzip 流交错"并给出 lsof/独占锁/禁热重载处置 |

### 5.2 验收（无头 Chrome + CDP 实测）
```
徽标数量 = 4（此前 2）
mw-lv-ES-TICKS  "最后有效 10:04:14（3 秒前 · 实时）"   ES_20260916_TICKS.csv · csv-tail
mw-lv-NQ-TICKS  "最后有效 10:04:14（3 秒前 · 实时）"   NQ_20260916_TICKS.csv · csv-tail
mw-lv-ES-DOM    "最后有效 10:04:12（6 秒前 · 实时）"   ES_20260916_DOM.csv.gz · gz-incr
mw-lv-NQ-DOM    "最后有效 10:04:14（4 秒前 · 实时）"   NQ_20260916_DOM.csv.gz · gz-incr
卡片标题 = 时段覆盖（ES / NQ · 每格 5 分钟）
重复 id 检查 = 无重复 id          （改前会有两个 mw-bf-btn / mw-gap-box-TICK）
```
截图：`lastvalid_badge_screenshot_es_nq.png`（4 行 4 徽标，浅色主题）。

| 行 | 渲染结果 |
|---|---|
| TICK ES | `最后有效 10:04:14（3 秒前 · 实时）` · 覆盖 100%（115/115）· 活跃时段无缺失 |
| TICK NQ | `最后有效 10:04:14（3 秒前 · 实时）` · 覆盖 100%（115/115）· 活跃时段无缺失 |
| DOM ES | `最后有效 10:04:12（6 秒前 · 实时）` · 覆盖 28.7%（33/115）· RTH 缺失 06:30–06:45（15min）· THIN 缺失 00:00–06:35（395min）· 09:37 后写入中 |
| DOM NQ | `最后有效 10:04:14（4 秒前 · 实时）` · 覆盖 26.1%（30/115）· RTH 缺失 06:30–07:00（30min）· THIN 缺失 00:00–06:35（395min）· 09:37 后写入中 |

处置文案以 AST 静态校验（`_MW_ACTIONS` literal_eval）：两键均存在、占位符 `{d}` 正常渲染、
旧根因字样仅保留在解释性注释里（无残留误导文案）。

### 5.3 已知小瑕疵（不影响正确性）
首次探测（Flask 进程刚 reload、解压状态为冷）时，某个徽标可能短暂停在"探测中"文字上，
待首个响应返回即转为实时值——实测 NQ DOM 在冷启动首轮出现过一次，第二次轮询即正常。

## 6. 验证脚本（可复跑）
- `/tmp/verify_mw_lastvalid.py`：CDP 驱动无头 Chrome → 等首轮巡检数据 → 展开明细 → 读徽标文本 + 截图
  （独立 `--user-data-dir`，只按自身 PID 结束，收尾删除 profile，符合「不得影响用户会话」规则）。
