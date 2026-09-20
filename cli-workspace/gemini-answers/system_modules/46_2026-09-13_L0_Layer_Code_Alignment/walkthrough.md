# Walkthrough · L0 层代码对齐 + 手册-代码一致性审计（2026-09-13）

## 1. 目标

用户要求以手册为基准做三方核对：
1. **§3.1.1.1 第0层统一门槛** —— 代码与文档不一致则**改代码**；
2. **§3.1.2 5分钟综合信号** —— 只列差异，等待确认；
3. **§3.1.3.1 / .2 / .3（QuantPivot 开仓规则 / 开仓策略 / 止盈策略）** —— 只列差异，等待确认。

## 2. §3.1.1.1 核对结果（已改代码）

| # | 文档 | 代码（改前） | 判定 | 处理 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | L0-D 机制级闸门 / L0-E 全局上限 | 代码里叫 **L0-C** / **L0-D**（docstring、常量注释、`check_layer0` 注释与 reason、cycle 注释日志） | 不一致（编号错位） | **改代码**：全部顺延为 L0-D / L0-E |
| 2 | **L0-C = EMA 阻力/支撑带禁区反向开仓一票否决（只掩码方向，不终止）** | **未在 L0 实现**；同名判据内联在引擎 `option_seller_engine.py` 原 **Hard Veto 7**，且以 **REJECTED 终止**；几何口径不同（仅 15m EMA、绝对点位 ±2.5/±1.0、无跳空/日内极值前置） | 不一致（层错 + 语义错） | **改代码**：新增 `ema_forbidden_zone_mask()` 于 `check_layer0`（掩码语义、手册口径、fail-open）；**移除**引擎 Hard Veto 7 |
| 3 | L0-A③ 必需数据齐备 → **立即结束本周期** | `if ctx.price_position_pct is None and ctx.required_ok is False` —— `required_ok` **从未被装配**、且用 `and` ⇒ **死条件，从未生效** | 不一致（门槛失效） | **改代码**：改为 `if ctx.required_ok is False` 即终止；并在 manager 装配 `required_ok = (quality_tier != 'INSUFFICIENT')` |
| 4 | L0-B 位置掩码阈值：开盘前 30 分 70/30 · Neutral 60/40 · Trend Day 70/30 | L0 层正确（`POS_MASK_*`）；但**引擎内联重复实现**用 **50/50 · 65/35**（漂移） | 不一致（重复实现 + 阈值漂移） | **改代码**：引擎 Hard Veto 5 改为**委托** `auto_mechanisms.position_mask()`，单一权威 |
| 5 | 时段 06:35 ≤ now < 11:30 PST | L0 用 `>=`（11:30 截断）；引擎内联用 `>`（11:30 允许） | 口径漂移 | **改代码**：引擎 `>` → `>=` 对齐 |

**未改动（记录在案）**：引擎 `evaluate_entry_opportunity`（全库**无调用方 = 死代码**）内含同样 50/50·65/35 位置掩码；本轮不动。

## 3. 代码改动清单

| 文件 | 改动 |
| :--- | :--- |
| `PyTools/option_seller/auto_mechanisms.py` | ① docstring/常量/注释/日志 L0-C↔L0-D↔L0-E 顺延；② 新增常量 `EMA_BAND_TOL_PCT=0.10`、`DAY_EXTREME_VETO_PCT=0.40`；③ 新增 `ema_forbidden_zone_mask()`；④ `check_layer0` 接入 L0-C 并写 `detail['ema_forbidden_zone']`；⑤ L0-A③ 死条件修复 |
| `PyTools/option_seller/option_seller_engine.py` | ① Hard Veto 5 → 委托 `position_mask()`（删 50/50·65/35）；② Hard Veto 1 `>`→`>=`；③ Hard Veto 7（EMA 否决）整块移除并留迁移说明 |
| `PyTools/option_seller/option_seller_manager.py` | `_build_mechanism_context`：装配 `required_ok`（L0-A③）+ 注入 L0-C 输入（`price` / `gap_pct` / `day_low_pct` / `day_high_pct`） |

## 4. L0-C 判定口径（实现）

- **禁做多（掩码 BULLISH）**：跳空低开（`gap_pct < 0`）**或**日内最低跌幅 `<= -0.40%`，**且**现价距 15m / 1h EMA13/21 带**下沿** `<= 0.10%`。
- **禁做空（掩码 BEARISH）**：完全对称（`gap_pct > 0` 或日内最高涨幅 `>= +0.40%`，且距**上沿** `<= 0.10%`）。
- **fail-open**：任一必需输入缺失 ⇒ **不否决**，并在 `detail` 记录缺项。
- **未实现的手册分支**：手册另含「尚未在带外实体站稳 2 根 5m K 线」，需 bar 序列，当前上下文无 ⇒ 只取「贴近/进入带内」这一确定性分支，不使用更宽的「位于带内即否决」以免过度拦截。

## 5. 行为影响（重要）

| 改动 | 方向 | 说明 |
| :--- | :--- | :--- |
| L0-A③ 收紧为真闸门 | **更严** | 实测 `quality_tier` 分布（有指标的行）：OK 95 / **INSUFFICIENT 49** / DEGRADED 12 ⇒ 约 **8%** 的周期将**整周期终止**（此前仅机制 ① 受影响，其他机制仍可开仓）。无 `quality_tier` 键（老数据/无 OF 快照）视为齐备，不误伤。 |
| 引擎位置掩码改权威阈值 | **放宽** | 机制 ① 在 Pos 50–60%（Neutral）与 35–40%（Trend 空头）区间不再被引擎整体拒绝（原 50/50·65/35 → 现 60/40·70/30）。方向掩码仍由 L0-B 与 `_mech_*` 保证。 |
| 引擎 EMA 否决移除 → L0-C | **等价（实盘）** | 引擎原 Hard Veto 7 在实盘 5m 路径本就**失效**（`ema_data` 仅含 `regime`，无 EMA 点位 ⇒ `e13=0` 使判定短路）。移除后总量不变。 |
| L0-C 是否实盘生效 | **暂未激活** | 实时 5m 装配只提供 `regime`，未提供 EMA 点位与日内极值 ⇒ L0-C **fail-open 未激活**；补齐取数后自动生效（**待办**）。 |

**回滚点**：`/tmp/l0c_bak/{auto_mechanisms,option_seller_engine,option_seller_manager}.py`（改动前原样）。

## 6. 校验

- `py_compile` 三文件 **OK**；`symtable` 未定义名扫描 **OK（0）**
- 三模块导入 **OK**；`MECHANISMS` 七机制顺序不变
- **L0 冒烟 6 例全通过**：低开贴近下沿→掩码 BULLISH；高开贴近上沿→掩码 BEARISH；无 EMA 点位→不否决（fail-open）；`required_ok=False`→terminal；`required_ok=True`→放行且 `detail` 含 `ema_forbidden_zone`/`pos_mask`/`global_groups`；综合掩码 `{BEARISH,BULLISH}`
- `test_l1_h1_breakeven_stop.py` **通过**；`test_quant_pivot_option_seller.py` **2 例失败 —— 经 A/B 对照（切回改动前备份重跑）结果完全相同 ⇒ 属既存失败，非本次引入**
- 服务冒烟：`/bbt_option_seller`、`/api/option_seller/status` 均 **200**
- 手册 HTML：errors=**0**、残留 **0**、断链 **0**（L0-C「实现现状」段已同步更新为「已上收」）

## 7. 待确认项（§3.1.2 与 §3.1.3.1–.3）

两项审计**只读完成、未改任何代码**，差异清单已提交用户等待确认（详见对话记录）：
- **§3.1.2**：8 项差异（含维度 3「≥12 分」、维度 4「≥6 分」、QP 极值→激进型 三项未实现；引擎内联 L0 与阈值漂移）。
- **§3.1.3.1–.3**：15 项差异（含 L1/H1 `is_l1_h1_pivot_trade` 标签丢失致模式 B 不自动生效、条件单路径三维准入可绕过、微观共振门恒真失效、L2/H2→Aggressive 未实现 四项高严重度）。

---

# 第二轮：L0-C 取数补齐 + §3.1.2 三维共振重构（2026-09-13 续）

## 8. (1) L0-C 取数补齐 → 已可实盘生效

**新增独立模块** `PyTools/order_flow_analysis/ema_engine.py`（通用 EMA / 均线带引擎）：

| API | 作用 |
| :--- | :--- |
| `ticks_path / load_ticks(date)` | 定位并读取 ES 逐笔 CSV（新/旧命名兼容），带 `America/Los_Angeles` 时区 |
| `resample_closes(ticks, minutes)` / `ema(series, span)` | 任意周期重采样 + EMA（`adjust=False`，与原实现逐值一致） |
| `band_view(price, ema_fast, ema_slow, tol_pct)` | 均线带视图：上下沿、距沿百分比、是否「贴近/进入带内」 |
| `bars_outside_band(...)` | **带外连续站稳根数**（对应手册 L0-C「站稳 2 根 5m K 线」分支） |
| `compute_ema_snapshot(date, time, timeframes)` | 统一快照：15m/1h EMA13/21、bands、regime、tangled、dist_pct、bars_outside |
| `rescale(snapshot, target_price)` | **ES → 调用方价格尺度归一**（SPY 哨兵必需，否则永不命中） |
| `forbidden_zone_mask(...)` | L0-C 的纯函数版（离线回放 / 单测 / 其他调用方复用） |

**单一权威收敛**：`order_flow_rules_optimizer.calculate_15m_emas_and_price()` 由内联实现（1,928 字符）改为**委托** `ema_engine`（902 字符），逐值一致性已实测（08:30 / 10:00 / 11:29 三时点 legacy == engine）。

**实时接线** `order_flow_sentinel.py`（5 分钟周期）：
1. 计算 `compute_ema_snapshot(date_str, target_time)` → `rescale(..., spy_price)` → 并入 `ema_dict`（15m/1h EMA 点位）；
2. 计算 `day_high_pct` / `day_low_pct`（相对 **RTH 开盘代理** = 当日首个 5m bin 的 `price_start`）写入 `pivot_dict`；
3. 两处均 `try/except` 静默降级 —— 失败不影响主流程（L0-C fail-open）。

**端到端实测（2026-09-11 真实数据）**：15m 带 766.56~766.98、现价 767.33（SPY 尺度，factor=0.1000）⇒ L0-C **成功命中**：跳空低开 → 掩码 BULLISH；跳空高开 → 掩码 BEARISH；宽幅双向日 → 双向掩码。

## 9. (2) §3.1.2 删除维度 3 → 三维共振（文档 + 代码）

**代码**（`option_seller_engine.py`）：
- 删除原 **Dimension 3（拍卖关键位与 QuantPivot 反转边界，20 分）** 整块（`pivot_data` 打分 + `QuantPivotCalculator` 打分），并移除 `debug_info['d3_pivot_score']`；
- **维度 1 权重 40 → 60**：`OF_SCORE_MAP = {10:60, 9:56, 8:51, 7:47, 6:42, 5:38, 4:33, 3:30, 2:23, 1:23}`（原值 ×1.5 取整），兜底默认 20 → 30（4 处）；
- **维度 4 → 维度 3**（EMA 乖离回归，10 分不变）：`d4_ema_score` → `d3_ema_score`（仅测试文件曾读，无生产消费方）；
- 总分 `tot = of + gamma + ema`（去掉 pivot）；`rationale` 文案改为 `OF/60 + Gamma/30 + EMA/10`。

**文档**：表格三行 = 维度1 **60** / 维度2 30 / 维度3(原维度4) 10；全文「四维 → 三维」「4-Factor → 3-Factor」共 14 处（含 §3.1.1.4 机制概览、§3.1.7、§3.2 章首、§3.1.2 引言与 §3.1.2.1）。

**连带修正**（用户未列但为必然结果）：
- §3.1.2.1 删除「**或命中 QuantPivot L2/H2 极值** → 激进型」子句（该子句既未实现，其依据的维度 3 亦已删除）；
- §3.1.3 章首「用途 1：主决策漏斗『维度 3』的定量打分内核（满分 20 分）」改写为「机制 ② 边界反向的自身判定内核」，并明确 QuantPivot **不再参与共振打分**；
- §3.1.3.1 开仓规则表：**「评分与 Strike 锚定」列 → 「Strike 锚定」列**（+10/+6/+5/封顶 20 的评分随维度 3 一并取消），并加说明段。

## 10. (3) Setup 1A → 强度 S6~S8：确认不实现（文档 + 代码）

- **代码**：移除 `debug_info['passive_absorption_bull'/'bear']` 调试标记（原仅写标记、不参与计分，易误读为存在计分通道）；
- **文档**：删除「被动吸收反转为期权卖方赋能 → 强度通常在 **S6~S8（28~34 分）**」声明，改为「被动吸收不单独赋能强度，只通过 `of_strength` 正常参与维度 1 打分；该描述**未实现且不予实现**」。

## 11. (4) 文档补记 5 项「代码有但文档未写」

在 §3.1.2 新增「实现补充」块：① 维度 2 兼容**裸方向串** `Bullish`/`Bearish`（同样 20 分）；② 维度 3 缺 `ema_data` 时两侧**各 7 分**兜底；③ 总分**并列 ⇒ NONE 拒绝**（须严格 `>` 且 `>= 55`）；④ 全局 `auto_strategy` 可**强制覆盖**选档；⑤ `trade_decision` **硬闸**（解耦打分时须 `OPEN_LONG`/`OPEN_SHORT` 同向）。

## 12. 校验与回滚

- `py_compile` **6 文件全 OK**；`symtable` 未定义名扫描 **全 OK**
- `test_l1_h1_breakeven_stop.py` **通过**；`test_quant_pivot_option_seller.py` 2 例失败 —— **A/B 对照确认既存失败**（切回改动前备份结果相同）
- 服务 `/bbt_option_seller`、`/api/option_seller/status` = **200**
- 手册 HTML errors=**0**、残留 **0**、断链 **0**；`四维`/`维度 4`/`或命中 QuantPivot L2/H2 极值` 残留 **0**
- 关键残留：`bull_piv`/`bear_piv`/`d3_pivot_score` = **0**（余 1 处注释说明）

**回滚点**：`/tmp/l0c_bak/`（auto_mechanisms / option_seller_engine / option_seller_manager / order_flow_sentinel）、
`/tmp/manual_pre_d3rm.html`、`/tmp/manual_md_pre_d3rm.md`（维度3 删除前）、
`/tmp/manual_post_d3rm_ema.html`、`/tmp/manual_md_post_d3rm_ema.md`（成品）。

## 13. 风险提示（待用户确认）

L0-C 容差为**相对 0.10%**（SPY≈767 时约 0.77 点），而 15m EMA13/21 带宽通常仅约 0.4 点 ⇒
「贴近下沿」与「贴近上沿」**可能同时成立**；当**跳空低开与高开前置同时满足**（宽幅双向日）时会**同时掩码两个方向**，
`evaluate_auto_entry_cycle` 因可用方向为空而跳过全部机制 ⇒ **该周期不交易**（保守/安全侧）。
如需避免「双向同时掩码」，可加一条「L0-C 不得同时掩码两侧」的守卫 —— 请确认是否要加。

---

# 第三轮：L0-C 补齐手册「第二条」判定（有界口径）

## 14. 背景

手册 L0-C 原文含**两条并列**判定（「或」关系）：
1. 现价距 **15m 或 1h** EMA13/21 带**沿** `<= 0.10%`；
2. 现价处于 **EMA13 与 21 之间/下方（上方）** 且**尚未在带外实体站稳 2 根 5m K 线**。

首轮实现**只做了第一条**（docstring 已如实标注）。用户选择**方案 2（有界口径）**补齐第二条。

## 15. 为何必须补 1h 带的「站稳」计数

1. **两条并列、且第一条明确覆盖 15m 或 1h** ⇒ 第二条的「EMA 13 与 21」承前指同一组均线，须能对 **15m 与 1h 分别判定**；
2. **计数单位是 5m K 线**（手册原文），与带所属周期无关 ⇒ 判 1h 带时须用 **5m 收盘价** 数「连续收在 1h 带外」的根数，而非 1h K 线；
3. 原 `bars_outside_band()` 是「同周期 K × 同周期带」，且只在 `minutes == 15` 分支调用 ⇒ 1h 无数据。已改为 **`consecutive_closes_beyond(5m_closes, 带沿)`**，对 **15m 与 1h 均产出** `bars_outside[<tf>_above/_below]`。

## 16. 实现（方案 2：有界口径）

**`ema_engine.py`**
- 新增 `consecutive_closes_beyond(closes, level, above, max_bars)`；
- `compute_ema_snapshot` 预取 **5m 收盘序列**，对每个周期带产出 `bars_outside["15m_above"/"15m_below"/"1h_above"/"1h_below"]`。

**`auto_mechanisms.py`（L0-C）**
- 新增常量 `EMA_BAND_ZONE_PCT = 0.50`（第二条的**有界上限**）、`EMA_STAND_BARS = 2`；
- 判定 = **第一条 OR 第二条**：

  | 禁区 | 条件 |
  | :--- | :--- |
  | 阻力（掩码 BULLISH） | `bearish_ctx` 且（① 距下沿 ≤0.10% **或** ② 逐周期：`band_low×(1−0.5%) <= price <= band_high` 且 `bars_above(tf) < 2`） |
  | 支撑（掩码 BEARISH） | `bullish_ctx` 且（① 距上沿 ≤0.10% **或** ② 逐周期：`band_low <= price <= band_high×(1+0.5%)` 且 `bars_below(tf) < 2`） |

- `detail['clause1']` / `detail['clause2']` 全量可观测（含每个周期的 `in_zone_*`、`bars_*`、`band`）。
- **为何要有界**：若不加 0.5% 上限，单边下跌日中「价格远在带下方」会长期成立 ⇒ 长时间掩码多头（过度拦截）。

## 17. 实现中发现并修复的缺陷

首版把「在带内」与「未在带外站稳」**跨周期独立 OR**，导致：1h 带通常远在价下方 ⇒ `1h_above` 恒 ≥ 2 ⇒
「已站稳」恒真 ⇒ **第二条退化为永不生效**。已改为 **逐周期分别取合取（在带内 ∧ 未在该带外站稳）后再取并集**。

## 18. 验证

**边界语义单测（带 766.0~766.4）**

| 用例 | 结果 |
| :--- | :--- |
| 价 765.0（距下沿 0.13%，第一条不命中）、`bars_above`=0 / 1 | 掩码 **BULLISH**（第二条成立） |
| 价 765.0、`bars_above`=2 | **不掩码**（已在带上方站稳 ⇒ 第二条不成立） |
| 价 762.5（距下沿 0.46%，在 0.5% 内） | 掩码 **BULLISH** |
| 价 762.0（距下沿 0.52%，超上限） | **不掩码**（有界生效） |
| 无跳空 / 无日内极值（无前置 ctx） | **不掩码** |
| 带上方 + 高开日 | 掩码 **BEARISH**（对称） |

**真实数据（2026-09-11）**：`bars_outside` 现同时输出 15m/1h；逐时点 L0-C 命中与 `clause1/clause2` 明细均可观测。

**回归**：`py_compile` OK、未定义名扫描 0、`test_l1_h1_breakeven_stop` 通过、服务 200、手册 errors=0 / 断链 0。

**回滚点**：`/tmp/l0c_bak/`（auto_mechanisms / option_seller_engine / option_seller_manager / order_flow_sentinel）+ 本轮 `ema_engine.py` 首次提交版本见对话记录。


---

# 第四轮：§3.1.3.1 删除表前三段（内容已表内化）

## 19. 改动

用户指出 §3.1.3.1 表格上方的三段说明「应该已经包含在下面的表格里了」，要求删除：
① 触发容差铁律（Strict [-0.2, +0.2] Band）；② 「本机制不再向共振评分贡献分数」说明；③ 多次开仓（Triple-Barrier Multi-Entry）。

**核实**：① 的容差带与 QUALIFIED/ARMED 降级确已在表内「触发点位与容差带（SPY）」列；③ 的三维准入确已在表首「前置规则」行的 **② 多次开仓三维准入**。**但表内缺 3 处小信息**，删段前已折入表内：

| 缺失信息 | 折入位置 |
| :--- | :--- |
| 容差带口径「±0.2 点为准」+ **SPX/ES 等高点位标的等比映射 2.0 点** | 两行「触发点位与容差带」列 |
| **对 L1 / L2 / H1 / H2 四个具体点位分别开放多次开仓** | 表首前置规则 **②** 标题 |
| **解除「单日仅触发一次」的僵化限制** | 表首前置规则 **②** 标题 |

② 为纯说明（同义信息已见于 §3.1.2 与 §3.1.3 章首「用途 1」）⇒ 直接删除。
③ 原句中的「下标第 5 列」为**失效引用**（该列已重构为表首前置规则行）⇒ 随删段一并清除。

## 20. 校验

- 三段 + 失效引用「下表第 5 列」在 HTML/MD 残留 **0**
- 折入内容在位：`等比映射为` ×3（2 处新增 + 1 处既有）、`四个具体点位分别开放多次开仓` ×1、`解除「单日仅触发一次」` ×1
- 手册 errors=**0**、残留 **0**、断链 **0**
- **回滚点**：`/tmp/manual_pre_del3p.html`、`/tmp/manual_md_pre_del3p.md`


---

# 第五轮：§3.1.3.1「微观共振与均线验证」删除三项限制（代码 + 文档）

## 21. 改动

用户要求删除机制 ②「微观共振与均线验证」列中的三项限制（上/下边界对称）：
- CVD 顶/底背离或 Delta 急剧反向；
- DOM 主动单竭尽 + 卖方/买方大单冰山吸收或真空；
- Smashelito R1/R2（S1/S2）或日内 Pivot 上/下轨遇阻。

**代码**（`option_seller_engine.py`）：
1. 上边界 gate：`if ema_ext >= 0.08 or has_micro_exhaustion_top or ...` → **移除 `has_micro_exhaustion_top`**；
2. 下边界 gate：对称移除 `has_micro_exhaustion_bot`；
3. 删除已无引用的 `has_micro_exhaustion_top/bot` 定义（并以注释说明删除原因）；
4. 引擎 docstring 聚合清单由「四维（含 Smashelito Pivot & auction key levels）」改为**三维 60/30/10**。
- **Smashelito 在机制 ② 代码中从未实现**（全文件仅 docstring 提及）⇒ 仅需删文档声明，无对应代码可删。

**文档**（HTML + MD，两行对称）：
- 「微观共振与均线验证」列由 4 项 → **仅保留 `15m EMA 正/负乖离率 ±0.08%`** 一项。

## 22. 行为影响（重要，方向与直觉相反）

机制 ② 的该 gate 原为 **OR**：
`ema_ext 达标 **或** DOM 竭尽/背离 **或** 现价已在带内 **或** zone ∈ {TESTING_H1/H2}`
⇒ 「CVD/DOM 竭尽·背离」原本是 **OR 中的一条放行路径**，而非拦截条件。

移除它之后，仅在**窄缝情形**下略有收紧：`zone ∈ {AT_OR_ABOVE_H2, BETWEEN_H1_AND_H2}` **且** `现价 < H1 − 0.2` **且** `EMA 乖离 < +0.08%` —— 原先可靠「DOM 竭尽/背离」放行，现会被拦下。其余路径不变（gate 仍为 OR，且「现价已在带内」自动满足）。

## 23. 校验

- `py_compile` OK；未定义名扫描 **0**；`has_micro_exhaustion` 残留 = 1（仅注释）
- `test_quant_pivot_option_seller.py` 仍为 **2 例失败**，**A/B 对照（切回改动前引擎）结果完全相同** ⇒ 既存失败，非本次引入
- 服务 200；手册 errors=**0**、残留 **0**、断链 **0**；表格两行「微观」列现仅含 EMA 乖离
- **回滚点**：`/tmp/l0c_bak/option_seller_engine.py.pre_micro`、`/tmp/manual_pre_micro.html`、`/tmp/manual_md_pre_micro.md`

## 24. 遗留提示

该列现只列 EMA 乖离一项，**但代码中它仍是 OR 选项**（与「现价已在带内 / zone ∈ TESTING_*」并列），
即**并非必填**。若要让文档与代码语义完全一致，可将列名与措辞改为「均线乖离验证（四选一之一，非必填）」——
待用户确认。


---

# 第六轮：查实并修复「15m EMA 乖离率」从未生效（键名不匹配 + 缩放污染）

## 25. 起因

用户追问「你指的是 `15m EMA 正乖离率 >= +0.08%` 吗」——顺此核查该判据的取数链路，发现**它从未生效**。

## 26. 两个缺陷

**① 键名不匹配（读侧与产侧不一致）**
```python
# option_seller_engine.py:837
ema_ext = float(ema_data.get('ema15_dist_pct', 0.0) if ema_data else 0.0)
```
- 代码读 `ema_data['ema15_dist_pct']`；**全仓库无任何生产者**（grep 仅命中该读取处）；
- 新建的 `ema_engine` 快照只产出 `dist_pct = {'15m':…,'1h':…}`；
⇒ `ema_ext` 实盘**恒为 0.0**，`>= +0.08` / `<= −0.08` **永远为假** ⇒ 该判据从未参与决定（此前全靠 OR 中的「现价已在带内 / zone ∈ TESTING_*」放行）。

**② 修复时又引入并随即修掉的一处缩放污染**
在快照补出 `ema15_dist_pct` 后，`rescale()` 的「按比例缩放以 `ema` 开头的数值键」逻辑把**百分比键也乘了尺度因子**（0.1 × 0.1 = 0.01）。
已修正为**只缩放价格类键**（跳过含 `dist` / `pct` 的键）。

## 27. 改动（`ema_engine.py`）

1. 快照补出兼容契约键：`ema15_dist_pct` / `ema1h_dist_pct`（= `dist_pct` 同值，乖离率 = (现价 − EMA21)/EMA21×100，与尺度无关）；
2. `rescale()` 的缩放白名单改为「`ema` 开头 **且** 不含 `dist`/`pct` **且** 为数值」。

## 28. 行为影响

- 「15m EMA 乖离率」判据**自此可真正生效** ⇒ 在窄缝情形（`zone ∈ {AT_OR_ABOVE_H2, BETWEEN_H1_AND_H2}` ∧ `P < H1 − 0.2`）下**多了一条放行路径**（放宽）；
- 与第五轮「删除 CVD/DOM 竭尽·背离」的**收紧**在窄缝上大致相互抵消；常规路径（现价已进/触带）不变。

## 29. 校验

- `py_compile` OK；未定义名扫描 **0**
- 实测：`ema15_dist_pct = 0.1`（缩放前后一致）、`ema15_13` 由 7669.80 → 766.98（factor 0.1000）⇒ 价格缩放、百分比不缩放，均正确
- `test_l1_h1_breakeven_stop` 通过；服务 200
- **回滚点**：`/tmp/l0c_bak/option_seller_engine.py.pre_micro`（引擎侧不变）；`ema_engine.py` 本轮两处改动见对话记录


---

# 第七轮：从代码删除「15m EMA 乖离率」判定；文档保留并标记「未使用」

## 30. 改动

**代码**（`option_seller_engine.py`）
- 上边界：删除内层 `if ema_ext >= 0.08 or P >= H1−0.2 or zone ∈ {TESTING_H1, TESTING_H2}:`，**整体去一级缩进**保留其体；
- 下边界：对称删除 `if ema_ext <= -0.08 or …:`；
- 删除判定后，内层剩余两项**已被外层条件蕴含**（`{TESTING_H1/H2} ⊂ {AT_OR_ABOVE_H2, TESTING_H1, TESTING_H2, BETWEEN}`）⇒ 该内层 `if` 恒真，故直接移除（行为等价于「恒真」）；
- `ema_ext` 计算**保留但改为仅记录**（注释声明不参与任何开仓判定），仍输出到 `debug_info` / rationale 供诊断。

**文档**（HTML + MD）
- 「微观共振与均线验证」列两行保留原判据，追加 **【未使用】** 红字标记 + 「当前代码不将其作为开仓判定条件，仅作记录」；
- 表格后新增说明段，解释【未使用】含义并明确机制 ② 的**实际准入 = 触发点位与容差带 + 前置规则（波幅/位置 + 三维准入）**。

## 31. 行为影响

- 删除 EMA 项后，机制 ② 的内层门槛恒真 ⇒ **实际准入 = 外层（QP zone ∈ 4 值 或 现价达 H1−0.2）+ 日内位置**；
- 净效果：在原有**窄缝情形**（`zone ∈ {AT_OR_ABOVE_H2, BETWEEN_H1_AND_H2}` ∧ `P < H1 − 0.2`）下**不再有任何附加门槛** ⇒ **略微放宽**（此前需 `ema_ext ≥ +0.08%` 放行）。常规路径不变。

## 32. 过程记录（一次误恢复与纠正）

A/B 对照测试时，为对比把工作区临时切回 `…pre_ema_rm`，随后**恢复用错了备份路径**（`/tmp/l0c_new/`，那是**第一轮**的快照，早于 D3 删除与 micro-exhaustion 删除）⇒ 工作区一度退回旧版本。
已通过标记校验发现（`has_micro_exhaustion` 4 处、无 `d3_ema_score`、无 `OF_SCORE_MAP{10:60}`），随即从**正确基线** `/tmp/l0c_bak/option_seller_engine.py.pre_ema_rm` 恢复并**重新应用删除脚本**，逐标记复核通过；并把易误用的 `/tmp/l0c_new` 重命名为 `/tmp/l0c_new_STALE_DO_NOT_USE`。**教训**：A/B 对照后恢复必须按「每步快照」而非任意历史快照，且恢复后要跑标记校验。

## 33. 校验

- `py_compile` 6 文件全通过；未定义名扫描 0
- 标记复核：`ema_ext >= 0.08` / `<= -0.08` 残留 **0**；删除注释 **2** 处；`d3_ema_score` **4**；`OF_SCORE_MAP{10:60}` **1**；`has_micro_exhaustion` **1**（仅注释）
- `test_l1_h1_breakeven_stop` 通过；`test_quant_pivot_option_seller` 2 例失败（**既存**，A/B 一致）
- 服务 200；手册 errors=**0**、残留 **0**、断链 **0**；`【未使用】` HTML/MD 各 **3** 处
- **回滚点**：`/tmp/l0c_bak/option_seller_engine.py.pre_ema_rm`（删除前）· `…post_ema_rm`（成品）；文档 `/tmp/manual_pre_emaunused.html` · `/tmp/manual_md_pre_emaunused.md`

---

# 第八轮：§3.1.3.1「开仓规则」文档 ↔ 代码一致性修正（审计差异清单自主落地）

> 用户指令：把审计报告 `audit_312_3131_manual_vs_code` 的 §3.1.3.1 差异清单，**依据前述文档修改思路与原则，自主做最优决策，不需要确认**。原则不变：**文档是规则权威 → 代码向文档对齐**；不予实现的规则从代码删除并在文档标注；单一权威（不重复实现）；缺数据以保守方向处理；最小行为面。

## 34. 本轮定位

审计 19 项差异中，§3.1.3.1 相关 12 项本轮全部处置完毕：**代码 9 项**（含 3 项本轮自查新发现的真实缺陷）、**文档 9 项**、**判定收口 1 项**（触发侧不复查波幅 → 以「施行时点」写清）、**新增回归 40 例**。

## 35. 代码改动清单

### 35.1 触发/布防跨进程链路（审计 #8 #9 #10 #16）

| # | 缺陷 | 修复 |
| :--- | :--- | :--- |
| 1 | 布防在 `order_flow_sentinel` 子进程、触发在 `bbt_data_web`，`qp_level`/`quant_pivot` 无法携带（条件单表无 level 列） | ARMED notes 追加机器标记 `[QPLevel: X] [L1H1: true] [Anchor: n]` |
| 2 | 触发侧仅认 `QuantPivot X` 字面量，ARMED 单恒解析为 `None` ⇒ 三维准入被 `and qp_level` 整段跳过 | 四级兜底：DB 字段 → `QuantPivot X` → `[QPLevel: X]` → `(H1=…)`；并抽出纯函数 `parse_qp_meta()` 供单测 |
| 3 | 触发侧 `quant_pivot=None` 使锚位与 Gamma 墙全失效 | 触发侧重新获取 QuantPivot（失败仅告警，锚位仍由标记生效） |
| 4 | 原位将 pending 单**在开仓前**移除 ⇒ 任一闸门拒绝即静默丢单（内存无、DB 仍 PENDING） | 改为 **open_trade 成功后才移除**；失败保留可重试并落 `SKIPPED_GUARD / open_trade_returned_empty` 事件；删除死标记 `_consume_pending` |

### 35.2 Strike 锚定（审计 #16 #17）

- **单一权威**：`target_short_anchor` 由机制判定层给出并透传；引擎 QUALIFIED 分支写 `debug_info['target_short_anchor']`，`_open_from_engine` 与条件单触发路径均传入 `find_optimal_spread`。
- **与 `quant_pivot` 解耦**：锚位来源改为「调用方传入优先，且不依赖 QP 是否取到」；仅在未传锚位时才走旧「按 spot 与 L1/L2·H1/H2 自行推定」兼容路径。
- **锚位不可绕过**：锚位集合为空 ⇒ 退守 L2/H2；退守仍为空 ⇒ **置空主检索集合**（宁可不开仓）。
- **cushion 回退保锚**：回退改为**从全链重取**并叠加锚位 / Gamma 墙边界 —— 原实现从「已按 cushion 过滤的集合」再取子集，`min_cushion_pct ≥ 0.25` 时该回退**恒为空操作**（放宽是假的）。

### 35.3 本轮自查发现并修复的 3 处真实缺陷（不在原审计清单内）

1. **`target_short_anchor` 未绑定先使用**：`find_optimal_spread(...)` 调用写在第 2609 行、变量赋值在第 2664 行 ⇒ 一旦走到条件单触发路径即 `UnboundLocalError`；同时 `if not cand:` 守卫被留在调用之前。已重排为「解析 → 调用 → 守卫 → 落 cand 字段」。**由新工具 `/tmp/scan_use_before_def.py` 抓出**。
2. **回退分支调用不存在的方法**：`cls._search_call_candidates(...)`（类中只有 `_search_bull_put_candidates` / `_search_bear_call_candidates`）⇒ 熊市看涨价差一旦走到 cushion 回退即 `AttributeError`。已改为 `_search_bear_call_candidates`。**由 `/tmp/scan_missing_attr.py` 抓出**（该扫描器已用「注入已知笔误的副本」验证有效）。
3. **`is_l1_h1` 大小写缺陷**：`('L1H1: true' in notes_str.lower())` 左侧为大写、右侧已小写 ⇒ **恒 False** ⇒ 自动布防的 L1/H1 单丢失 pivot 标记（连带 breakeven 保本位移等 L1/H1 专属处理不生效）。已改为 `'l1h1: true' in …lower()`。

### 35.4 闸门清理

- **Setup 闸门 fail-open → fail-closed**（审计 #7）：原 `if setup and not ok:` 在 `setup_result` 整体缺失时**整段跳过**文档要求的 Setup 闸门；改为必查，缺失即判不合格并给出可读原因。
- **删除 EMA 严重缠结死否决**（审计 #5）：`is_tangled` 与生产者 `tangled` 键名失配 ⇒ 从未生效；且与 §3.1.4.1「平衡日**允许** EMA 缠结（须边界确认）」直接冲突 ⇒ 按「不予实现的规则从代码删除」处理。

## 36. 新增回归测试（40 例）

| 文件 | 例数 | 覆盖 |
| :--- | :--- | :--- |
| `test_qp_meta_parse.py` | 20 | 机器标记解析、旧格式与括号兜底、锚位推导（含 0 值视为无效）、**触发路径语句顺序/结构回归**（锚位先于选单、守卫在调用后、pending 在 open_trade 后消费、无死标记） |
| `test_strike_anchor_3131.py` | 11 | Short Put ≤ 锚位 / Short Call ≥ 锚位；无 QP 亦生效；缺锚位时保留兼容推定；退守不绕过锚位（无候选 ⇒ 不成交）；**cushion 回退保留锚位且确实放宽**；Gamma 墙 SPX→SPY 换算 |
| `test_conditional_order_trigger_3131.py` | 9 | ARMED 上/下轨端到端触发（含现价/条件匹配）、锚位透传至短腿、开仓失败保留 pending、级别不可判定 fail-closed、QP 重取、`_open_from_engine` 透传锚位 |
| `test_quant_pivot_option_seller.py`（改） | 4 | 夹具按「删除维度3 + 60/30/10 + ≥55/≥75」重建（原断言已删除的 `d3_pivot_score` 且总分仅 35 ⇒ 长期既存失败）；现 4/4 通过，锚定断言 779 ≥ H2、764 ≤ L2 |

## 37. 文档修正（HTML + MD 同步，9 项）

1. 维度 1 触发阈值栏旧 **40 分制**数字 → **60 分制**（60/56/51/47/42/38/33/30/23）；
2. 补录维度 1 **兜底口径**（强度缺失/越界按强度 3 = 30 分）；
3. 维度 3 重写为代码实态（基准 +7 / 无序两侧 +5；乖离 ±0.15% ⇒ +5、其余两侧 +3；封顶 10；缺数据两侧 7），**删除未实现的「需贡献 ≥6 分」门槛与「动能衰竭」表述**（审计 #3）；
4. §3.1.2.1 选型更正为**只由共振得分决定**（QuantPivot 已不参与机制 ① 打分与选档；L2/H2 ⇒ 激进型归机制 ②）（审计 #2）；
5. §3.1.3.1 前置规则①补 **AND 语义 / 位置上下界 60–95% 与 5–40% / ES 与 SPY 口径拆分 / 施行时点**（审计 #10 #11 #13 #14）；
6. 前置规则②按代码改写（内存活跃仓 / `status != 'OPEN'` 且 `realized_pnl < 0` 熔断 / `elapsed ≤ 45` 拦截 / **触发侧强制执行且级别不可判定 fail-closed**）；
7. Strike 锚定栏标注**硬约束、不可绕过、单一权威 + ARMED 跨进程标记机制**（审计 #16 #17）；
8. 新增 **§3.1.3.4.4 施行时点与外围闸门**：机制 ② 专属 `07:00–11:30` 窗口（审计 #18）· L0-D/L0-E 组数闸门 · 条件单布防截断区 `11:00–23:30` · 哨兵侧「无活跃 AUTO 仓才判定」更严闸门（审计 #19）；
9. 实现补充补录 **EMA 缠结否决已删除** 与 **Setup 闸门缺数据 fail-closed** 两项（审计 #5 #7）。

## 38. 判定收口（审计 #14）

**触发路径不复查前置规则①（波幅/位置）**：以**施行时点**口径收口而非新增代码 —— 布防即该机制的准入决策点（5 分钟周期持有 OF 快照），触发侧（8 秒巡检，另一进程）不持有 OF 快照，重复取数会引入 DB/接口负载与陈旧数据风险。文档已明确写出两处时点各查什么，不再构成「文档要求但未实现」。

## 39. 新增/复用工具

| 工具 | 作用 | 备注 |
| :--- | :--- | :--- |
| `/tmp/scan_use_before_def.py` | AST 级「读取未绑定局部变量」扫描 | 已消除推导式假阳性；本轮 `UnboundLocalError` 即由它抓出 |
| `/tmp/scan_missing_attr.py` | 类成员存在性扫描（`self.X` / `cls.X`） | 已用注入已知笔误的副本验证有效 |
| `/tmp/validate_manual.py` | 手册结构校验（标签配平 / 重复 id / 内部锚点 / 残留占位符 / 旧口径数字） | 本轮手册 errors=0、断链 0 |
| `/tmp/scan_undefined.py` | 既有：`symtable` 未定义名扫描 | 全量 0 |

## 40. 校验

- `py_compile`：engine / manager / auto_mechanisms / setup_classifier / ema_engine / sentinel / optimizer / 新测试 = **8 文件通过**；
- 三把扫描器（未定义名 / use-before-assignment / 未定义类成员）：**全 0**；
- 测试：option_seller **44 例通过**（新增 40 + 既有 4）；`test_l1_h1_breakeven_stop` 通过；
- `test_live_resting_limit_order` 1 例失败：**A/B 三方对照**（`pre_patchD` / `pre_fix3131` / 现版本）均 1 例失败 ⇒ **既存**；
- 手册：HTML errors=**0**、断链 **0**、重复 id 仅 `chapter-18`（既存）、**40 分制残留 0**；HTML/MD 17 项关键口径逐项一致；
- 模块索引 `bbt_trading_modules.html`：新增 ⑲ 条目后解析错误数与术前**相同**（7+7，均既存）；
- 服务：`/bbt_option_seller`、`/api/option_seller/status`、`/api/option_seller/force_dry` 全 **200**。

## 41. 行为影响

| 变更 | 方向 | 说明 |
| :--- | :--- | :--- |
| 触发侧锚位生效 + ARMED 单级别可解析 | **收紧**（正确性修复） | 原「BETWEEN/ARMED 单无锚软约束」路径消失；短腿被锚位硬约束 |
| 触发侧三维准入不再被跳过 | **收紧** | 活跃仓 / 熔断 / 45 分钟冷却对 QP 边界单真正生效 |
| 锚位退守为空 ⇒ 不开仓 | **收紧** | 极端突破且全链无候选时不再静默开仓 |
| cushion 回退真正放宽 | **放宽** | 原为死代码/空操作；现可在守住锚位与墙位的前提下取更近行权价 |
| Setup 闸门缺失数据 fail-closed | **收紧** | 实时路径 sentinel 始终提供 `setup_result` ⇒ 实盘无变化 |
| EMA 缠结死否决删除 | **无变化** | 该分支从未生效 |
| `is_l1_h1` 标记修复 | **收紧** | 自动布防的 L1/H1 单恢复专属保本处理（原被静默丢失） |

## 42. 遗留与提示

1. **`test_live_resting_limit_order.py` 1 例既存失败**（`get_order_status` 被多调 1 次）—— 非本轮引入，A/B 三方对照已证；如需修复应单独一轮处理。
2. **ES 与 SPY 口径差异**为设计使然（边界/锚定 = SPY，位置/波幅 = ES），本轮已**写入文档**而未改代码；若要统一口径属行为变更，需先做等价性回归。
3. **触发侧不复查波幅/位置**已以「施行时点」口径写入文档；若将来希望触发侧也复查，需先把 OF 快照持久化供 `bbt_data_web` 读取。
4. **L0-C 双掩码**（宽幅双向日两侧同时被掩码 ⇒ 该周期不交易）仍为保守行为，待用户确认是否加守卫。

## 43. 回滚点

- 代码：`/tmp/l0c_bak/option_seller_engine.py.pre_fallback_fix`（本轮回退修复前）· `…pre_fix3131`（§3.1.3.1 修复前）· `option_seller_manager.py.pre_patchD` · `…pre_setupgate` · `…patchD_applied`（本轮成品）
- 手册：`/tmp/manual_r8.html.bak` · `/tmp/manual_r8b.html.bak` · `/tmp/manual_r8.md.bak`
- 模块索引：`/tmp/mods_pre_r8.html.bak`
- 本归档：`/tmp/wt_md_pre_r8.bak` · `/tmp/wt_html_pre_r8.bak`
