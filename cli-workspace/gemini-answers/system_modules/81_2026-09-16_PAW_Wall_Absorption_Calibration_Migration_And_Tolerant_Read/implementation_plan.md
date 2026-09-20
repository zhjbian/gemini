# PAW 墙-吸收-收复 累积统计：从「数据健康」迁至 large_timeframe · 容错读取 (P0) 与调度自愈 (P4) 实施计划 (Plan)

- **日期**：2026-09-16（PT）
- **归属模块**：**M03. DOM 200档深度盘口与特征分析系统**（交叉引用 **M05. 多源实时数据流监控与数据接入引擎** —— 容错读取器族；**M16. BBT 信号监控仪表盘前端交互系统** —— 页面迁移落点）
- **触发场景**：用户核查 `/bbt_signals` →「数据健康」中的 **PAW 墙-吸收-收复 累积统计** 卡片（盘后统计）与新的 `bbt_signals_large_timeframe` 页（Adam 研究 + Order Flow 深度分析 pattern 匹配）**功能定位是否重叠**，问"还有意义吗"。
- **性质**：**页面位置迁移（P2）×1 + 接口语义修正（P1）×1 + 校准产物语义修正（P1）×1 + 根因修复（P0 容错读取）×1 + 调度自愈（P4）×1 + 页面文案纪律（P1）×1**，共六组改动

---

## 1. 背景：用户的原问题与决定

### 1.1 核查结论（先给结论）

| 问题 | 结论 |
| :--- | :--- |
| 与 large_timeframe 的 pattern 匹配功能重叠吗？ | **概念上不可替代** —— 它是「墙 / 吸收」从**描述性维度**升级为**判据**的唯一标定来源，并产出卖家选行权价所需的「安全距离」 |
| 当前形态有意义吗？ | **基本没有意义** —— ① 根本没在累积；② n=1 也显示 `100.0%` + `p=0.0000`，误导决策；③ 无任何决策层消费 |
| 用户决定 | **从「数据健康」删除 → 在 large_timeframe 的「Order Flow 深度分析（pattern 匹配）」下面新建 section 显示它 → 并做其余建议的修改** |

### 1.2 三档定义（理解全文的前提）

三档为**嵌套**关系 `E1 ⊇ E2 ⊇ E3`：

| 档位 | 定义 |
| :--- | :--- |
| **E1** | 墙被测过（`traded >= 500` 手） |
| **E2** | 吸收成立（`|net| >= 300` 且未破或已收复） |
| **E3** | 收复确认（`LEVEL_CONFIRMED`） |

> 当日/累积的「事件总数」= E1 + E2 + E3（各档分别计数）；而校准库中 `tiers.E1.n` 只计 **E1 档**自身，不含 E2/E3 —— 两者不可混用，详见 §3.2 与 walkthrough §4。

---

## 2. 诊断证据（改造前）

### 2.1 PAW 累积库逐日（改造前）

| 数据日 | status | 事件 | 备注（原样） |
| :--- | :--- | ---: | :--- |
| 2026-09-08 | ok | 48 | —— |
| 2026-09-09 | ok | 0 | —— |
| 2026-09-10 | ok | 48 | 含 E2 1、E3 1 |
| 2026-09-11 | ok | **0** | 备注 **DOM 读取失败（error）** |
| 2026-09-12 | data_unavailable | 0 | 无文件 |
| 2026-09-13 | ok | 0 | DOM 15:00 才开始录制 |
| 2026-09-14 | **study_failed** | 0 | `TimeoutExpired` **1800 s** |
| 2026-09-15 | **study_failed** | 0 | `TimeoutExpired`（同上） |
| 2026-09-16 | ok | **0** | 备注 **DOM 读取失败（error）** |

**由表可推**：E1 的 94 例**全部来自 09-08 与 09-10 两天**。

### 2.2 为什么"已积累很多天"是错觉

- 门槛 `gate.usable_days_n: 6` 只数 `status == ok`，**含 0 事件日**（09-09、09-13 都算"可用日"）⇒ 造出"已积累很多天"的错觉。
- 页面上出现的 `E2/E3 2/30 未达门槛 · 继续累积`，**实际语义是「管道断了」而不是「形态罕见」**。
- n=1 时报告仍输出 `100.0%` 与 `p=0.0000`（`p` 是两比例 z 检验在极小样本下的退化值），对决策者是**误导性证据**。

### 2.3 页面侧链路（改造前）

| 环节 | 位置 |
| :--- | :--- |
| 前端页面 | `/bbt_signals`（「数据健康」widget） |
| 卡片渲染 | `bbt_data_web/static/js/bbt_signals.js` 的 `mwPawStatsHtml / mwPawRender / loadPawStats`，注入容器 `#paw-stats-card` |
| 后端接口 | `/data/paw_stats`（`bbt_data_web/data_app/bbt_signals.py`） |
| 数据产物 | `PyTools/jobs/state/paw_calibration.json`、`PyTools/jobs/state/order_flow_paw_stats.json` |

### 2.4 根因：三处错配 + 管道断在两处

#### （1）位置错配（P2）
「盘后统计 · 研究标定」类内容放在**实时数据健康**页面，与页面的时间语义与读者预期都不符。

#### （2）展示误导（P1）
接口把 `hit / hold` 原样透出，不管 `n`；n=1 也显示 `100.0%`。缺少三项决策必需参照：**随机基准**、**p 值**、**样本来源日**。

#### （3）管道断在 gzip 成员与超时（P0，核心根因）

**根因链**：

```
MW 热重载 / 多写者时期
  └─ 导出 gz 呈现三种病态：
       · 多成员拼接（每次 flush / 每个写者各写一个成员）
       · 成员 CRC / 长度损坏（两写者交错写同一文件）
       · 尾成员未闭合（文件仍在被写）
            ↓
  标准库 gzip.open(path, "rt") 逐行读
    └─ 在【任一】成员上抛 zlib.error ⇒ 整份读取终止
         ⇒ 调用方看到「读到一半就空了」
              ⇒ 当日 0 事件（PAW 事件研究）
              ⇒ 整日被标「读取失败」（daily_stats.probe_data）
```

**实测铁证**：09-11 / 09-16 标准库均报
`error: Error -3 while decompressing data: invalid block type`，**读到 0 行**；而同一文件其实有**上千万行可读**（见 walkthrough §3.1）。

**超时侧（P0 第二处）**：单日默认 `1800 s` 不够（09-14 / 09-15 双双 `TimeoutExpired`）。

---

## 3. 设计取舍

### 3.1 为什么保留而不是删除

| 维度 | 判断 |
| :--- | :--- |
| 概念价值 | 「墙 / 吸收」在系统里原本只是**描述性维度**；PAW 标定是把它升级为**判据**的唯一来源 |
| 决策价值 | 产出「**行权价安全距离**」（击穿深度分位数 + 90% 持稳缓冲），是卖家选行权价的直接依据 |
| 现状 | 无累积、无参照、无消费 ⇒ **保留资产、迁移位置、补齐语义、修好管道**，而不是删除 |

### 3.2 为什么必须分批修 P0 → P1 → P2 → P4

| 顺序 | 理由 |
| :--- | :--- |
| **P0 先修** | 管道不通时，任何接口/页面改动都只是"把 0 事件显示得更漂亮"；必须先让**数据真的读得出来**（否则样本永远是 0，改页面无意义） |
| **P1 再修** | 有数据之后，接口必须**先能表达可靠性**（n<30 不给百分比、带基准与 p、带来源日），页面才有东西可呈现 |
| **P2 后迁** | 语义正确后才迁移位置；迁移是纯前端改动，放在 P1 之后可一次性把新语义渲染到新位置（避免"先搬再改"两次触碰同一卡片） |
| **P4 收尾** | 调度自愈解决**长期累积**问题：原逻辑"已入库即跳过"使一天只被评估一次，而当天 DOM 常在**写入中途**（如 14:45 那次只覆盖到 14:45）⇒ 样本永远停在部分覆盖 |
| **P3 不做** | 见 §3.3 |

### 3.3 为什么 P3（接入卖家系统）不做

**全仓 grep 确认**：`paw_calibration.json` **没有任何决策层消费方** —— 卖家系统 `PyTools/option_seller/*` **零引用**，也不存在所谓 "Setup 5" 代码；仅 launchd plist 注释声称它是"Setup 5 行权价安全距离的来源"，属**未实现的设计意图**。

⇒ 「行权价安全距离」目前**仍是研究产物**。接入需要用户先定设计（**用哪个方向 / 哪个时限 / 如何闸门**），本轮**只报告、不接线**，并在页面上明确标注 **"未接入自动下单"**。

---

## 4. 六组改动清单与关键代码点

### 4.1 P2 页面位置迁移

**（1）`bbt_data_web/static/js/bbt_signals.js` —— 删除 PAW 累积统计卡片**

- 删除函数块：`mwPawStatsHtml / mwPawToggle / mwPawRender / loadPawStats / PAW_STALE_FETCH_MIN / _mwBalance` 等，约 **156 行**；
- 删除容器注入 `#paw-stats-card`、初始化调用及相关注释；
- **保留**信号卡里**实时的** `paw_walls` 定价挂单墙模块 —— **两者是不同功能**（实时盘口墙 vs 盘后统计标定），不可一并删除。

**（2）`bbt_data_web/templates/bbt_signals_large_timeframe.html` —— 新增 `#pawStatsCard` section**

在 `#ofDeepCard`（Order Flow 深度分析 pattern 匹配）**之后**新增：

```html
<div id="ofDeepCard" class="card" style="margin-bottom: 20px;">   <!-- 既有：pattern 匹配 -->
<div id="pawStatsCard" class="card" style="margin-bottom: 20px;"> <!-- 新增：PAW 累积统计 -->
```

| 交互点 | 实现 |
| :--- | :--- |
| 收起 / 展开 | `pawStatsToggle()`，状态写入 `localStorage['bbt_pawstats_open']` |
| 深链 | `?paw=1` 直接展开（`/[?&]paw=1/.test(location.search)`） |
| 右上刷新 | `pawStatsLoad(true)` 强制重读 `/data/paw_stats`（绕过 30 分钟缓存 `PAW_STATS_TTL_MS`） |
| 徽标（收起也显示） | `#pawStatsBadge` 在页面初始化 IIFE 内单独拉一次接口 ⇒ **未展开时即显示门槛进度** |
| 标题下注记 | 「盘后统计 · 仅研究标定，不参与自动下单」 |

### 4.2 P1 后端接口 `/data/paw_stats`

`bbt_data_web/data_app/bbt_signals.py` 扩展返回：

| 层级 | 新增字段 | 语义 |
| :--- | :--- | :--- |
| 每档 | `reliable` | `n >= 30` 才给百分比 |
| 每档 | `raw_hit / raw_hold` | 原始命中率（不论 n，永远给出） |
| 每档 | `baseline / baseline_n / p` | 两比例 z 检验，**与产物同口径** |
| 每档 | `sources` | 样本来源日（含当日事件数） |
| 每档 | `need_n` | 门槛（30） |
| 每档 | `sides` | BID / ASK 明细 |
| 顶层 | `baselines`、`days_with_events`、`usable_days`、`events_total`、`baselines_total`、`store_updated_at`、`tiers_note` | 汇总与自述 |

**关键行为**：`n < 30` 时 `hit / hold` 返回 `None` ⇒ 前端显示「**样本不足（n=1）**」而不是 100%。

### 4.3 P1 校准产物

`PyTools/jobs/order_flow_paw_daily_stats.py` 写入的 `paw_calibration.json`：

- 新增 `baselines`（各窗随机基准 `n` / `hit_rate`）；
- 新增 `usable_days_with_events`（**真正产出过事件的天数** —— 修正"可用日"口径）；
- 新增 `gate.days_with_events_n`；
- 每档新增 `provenance`（来源日与当日事件数）与 `reliable`；
- 每 (档, 方向, 窗) 新增 `baseline_hit_rate` 与 `p_value`；
- 抽出 `baseline_hits()`，让**报告与校准共用同一口径**（避免两处各算一套）。

### 4.4 P0 容错读取（新模块）

**新模块 `PyTools/jobs/gz_tolerant.py`** —— 按 **gzip 成员逐个解压**的容错读取器：

| 函数 | 用途 |
| :--- | :--- |
| `iter_gz_lines(path, chunk, stats)` | 逐行产出；成员内出错**只丢该成员**并在字节流里重新定位成员头 `\x1f\x8b\x08`；尾成员未闭合按"读到哪算哪"结束 |
| `head_lines(path, n)` | 探测文件头 n 行（返回 `(行列表, 统计)`），首成员损坏也不抛异常 |
| `scan_gz(path)` | 全量容错扫描 → `rows / first_ms / last_ms / members_ok / members_bad / bytes_skipped / lines` |

```python
GZIP_MAGIC = b"\x1f\x8b\x08"
CHUNK = 1 << 20          # 每次读 1 MB 压缩字节

d = zlib.decompressobj(31)
try:
    out = d.decompress(buf)
except Exception:
    # 该成员损坏：丢弃解压器，跳过 1 字节后重新找成员头（保证有进展，不会死循环）
    d = None
    st["members_bad"] += 1
    st["bytes_skipped"] += 1
    buf = buf[1:]
    continue
if d.eof:
    buf = d.unused_data          # 成员正常收尾：剩余字节属于下一个成员
    st["members_ok"] += 1
```

**改用它**：`order_flow_paw_event_study.py`（`from gz_tolerant import iter_gz_lines`）与 `order_flow_paw_daily_stats.probe_data`（`from gz_tolerant import head_lines`）。

**语义降级**：把「gzip 成员损坏」从**致命**降级为**警告** —— 记入当日 `note`（如「DOM 有 6 个 gzip 成员损坏（已跳过 379 MB 压缩字节，其余照常统计）」），**不再让整日报废**。

**超时**：单日默认 `1800 → 3600 s`。

```python
ap.add_argument("--timeout", type=int, default=3600,
                help="单日研究超时（秒；默认 3600 —— 原 1800 曾导致 09-14/09-15 判 study_failed）")
```

**同类风险扫描（受影响面收敛）**：

| 读取点 | 是否受影响 | 依据 |
| :--- | :--- | :--- |
| `PyTools/order_flow_analysis/order_flow_sentinel.py` | **否** | 实际读的是 **TICKS（非 gz）** |
| `PyTools/order_flow_analysis/dom_sentinel_evaluator.py` | **否** | 同上 |
| `PyTools/jobs/post_rollover_check.py` | **否** | 只读 2 行且包了 `try/except` |
| `order_flow_paw_event_study.py` / `order_flow_paw_daily_stats.probe_data` | **是（已修）** | 唯一两处全量 `gzip.open` 读 DOM 的点 |

### 4.5 P4 调度自愈

新增 `--recompute-recent N`（默认 **3**）：最近 N 天在

- ① 上次状态 **非 ok**，**或**
- ② DOM 文件 `mtime` 比上次分析时**更新**（数据还在长 / 已补齐）

时**自动重算**；否则跳过。

```python
prev = s["days"].get(d)
if prev and not args.force:
    stale = (prev.get("status") != "ok") or (dom_mtime > float(prev.get("dom_mtime") or 0) + 1.0)
    if _idx < args.recompute_recent and stale:
        log(f"  [{d}] 重算（上次 {prev.get('status')} · 事件 {prev.get('events', 0)} · DOM 已更新）", args.quiet)
    else:
        log(f"  [{d}] 已在累积库中且数据未再增长，跳过（--force 可强制重算）", args.quiet)
        continue
```

**日记录新增**：`ran_at`（分析时刻）、`dom_mtime`、`dom_members_bad`。

**动机**：原逻辑「已入库即跳过」使**一天只被评估一次**，而当天 DOM 常在写入中途（14:45 那次只覆盖到 14:45）⇒ 样本永远停在部分覆盖。

**launchd 未改**：`com.bbt.orderflow-paw-stats.plist` 现有命令为 `--days-back 3 --email --quiet`（周一至周五 **14:45 / 21:15**），**默认值即生效**，因此不触碰 plist。

### 4.6 页面文案纪律（P1）

新 section 内**所有百分比都带参照**：

- **随机基准**（同日其它节点、与事件相隔 **≥30 分钟**）；
- **p 值**（`<0.05` 才高亮）；
- **样本来源日**。

并给出两段说明：

| 段落 | 内容 |
| :--- | :--- |
| **怎么用这页** | ① E1 基础率对照 ② 安全距离 ③ 只做研究标定（未接入自动下单） |
| **当前局限** | 样本高度集中、E2/E3 未达 30 例、DOM 历史损坏期无法回算 |

---

## 5. 验证方法

| # | 验证项 | 命令 / 方式 | 判据 |
| ---: | :--- | :--- | :--- |
| 1 | 容错读取器对照 | `python3 /tmp/paw_gz_compare.py`（`gzip.open` vs `scan_gz`，09-11 / 09-16） | 旧口径 **0 行 + `invalid block type`**；新口径可读上千万行 |
| 2 | 单日直跑 | `order_flow_paw_event_study.py`（09-16，544 MB DOM） | 事件 **0 → 50** |
| 3 | 全量重算 | `order_flow_paw_daily_stats.py --days-back 10 --force --timeout 3600` | 10 日跑完；09-14/09-15 由 `study_failed` 转 `ok` |
| 4 | 校准产物 | 读 `paw_calibration.json` | `baselines` / `provenance` / `reliable` / `gate.days_with_events_n` 齐备 |
| 5 | 接口 | `curl -s http://127.0.0.1:5005/data/paw_stats` | 顶层 `baselines/days_with_events/usable_days/events_total/baselines_total/tiers_note` 存在；E2/E3 `hit=None` |
| 6 | 页面迁移 | `curl -s /bbt_signals` / `/bbt_signals_large_timeframe?paw=1` | `/bbt_signals` 已无 `paw-stats-card`；large_timeframe 有 `pawStatsCard` 且在 `ofDeepCard` 之后 |
| 7 | 前端渲染 | 无头 Chrome（独立 `--user-data-dir`、按 PID 结束） | 12 项断言全过 |
| 8 | 徽标（收起态） | 无头 Chrome 打开**不带** `?paw=1` 的页面 | 显示 `E2/E3 n/30 · 有事件日 n/10` |
| 9 | 同类风险面 | 全仓排查 DOM gz 读取点 | 受影响面收敛到 PAW 两处（已修） |
| 10 | P3 事实核查 | 全仓 grep `paw_calibration` / `option_seller` | 决策层零引用 ⇒ 页面标注"未接入自动下单"为事实 |

---

## 6. 回滚方式

| 层 | 回滚点 |
| :--- | :--- |
| **归档页面**（本轮唯一被改的归档文件） | 同目录 `bbt_trading_modules.html.bak-<YYYYmmdd_HHMMSS>`（改前自动备份，**覆盖回该文件即可**） |
| **前端 JS** | `bbt_data_web/static/js/bbt_signals.js`（删除卡片前的版本可由项目 git / 备份恢复） |
| **模板** | `bbt_data_web/templates/bbt_signals_large_timeframe.html`；删掉 `#pawStatsCard` section 与三个 `pawStats*` 函数即回到改造前 |
| **后端接口** | `bbt_data_web/data_app/bbt_signals.py`：`/data/paw_stats` 的扩展字段可整体去除（旧字段仍在，向后兼容） |
| **校准产物** | `paw_calibration.json` 新增字段为**附加**，旧读法（只读 `tiers`）不受影响；可由任一次 `--report-only` 重生成 |
| **容错读取模块** | `PyTools/jobs/gz_tolerant.py` 为**新增文件**；两处调用点改回 `gzip.open` 即回到旧行为（会**重新引入 09-11/09-16 式 0 事件**，仅作应急） |
| **生效条件** | Python/模板改动经 Flask reloader 自动生效；模板/静态资源需**硬刷新**浏览器 |

**回滚后的状态说明**：回退 P0（容错读取）会**重新引入本次根因**（gzip 成员损坏 ⇒ 整日 0 事件且静默）；回退 P2 只是把卡片搬回数据健康页，不影响数据正确性。

---

## 7. 风险与不影响面

| 项 | 说明 |
| :--- | :--- |
| 不改代码以外的东西 | 本轮归档动作**只新建归档目录 + 两个文档 + 备份并更新 `bbt_trading_modules.html`**；不部署、不重启服务、不动数据库 |
| 容错读取的取舍 | 坏成员**整体丢弃**（宁可少读、不可错行）；因此 `members_bad` 较大的日子覆盖会偏短，已记入当日 `note` 供读者判断 |
| `usable_days` 语义 | 新口径拆分「可用日（含 0 事件）」与「**有事件日**」两个指标，避免再出"已积累很多天"的错觉 |
| 小样本展示 | `n < 30` 一律不给百分比（`hit/hold = None`），但保留 `raw_hit` 供研究溯源 |
| P3 未做 | 「安全距离」仍是研究产物；页面已明确标注，避免被误读为已生效的下单闸门 |
| 并发编辑 | `bbt_trading_modules.html` 可能被其它会话并发编辑 ⇒ 本轮**先读现状再改、只做增量**，其余内容一字不动 |
| 历史缺口不可回填 | MW **不存 DOM 历史**，TICK 缺口需在 MW 里重新下载 tick 后才能回填 ⇒ 记录为不可恢复损失 |
