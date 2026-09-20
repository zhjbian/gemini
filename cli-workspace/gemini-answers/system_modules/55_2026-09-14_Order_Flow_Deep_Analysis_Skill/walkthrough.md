# Order Flow 深度分析模块验收报告

- **日期**：2026-09-14
- **模块**：`order-flow-deep-analysis` skill（证据向量 + P1–P5 pattern + 回测/标定）+ 大周期页面展示卡片
- **归档目录**：`55_2026-09-14_Order_Flow_Deep_Analysis_Skill`
- **技术栈**：Python 3.11 / MySQL `bb_trade` / MW 原始 TICKS/DOM / Flask + Jinja2 / agent skill / 浅色主题 / headless Chrome DOM 断言

---

## 1. 结论先行

| 需求 | 结果 |
|---|---|
| 可重复的深度分析 skill | ✅ `order-flow-deep-analysis`（时间点/段 → 五板块报告 + 🧩 pattern 板块，命名规范落盘） |
| DOM 全窗口扫描（修「以偏概全」+「硬编码」） | ✅ `dom_window_profile()` 聚合器；交叉表/解读全部接真实计算 |
| 证据向量 + pattern | ✅ `patterns.py`：`match_patterns`（P1–P5，可机检、阈值可覆盖） |
| 积累 → 标定 | ✅ `of_deep_pattern_cases` 落库 + `backtest.py`（回测/回填）+ `calibrate.py`（网格→回写常量） |
| 页面展示 | ✅ `/bbt_signals_large_timeframe` 新增「Order Flow 深度分析」卡片（可收起，默认收起）；Adam 卡片改可收起（默认收起） |

## 2. 处理逻辑（落地为代码）

### 2.1 TICK / DOM 元数据 → 指标

| 层 | 脚本 | 产出 |
|---|---|---|
| TICK | `adam_tick_analysis.tick_analysis` | 概览 / 分窗口（5/10/15/30/60m 净 Delta·量·位移·比）/ Volume Profile（POC/VAH/VAL）/ ≥20 手大单 / 逐分钟节奏 |
| DOM | `adam_dom_analysis.dom_analysis` | ±2/±5/±15/±25 tick 失衡 / 挂单墙 / 堆叠 / 真空 / T−60…T0 演变 / 引擎同名对照 |
| 引擎行 | `order_flow_signals` | `recent_micro_5m`（Δ5m 系列）· `imb_short/mid`（±2/±5）· `recent_30m_delta`（慢）· `washout_*` / `quality_tier` |

### 2.2 DOM 全窗口聚合（`dom_window_profile`）

修两个缺陷：① 交叉表 DOM 只看 T0 单点 ② section 3 的「imb 偏空」硬编码。现产出：`mean5`（时间加权）/ `bull·bear·neut_frac`（分时占比）/ `first·second_half_mean`（收敛检测）/ `runs`（连续同侧段）/ `agree_frac`（DOM×tick 逐段同向占比）/ `missing`（盲区槽数）。

#### 2.2.1 动机：修两个具体缺陷

1. **「以偏概全」**：§2 交叉表的 DOM 一栏此前只取 **T0 单点快照**（`dp[0]` 的 `imb_2/imb_5`）—— 整个 07:25–08:15 窗口的盘口结论由**最后一行的瞬时挂单**代表；遇插针 / 瞬时撤单会得出与全窗相反的结论。
2. **「硬编码」**：§3「系统 OF 指标解读」里的「imb 偏空」是**写死的文案**，与实际盘口数值无关（无论真实 imb 正负都输出偏空）。

⇒ 新增 `dom_window_profile()`：把窗口内**每一根 5 分钟行**的 DOM 失衡全部纳入，产出「全窗汇总 + 时序结构」；交叉表与解读**全部改接该聚合结果**，报告内不再出现任何硬编码方向词。

#### 2.2.2 数据来源与取值优先级（逐行）

| 优先级 | 来源 | 字段 | 说明 |
|---|---|---|---|
| ① | `order_flow_signals` 扁平列 | `imb_short`（±2）、`imb_mid_short`（±5） | 与引擎同源、数据库化，稳定可得 |
| ② | 该时刻解析后的 DOM 快照 `_at[ts]` | `imb_2`、`imb_5` | 仅当①的 ±2 与 ±5 **同时为空**时兜底（来自 MW DOM 原始文件解析） |
| ③ | 兜底后仍无 ±5 | — | 计入 `missing`（**盲区槽**），**不插值、不参与任何均值/占比** |

扫描对象 = 该次分析**窗口内的全部 5 分钟行**（`rows`，时间升序）；**无前视**（不读 t0 之后的行）。

#### 2.2.3 算法（逐行扫描 → 一次汇总）

```text
vals2, vals5 = [], []
bull = bear = neut = missing = 0
runs, cur_side, cur_start = [], None, None
agree = total = 0

for r in rows:                                    # ← 全窗口扫描（非单点）
    ts = 秒(r.signal_time)
    a, b = r.imb_short, r.imb_mid_short           # ±2 / ±5（DB 扁平列）
    if a is None and b is None:                   # 两者皆空 ⇒ 快照兜底
        a, b = 快照(ts).imb_2, 快照(ts).imb_5
    if b is None:                                 # ±5 仍缺 ⇒ 盲区
        missing += 1; 闭合当前 run; continue
    vals5.append(b);  a is not None and vals2.append(a)
    side = '多' if b > +0.02 else '空' if b < -0.02 else '中'
    bull/bear/neut += 1 (按 side)                 # 时长占比的分子
    runs: side 变化时闭合上一段 (cur_start → 本行时刻, cur_side)
    d5 = tick_net(ts, 5)                          # tick Δ5m（严格逐笔口径）
    if d5 is not None and abs(b) > 0.02:          # 只在「有方向」的行上比较
        total += 1;  agree += 1 if d5*b > 0 else 0
末尾仍未切换的 run ⇒ 用 t0（分析时刻）闭合

mean5 = mean(vals5)      mean2 = mean(vals2)
*_frac = 计数 / n        first/second_half_mean = mean(vals5 的前/后半)
agree_frac = agree / total (total=0 ⇒ None)
```

#### 2.2.4 输出字段（完整清单）

| 字段 | 含义 | 计算口径 | 空值语义 |
|---|---|---|---|
| `n` | 有效行数（±5 可得） | `len(vals5)` | `n=0` ⇒ 窗口内无 DOM 数据 |
| `missing` | DOM **盲区槽数** | ±5 为空的行数（含兜底后仍空） | `>0` ⇒ 该段盘口不可读（如 exporter 空洞） |
| `mean5` | 全窗 **±5 失衡时间加权均值** | `sum(vals5)/n`；每行代表恒定 5 分钟 ⇒ **等权即时间加权** | `n=0` ⇒ `None` |
| `mean2` | 全窗 **±2 失衡均值** | `sum(vals2)/len(vals2)`（分母独立） | 无 ±2 数据 ⇒ `None`（不影响 `mean5`） |
| `bull_frac` / `bear_frac` / `neut_frac` | 偏多 / 偏空 / 中性**时长占比** | 逐行分类（`b>+0.02` / `b<-0.02` / 其他）计数 ÷ `n` | `n=0` ⇒ 全 0.0；正常时三者之和 = 1 |
| `first_half_mean` | 前半段均值（**收敛检测**用） | `sum(vals5[:n//2]) / (n//2)` | `n//2 = 0` ⇒ `None` |
| `second_half_mean` | 后半段均值 | `sum(vals5[n//2:]) / (n-n//2)` | 同上 |
| `runs` | **连续同侧段**列表 | `(起 HH:MM, 止 HH:MM, 侧)`；侧切换即闭合 | 空列表 ⇒ 无有效段（全盲区） |
| `agree_frac` | DOM×tick **逐段同向占比** | 仅在「`\|b\|>0.02` 且 tick Δ5m 可得」的行上，比较 `sign(Δ5m)` 与 `sign(b)` | 无可比行 ⇒ `None`（**不是 0**） |
| `ordered` | 时序明细 `(HH:MM, b)` | 逐行追加 | 供报告 / 调试追溯 |

#### 2.2.5 阈值与设计取舍（每条都有理由）

- **中性带 ±0.02**：|失衡| ≤ 2% 视为噪声 / 中性，避免把微小抖动读成方向（与引擎 `imb_short/mid` 同一读法）；也用于 `agree_frac` 的样本筛选（只在「有方向」的行上比同向性）。
- **等权 = 时间加权**：每行恒定代表 5 分钟 ⇒ 算术平均即时间加权；**刻意不对单行额外加权**，避免插针 / 极端行主导全窗结论。
- **±5 为主、±2 为辅**：全窗主口径用 ±5（更远挂单、噪声更低）；`mean2` 仅作参考且分母独立。
- **半段收敛 = 「吸收共现 vs 真反对」的判别器**：偏空但后半段向 0（或向对侧）收敛 ⇒ **卖压衰减**（对看多即「吸收共现」），不应计为反对证据。阈值取 `±0.05`（看多：`second − first > +0.05`；看空：`< −0.05`）。
- **`runs` 的端点约定**：段的「止」取**下一行的时间戳**（状态切换点），窗口末尾未切换的段用 **t0** 闭合 ⇒ 段覆盖整个窗口、不虚增段数。
- **`agree_frac` 是「条件同向率」**：分母只含可比行（DOM 有方向 **且** tick 可得）⇒ 不能与「全窗占比」混读；分母为 0 时返回 `None`（避免把「无从比较」误读成「完全分歧」）。
- **盲区不插值**：缺失行只计入 `missing`，既不填补也不参与均值 —— 并同时进入 §3 的 `con`（提示该段盘口不可读）。

#### 2.2.6 下游消费（三处，全部接真实计算）

| 位置 | 用法 |
|---|---|
| §2 交叉表「**方向 · 全窗**」行 | DOM 列 = `mean5` + 偏空 / 偏多 占比 +（有则）盲区槽数；TICK 列 = 全窗净 Delta + 买占比 +（有则）DOM×tick 同向占比；**综合判断**：两源同向（`mean5` 与 tick 净额同号且超阈）⇒ **✓✓ 高可信**；否则 ⇒ **⚠️ 两源分歧 · 谨慎**（两者皆缺 ⇒ `—`） |
| §3 系统 OF 指标解读 `_dom_interpret()` | 判定树：`n=0` ⇒ 盘口层完全缺失 ✗ → **收敛** ⇒ 「吸收 / 派发共现，非反对 ✓」 → 否则**对侧**占比 ≥50% ⇒ **真反对 ✗** → **本侧**占比 ≥50% ⇒ **支撑 ✓** → 否则「中性 ⇒ 无方向偏置」；`missing>0` 再追加盲区告警 ✗ |
| Adam 日报 `PyTools/jobs/adam_signal_deepdive.py` | 同一函数的**模块级版本** `dom_window_profile(rows, _at, tw_net, t0_sec)`（逻辑逐行对齐 skill 版）；把「方向」行升级为「方向 · 全窗」，并把单点盘口解读换成窗口级解读 |

#### 2.2.7 实测样例（2026-09-14 · 07:25→08:15 · bias=bearish）

```text
run_analysis.py --date 2026-09-14 --start 07:25 --end 08:15 --bias bearish

窗口 07:25→08:15   n = 11 行   missing = 0
mean5 = -0.035     bear_frac = 64%   bull_frac = 0%   neut_frac = 36%
first/second_half_mean 未收敛（converge = false）

§2 交叉表「方向 · 全窗」：
  DOM  : 全窗 imb ±5 均值 -0.035 · 偏空 64% / 偏多 0%
  TICK : 全窗净 Delta +1962 · 买占比 0.507 · DOM 与 tick 同向占 43%
  判断 : 两源分歧 ⇒ 谨慎 ⚠️
§3 解读：DOM 窗口级：imb ±5 偏空占 64%（时间加权 -0.035）⇒ 挂单侧卖方占优 ✓
证据向量（落 of_deep_pattern_cases）：
  dom = {imb5_mean: -0.03532, bear_frac: 0.6364, bull_frac: 0.0, converge: false}
```

**读法**：盘口（挂单）全窗**持续偏空 64%**，而成交（tick）全窗**净买 +1962**、逐段同向仅 **43%** ⇒ 典型「**挂单压着卖、成交在买**」的**分歧结构**，交叉表按规则标 **⚠️ 谨慎**；同时在 bearish bias 下，§3 单独把盘口列为**本方向支撑项 ✓**。这正是「T0 单点快照」给不出、**必须全窗聚合**才看得到的信息（单点若恰在买方瞬间，会得出与 64% 相反的结论）。

#### 2.2.8 边界与已知局限（据实登记）

- **短窗敏感**：本例 `n=11`，半段各 5–6 行，「收敛」判据（±0.05）相对单行波动偏敏感 ⇒ 窗口越短越应把 `converge` 当**提示**而非结论。
- **均值对极端行不敏感**（刻意设计）：若需要「插针行」视角，应看 `ordered` 或逐行值，而不是 `mean5`。
- **依赖 tick 可得性**：tick 层缺失时 `agree_frac = None`，交叉表的「同向占比」不会显示（不臆造数字）。
- **盲区只计不补**：`missing` 占比高时 `mean5` 代表性下降，§3 会同步给出盲区告警。
- **窗口边界**：仅吃 `rows`（t0 及之前）；若 `--at` 单点模式，窗口 = 前 `--lookback` 分钟 ⇒ 行数约为 `lookback/5`。

### 2.3 证据向量 + pattern

`build evidence`（tick/dom/engine 三层 + 位置分位）→ `match_patterns(ev, th=None)`（P1–P5，阈值可覆盖）。当日 07:25–08:15 → `P1+P5 / medium`。

### 2.4 回测 / 标定 / 跟踪

- `backtest.py --since-days N [--backfill]`：逐 5m 槽构建窗口 → 匹配 → 前向结果 → 按 pattern 聚合；`--backfill` 写回 `of_deep_pattern_cases`。
- `calibrate.py --apply`：网格 `P1_POS_MAX ∈ {0.20…0.60}` → 选定 0.20（命中30m 48%/94 样本，优于 0.40 的 41%/159）→ 写回 `patterns.py`。

## 3. 实测证据

### 3.1 首轮回测（12 日 · 命中=方向 |Δ|≥3 点）

| pattern | 样本 | 命中30m | 命中60m | 平均30m | 平均MFE |
|---|---|---|---|---|---|
| **P4 挂单-成交共振** | 25 | 68% | 76% | +1.82 | +4.60 |
| **P1 低点吸收（标定后 0.20）** | 94 | 48% | 52% | +3.06 | +7.60 |
| P5 短长窗背离 | 103 | 45% | 50% | +2.41 | +4.98 |

### 3.2 case 前向回填

手动落库 `ES_2026-09-14_0815`（P1+P5/medium）→ 前向 `+10.25 / +35.75 / +29.5` 点，`fwd_hit_30m=1`（30 分钟命中 ✓）。

### 3.3 页面

- 端点 `/data/order_flow_deep_analysis` → `{data:[case…], reports:[…]}`（time 修正为 HH:MM ✓）。
- headless DOM 断言：OF 卡片 case 行 `2026-09-14 · 08:15 · 多 · P1+P5 · medium · +10.25✓/+35.75✓/+29.5✓ · 打开(报告链接)`；Adam 卡片展开后正常渲染；两卡片 body 默认 `display:none`（默认收起 ✓）。

## 4. 页面改动

| 位置 | 改动 |
|---|---|
| `bbt_signals.py` | 新增 `GET /data/order_flow_deep_analysis`（只读，读 `of_deep_pattern_cases` + 报告目录清单） |
| `bbt_signals_large_timeframe.html` | Adam 卡片：header 加 toggle + body 包进 `#adamResearchBodyContainer`（默认收起，首次展开才拉数据）；新增「Order Flow 深度分析」卡片（可收起，默认收起，懒加载，列出 case + 前向结果 + 报告链接） |

## 5. 回滚

- skill 回滚：删 `~/.agents/skills/order-flow-deep-analysis/` 下 `scripts/patterns.py` / `backtest.py` / `calibrate.py`（`run_analysis.py` 回退到无 pattern 版本）。
- 页面回滚：还原 `bbt_signals_large_timeframe.html`（Adam 卡片去掉 toggle 包裹 + 删除 OF 卡片）；还原 `bbt_signals.py` 删除新路由。

## 6. 遗留与后续

1. **≥20 手大单**（暂缓，用户有其他想法）：落地后激活 P1/P3 大额否决，重跑标定。
2. **阈值随日数收敛**：`P1_POS_MAX=0.20` 是 12 日首轮，样本仍小（94，48% 的 95%CI 约 ±10 点）；每日运行 `calibrate.py` 累积收敛。
3. **全量语料**：回测目前只回填已存在的 case；如需把全部历史槽自动灌入 `of_deep_pattern_cases` 作语料，加 `--insert-all` 模式。
4. **P2/P3**：P2 需 washout 事件（样本少）、P3 缺大额数据，暂无法标定。

---

## 7. 后续升级（同日 · Adam 卡片 order flow 对齐 + OF 卡片表格化）

> 2026-09-14 晚（承接本节 module）：把新方法**接入 Adam 日报**，并把 OF 卡片从「一行一 case + 外链报告」升级为**表格 + 行内展开报告 + 拷贝/删除**。

### 7.1 Adam 日报的 order flow 分析对齐新方法（`PyTools/jobs/adam_signal_deepdive.py`）

| 能力 | 落地 |
|---|---|
| DOM 全窗口聚合 | 新增模块级 `dom_window_profile()`（对齐 skill 同名函数）：`mean5/mean2`、偏空/偏多/中性**时长占比**、前后半段**收敛检测**、DOM×tick **同向占比**、盲区槽数 |
| 证据向量 + P1–P5 | 每帖构建证据向量 → 复用 `patterns.match_patterns()` → 新增「🧩 命中的 pattern」板块 |
| 机构大单层 | 合并结论表新增「机构大单」行（`SingleTickBigTrade` 净额 ✓） |
| 单点 → 全窗 | 「方向」行升级为「方向 · 全窗」；系统指标解读里的**单点盘口失衡**换成窗口级解读（识别「吸收共现」与「真反对」） |

- 实测（09-14 两帖 bearish）：`build_day('2026-09-14', persist=False)` 成功，命中 `P3 高位派发(medium) + P5`。
- 说明：历史日报的逐帖缓存（`adam_deep_payload`）仍是旧方法产物；**新生成的日报**才含新方法。

### 7.2 OF 卡片表格化（`bbt_data_web/templates/bbt_signals_large_timeframe.html`）

| 项 | 结果 |
|---|---|
| 表格列 | 报告(⊕+标的) · 数据日 · 窗口 · 方向 · 命中 pattern · 置信 · 前向 15m/30m/60m · 分析摘要 · **操作** |
| 操作列 | **拷贝**（`fa-copy`，复制摘要 + 报告路径）· **删除**（`fa-trash-alt`，删 DB case） |
| 行内展开 | 点击 ⊕ → 展开 `iframe` 直读报告 HTML（**首次展开才赋 `src`** ⇒ 不展开不加载 ✓）；**自适应全高**：`onload` 量同源 `contentDocument` 高度 → 设 `iframe` 高度 + 内容 `overflow:hidden` ⇒ **无内部滚动条** ✓（`resize` 时重算 ✓） |
| 每页条数（Adam 卡片） | 25 → **15** |

### 7.3 新增/增强端点（`bbt_data_web/data_app/bbt_signals.py`）

| 端点 | 作用 |
|---|---|
| `GET /data/order_flow_deep_analysis`（增强） | 补 `window_start/window_end`（HH:MM ✓，用 `total_seconds()`）+ 每 case 映射**最新** `report_file` |
| `GET /data/order_flow_deep_report?file=` | 回传单个报告 HTML（**正则白名单 + resolve 父目录校验** ⇒ 防目录穿越 ✓） |
| `POST /data/order_flow_deep_delete` | 按 `case_id` 删 `of_deep_pattern_cases` 行（**仅删 DB 记录，报告文件保留** ✓） |

### 7.4 回填（09-14 07:25 → 08:25）

- `run_analysis.py --date 2026-09-14 --start 07:25 --end 08:25 --log-case` → `order_flow_analysis_ES_2026-09-14_0825_low_absorption_2026-09-14_2220.html`，bias=bullish，`P1 / medium`。
- `backtest.py --date 2026-09-14 --backfill` → 前向结果 `+17.25 / +23.75 / +29.5`（15/30/60m 全命中 ✓）。

### 7.5 验收（headless DOM 断言）

- 表头 9 列 ✓；两 case（0825 / 0815）✓；窗口列 `07:25 → 08:25` ✓；`fa-copy` / `fa-trash-alt` 存在 ✓。
- 首行：`ES 2026-09-14 07:25 → 08:25 BULLISH P1 MED +17.25✓ / +23.75✓ / +29.5✓ ES_2026-09-14_0825`。
- 展开：`ofDeepDetail-<cid>` 显示 + `iframe.src` 已设为 `/data/order_flow_deep_report?file=…` ✓。
- 端点：报告 `HTTP 200 · text/html`；`../../../etc/passwd` 与 `foo.html` → `HTTP 400` ✓。

### 7.6 回滚（本节）

- `adam_signal_deepdive.py`：`/tmp/adam_signal_deepdive_pre_ofdeep_upgrade.py.bak`。
- 页面：OF 表头还原 7 列 + `per` 改回 25；删 3 个新 JS 函数（`ofDeepToggleRow` / `ofDeepCopyCase` / `ofDeepDeleteCase`）。
- 后端：删 `/data/order_flow_deep_report` + `/data/order_flow_deep_delete`；`order_flow_deep_analysis` 去掉 `report_file` 与 window 字段。
