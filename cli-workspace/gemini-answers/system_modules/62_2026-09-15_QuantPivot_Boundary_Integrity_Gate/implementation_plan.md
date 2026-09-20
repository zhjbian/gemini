# 卖家系统：机制 ②「QuantPivot边界反向」新增前置条件 ④「边界有效性（未被有效突破）」实施计划

- **日期**：2026-09-15
- **模块**：期权卖家自动触发机制 ②（QuantPivot边界反向，`AUTO_QUANT_PIVOT_BOUNDARY`）
- **归档目录**：`62_2026-09-15_QuantPivot_Boundary_Integrity_Gate`
- **技术栈**：Python 3.11 / `OptionSellerEngine` 判定层纯函数 / `OptionSellerManager` 条件单触发侧 / 只读探针 `intraday_probe` / unittest 契约测试 / 规则手册（HTML + MD）

---

## 1. 背景与问题（真实事故）

用户报障：`http://127.0.0.1:5005/bbt_option_seller` →「今日交易流水账本」序列 **#27**：

```
【BBT期权流水】序列: #27 | 类型: 自动 | 开仓类型: QuantPivot边界反向 [L1] | 标的: SPY
时间: 11:10:38 -> 12:30:07 | 结构: BULL_PUT_SPREAD (批次1 (初级止盈 40%))
合约: SPY0916P-749+747 | TOS: .SPY260916P749-.SPY260916P747 | 周期: 1DTE
策略: BALANCED | 开仓金: $0.21 | 平仓价: $0.24 | 实现盈亏: $-6.00
退出状态: CLOSED_TIME_STOP | 运行模式: DRY
```

### 只读 DB 复核（DB id，非页面序列号）

| id | 开仓 | 触发机制 | 档位 | 子场景 | 短/长腿 | 状态 / PnL |
|---|---|---|---|---|---|---|
| **280** | 11:10:38 | `AUTO_QUANT_PIVOT_BOUNDARY` | **L1** | `RANGE_BOUND_LOWER_BOUNDARY` | 749 / 747 | `CLOSED_TIME_STOP` / $-6.00 (DRY) |
| **281** | 11:10:38 | 同上（批次 2） | L1 | 同上 | 749 / 747 | `CLOSED_TIME_STOP` / $-6.00 (DRY) |

`entry_evidence.debug_info`（只读回放）：

```
rationale: [Range-Bound Lower Boundary Reversal] Price tested QuantPivot TESTING_L1_SUPPORT
           (L1=757.82, L2=756.35) in range-bound regime (Pos=34.0%, RangePct=0.50%)
           on SPY 757.63 with EMA extension -0.01%.
           Open Bull Put Spread [BALANCED, Short Put <= 757.82, Level=L1].
quant_pivot_level: L1      target_short_anchor: 757.82      sub_scenario: RANGE_BOUND_LOWER_BOUNDARY
```

### 当日 RTH 极值（只读 DB `order_flow_signals`，ES 口径）

| 时间 | `rth_price_high` | `rth_price_low` | `price_position_pct` |
|---|---|---|---|
| 11:10 | 7684.50 | **7646.25** | 34.0 |

SPY 口径折算（百分比口径，见 §4.1）：波幅 `(7684.50−7646.25)/7646.25 = 0.50%`，现价 757.63、Pos 34.0%
⇒ **当日最低 ≈ 757.63 − 0.34 × (757.63 × 0.50%) = 756.34**，即 **低于 L1=757.82 达 1.48 点**。

**机理**：价格已**有效跌破 L1**（1.48 点，远超噪声），随后**从下方回抽至 L1**（757.63 落入 `[L1−0.2, L1+0.2]`）。
此时 L1 的角色已由「支撑」变为「阻力」——**回抽测试的是破位后失败的原支撑**。
旧判据只看「波幅 / 日内位置 / 容差带 / 昨收方向」，**无法区分「从上方回踩支撑」与「从下方回抽失败位」**，
于是把它当成正常的支撑回踩开了 Bull Put Spread，收盘时间止损离场。

## 2. 用户指令（需求原文）

> 这是个错误的开仓，当价格跌破了 L1，反弹接近或触碰到 L1 时，也就是从下面回到 L1 时，**不能开多仓**，
> 请对触发机制 QuantPivot边界反向，加上这个限制条件，
> **价格跌破了 L1 定义最低点低于 L1 by SPY 0.8 点**，**反方向最对称处理**。
> ref：规则手册 §3.1.3.1 开仓规则 (Entry Rules)

## 3. 实施目标

| 目标 | 交付 |
|---|---|
| 新增前置条件 ④「边界有效性（未被有效突破）」 | 做多：当日最低点 `<= L − 0.8` 点（SPY）⇒ 该 L 档位当日**禁做多**；做空：当日最高点 `>= H + 0.8` 点 ⇒ 该 H 档位当日**禁做空**（**严格反向对称**） |
| 阈值口径可跨尺度 | SPY **0.8 点**（与容差带 ±0.2 点同刻度）；SPX / ES 等高点位标的等比映射 **8.0 点**；**含等号**（恰好 0.8 点即算有效突破） |
| 双路径同时生效 | **QUALIFIED（直接开仓）与 ARMED（布防哨兵单）都不得绕过** |
| 触发侧兜底 | 覆盖「**布防时尚未突破、布防后价格才有效突破、随后回抽触发**」——该场景布防侧无从拦下 |
| 单一权威 | 判定收敛为一个纯函数（引擎判定层）+ 一个极值解析器，引擎 / 触发侧 / 探针三处共用 |
| 尺度安全 | 极值一律在 **SPY 口径**解析；**禁止**把 ES/SPX 绝对点位 `÷10` 当 SPY 点位（基差陷阱，见 §4.1） |
| 缺数据语义明确 | 极值不可解析 ⇒ **fail-open**（放行）+ `data_missing=True` 留痕（幅度类判据不得让机制整体停摆） |
| 不影响机制 ④ | 趋势日极限终点沿 SPX Gamma 墙开仓，**不受**本项约束 |
| 可观测 | 探针（当日高低点自动触发机制检测）新增前置④判据行；`debug_info.boundary_integrity_*` 留痕 |
| 规则归档 | 规则手册 §3.1.3.1 前置规则表新增 **④**（HTML + MD 双份，规则 11） |

## 4. 关键设计

### 4.1 数据层：SPY 口径极值解析（`resolve_qp_session_extremes_spy`）

机制判定层拿不到「当日 RTH 极值的绝对 SPY 点位」，但拿到的是**两组 ES 口径的百分比量**
（`price_position_pct`、`rth_range_pct`）。百分比与尺度无关（ES 与 SPY 日内涨跌幅一致、比价/基差日内近似常数），
因此用 **SPY 现价**折算即得 SPY 点位的当日极值：

```
range_spy = SPY现价 × rth_range_pct / 100
当日最低  = SPY现价 − (pos%/100)   × range_spy
当日最高  = SPY现价 + (1 − pos%/100) × range_spy
```

取数优先级（命中即止）：
1. `of_metrics['day_low_spy'] / ['day_high_spy']`（或 `rth_low_spy / rth_high_spy`）——**调用方直给 SPY 口径极值**（触发侧折算后传入）；
2. 上述百分比折算（`source='pct_derived'`）；`rth_range_pct` 缺失时退 `rth_range_pts / 10`（**仅差值可除 10**，`source='range_pts_approx'`）；
3. 全部失败 ⇒ `(None, None, 'missing')`。

> **⚠️ 绝对点位铁律（本模块最大风险点，写入代码注释与手册）**
> **不得**把 ES/SPX 口径的**绝对点位**（`rth_price_low/high`）直接 `÷10` 当 SPY 点位。
> 本机实测：2026-09-15 ES RTH 低点 `7646.25`，而同时刻 SPY 仅 `~757.6` ⇒ ES 对 SPY 的**基差 ≈ 0.9%（约 70 ES 点）**，
> **远大于**当日波幅（~0.5%）。`7646.25 ÷ 10 = 764.63` 会落在**现价之上**，
> 把「已有效跌破」整体翻转为「从未跌破」（结论相反）。ES 绝对极值只能在**持有实时 ES/SPY 比价**的调用侧换算（模块 57 已登记同一数据异常）。

### 4.2 判定层：单一权威纯函数

`PyTools/option_seller/option_seller_engine.py`：

```python
QP_BREAK_TOL_SPY  = 0.8     # SPY 口径「有效突破」阈值
QP_BREAK_TOL_HIGH = 8.0     # SPX / ES 等高点位标的等比映射

@staticmethod
def resolve_qp_session_extremes_spy(current_price, of_metrics, pivot_data) -> (day_low, day_high, source)

@staticmethod
def check_qp_boundary_integrity(level, direction, quant_pivot, of_metrics=None,
                                pivot_data=None, current_price=None,
                                session_extremes=None) -> (ok, reason, detail)
```

判据：

| 方向 | 判据 | 不满足 |
|---|---|---|
| `BULLISH`（Bull Put） | `day_low > L − 0.8`（即 `drop = L − day_low < 0.8`） | `drop >= 0.8` ⇒ **拦截**（`detail.drop_pts` 记录实际跌破点数） |
| `BEARISH`（Bear Call） | `day_high < H + 0.8`（即 `rise = day_high − H < 0.8`） | `rise >= 0.8` ⇒ **拦截**（`detail.rise_pts`） |
| 档位 | `L1 / L2 / H1 / H2` **逐档位独立**（跌破 L1 ≠ 跌破 L2） | 非档位 ⇒ `N/A` 放行 |
| 阈值 | `ref >= 2000` ⇒ 8.0 点，否则 0.8 点 | — |
| 缺数据 | 极值 `missing` / 档位值 `<= 0` / **档位值 `nan`·`inf`（非有限值）** ⇒ **fail-open** + `data_missing=True` | 不拦截（`nan` 绝不参与比较） |

### 4.3 机制 ② 判定：前置④ 与前置③ 同构接入（按**已判定档位**）

在 `evaluate_counter_trend_boundary_opportunity()` 的 `scenario in (None,'QP')` 块内，
**先完成档位判定**（`qp_level = 'H2'|'H1'` / `'L2'|'L1'`），再以 `qp_level` 为入参调用纯函数，
并把结果作为后续 QUALIFIED / ARMED 的**合取条件**：

```python
_bi_ok_h, _bi_reason_h, _bi_detail_h = OptionSellerEngine.check_qp_boundary_integrity(
    qp_level, 'BEARISH', qp, of_metrics=of_metrics, pivot_data=pivot_data, current_price=qp_curr_p)
debug_info['boundary_integrity_upper'] = _bi_detail_h
if not _bi_ok_h:
    debug_info['veto_reasons'].append(_bi_reason_h)
...
if _pc_ok_h and _bi_ok_h and is_testing_or_above_h1:          # ← QUALIFIED
elif _pc_ok_h and _bi_ok_h and dist_to_h1 > qp_tol and ...:   # ← ARMED
```

（下轨同构，方向 `BULLISH`，`debug_info['boundary_integrity_lower']`。）
⇒ 由于 H1/L1 档位的两条 `return` 都在分支内部，**QUALIFIED 与 ARMED 天然同时被拦**（既不直接开仓，也不布防哨兵单）。

### 4.4 触发侧兜底：`option_seller_manager.py`

触发进程（bbt_data_web）与布防进程（order_flow_sentinel）分离，且本项的关键风险是
**布防之后**才发生的有效突破。故在 `_evaluate_conditional_orders` 的 `RANGE_BOUND_*` 分支内、
既有「三维准入 + 前置③ 昨收方向」之后，**再复检一次**：

```python
_ext_low, _ext_high, _ext_src = self.resolve_day_extremes_spy_for_gate(curr_p)   # 当日 ES 快照 ⇒ SPY 口径
_bi_ok, _bi_reason, _bi_detail = OptionSellerEngine.check_qp_boundary_integrity(
    qp_level, direction, qp_order, session_extremes=(_ext_low, _ext_high, _ext_src))
if not _bi_ok:
    ... record_conditional_order_event('SKIPPED_GUARD', ...) ; continue          # 不消费 pending
if _bi_detail.get('data_missing'):
    ... debug 日志（fail-open 留痕）
```

`resolve_day_extremes_spy_for_gate()`：读当日 ES `order_flow_signals` 的
`rth_price_high/low`（ES 点 ⇒ **只求百分比波幅**）+ `quantitative_metrics.price_position_pct`，
按 §4.1 公式用实时 SPY 现价折算；**逐行回溯**取「极值 + 位置%」齐备的最近一行（最新一行常缺 `price_position_pct`）。

### 4.5 探针可观测：`intraday_probe.py`

`_mech_counter_trend(..., 'QP')` 两侧各新增判据行：
「前置④ 边界有效性（做多：L1/L2 未被有效突破）」/「（做空：H1/H2 未被有效突破）」，
档位代理与引擎同口径（`L2` 命中即按 L2、`H2` 命中即按 H2），
实际值显示 `当日最低/最高 = X / 档位 = Y（低于/超出 Z 点）`，并**纳入 `side_pass`**；
`side_view` 增 `boundary_integrity_ok` / `_level` / `_applicable` / `day_low` / `day_high` / `day_extremes_source`；
未通过时 `rationale` 显式列出该阻断项。

## 5. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `PyTools/option_seller/option_seller_engine.py` | 模块常量 + 新增两个静态方法 + QP 上/下轨分支 | `QP_BREAK_TOL_*`；`resolve_qp_session_extremes_spy()`；`check_qp_boundary_integrity()`；前置④ 总闸（QUALIFIED + ARMED 双路径）；`debug_info.boundary_integrity_upper/_lower` |
| 2 | `PyTools/option_seller/option_seller_manager.py` | 触发侧辅助 + `_evaluate_conditional_orders` | `resolve_day_extremes_spy_for_gate()`；前置④ 兜底复检 + `SKIPPED_GUARD` 事件（不消费 pending） |
| 3 | `PyTools/option_seller/intraday_probe.py` | `_mech_counter_trend` | 前置④ 判据行（双向）+ 纳入 `side_pass` + `side_view` 新字段 + 阻断文案 |
| 4 | `PyTools/option_seller/test_qp_boundary_integrity_gate.py` | 新增 | **28 条契约测试**（极值解析 5 / 纯函数 10 / 引擎 6 / 探针 4 / 触发侧 3；含 `nan`·`inf` 按缺失处理与「含等号边界」「逐档位独立」） |
| 5 | `PyTools/option_seller/test_conditional_order_trigger_3131.py` | 夹具 `_run` | patch `resolve_day_extremes_spy_for_gate` 为固定「未突破」极值（单元测试不读实时 DB） |
| 6 | `PyTools/option_seller/test_qp_prev_close_gate.py` | 夹具 | 波幅 0.60%→0.30%（旧夹具隐含「当日极值已突破 H1/H2 逾 0.8 点」，会被前置④ 独立拦截，掩盖该文件要测的前置③）；头部登记调整原因 |
| 7 | 规则手册 | `§3.1.3.1` | 新增**前置规则 ④**（HTML + MD）；收口句「实际准入 = … + 边界有效性」 |

## 6. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| 纯函数 | `TestBoundaryIntegrityUnit`（10 条） | 0.8 点**含等号**边界、内侧放行、严格反向对称、**逐档位独立**、SPX 档位 → 8.0 点、极值/档位缺数据 fail-open、**`nan` 档位值按缺失处理**、非档位 N/A |
| 极值解析 | `TestSessionExtremes`（5 条） | 真实案例折算出 `756.34 / 760.13`；直给 SPY 极值优先；`range_pts` 退路标记 `range_pts_approx`；缺数据 `missing`；**`inf`/`nan` 视为 `missing`** |
| 引擎（真实事故复现） | 用 11:10 真实参数（L1=757.82 / SPY=757.63 / Pos=34.0% / RangePct=0.50%） | **QUALIFIED 与 ARMED 两路径都 `REJECTED`**，否决理由含 `Boundary integrity gate (L1 long) failed: … 1.48 pts below L1=757.82`，且**无 `armed_order`** |
| 引擎（反向对称） | H1=761.32 / Pos=66% ⇒ 当日最高 762.59（高于 1.27 点） | 上轨做空 `REJECTED` |
| 引擎（放行对照） | 波幅使当日最低仅低 L1 0.57 点 / 最高未破 H1 | 行为不变（`QUALIFIED` + 锚位仍为 L1 / H1） |
| 引擎（缺数据） | 无 `rth_range_pct` / `rth_range_pts` | fail-open 照常 `QUALIFIED`，且 `data_missing=True` |
| 探针 | `TestBoundaryIntegrityProbeRow`（4 条） | 双向判据行存在、阻断时 `verdict=REJECTED` 且 `rationale` 含「前置④」、放行时不计阻断、缺数据 `passed=None` |
| 触发侧 | `TestTriggerSideGate`（3 条） | 破位 ⇒ **不开仓** + `SKIPPED_GUARD`（`detail.boundary_integrity.level='L1'`）+ pending 保留；未破位 / 缺数据 ⇒ 照常开仓 |
| 真实链路 | `resolve_day_extremes_spy_for_gate(757.63)`（当日 ES 快照） | 返回 `(756.5877, 760.3778, 'es_snapshot_pct_derived')`；同参数下单函数给出 **1.23 点跌破 ⇒ 拦截** |
| 无回归 | 11 套件 | 全绿（详见 Walkthrough §3）；`test_live_resting_limit_order` 1 项失败经 `git stash` 基线复跑确认为**既有失败** |
| 语法 | `py_compile` ×3 | 通过 |
| 手册 | HTML + MD | §3.1.3.1 出现前置④；HTML 标签配平（相对基线 +2 div / +1 ul / +8 li，全部闭合） |

## 7. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 1：尺度混比（最高危） | 已用「百分比折算 + 禁止绝对点位 ÷10」双保险；错误方向本会把「已突破」翻成「未突破」（若误用 `÷10`，7646.25/10=764.63 会高于现价 757.63，闸门**恒放行**） |
| 风险 2：折算精度 | 假设 ES↔SPY 日内比例近似常数；0.5% 波幅下折算误差 ≈ 0.04 SPY 点，相对 0.8 点阈值可忽略；跨日/隔夜基差变化不影响（极值与现价同日） |
| 风险 3：缺数据漏拦 | 判据为**幅度类**，缺极值时 fail-open 并留痕（`data_missing=True`）：前置① 波幅/位置与容差带仍在把关；若要求 fail-closed 可一行切换（见 Walkthrough §6） |
| 风险 4：单调熔断偏严 | 判据是「当日 RTH 极值」（单调量）⇒ 一旦有效突破，该档位**当日后续一律禁止反向开仓**，不区分现价从哪一侧接近。这是刻意的：破位后该档位的统计优势已消失 |
| 生效方式 | 纯 `.py` 改动，`bbt_data_web` Flask debug-reloader 自动重载；5 分钟哨兵（`order_flow_sentinel`）下一轮即用新代码；探针 / 手册无需重启 |
| 回滚（代码） | PyTools 为独立 git 仓库：`cd PyTools && git checkout -- option_seller/{option_seller_engine,option_seller_manager,intraday_probe,test_conditional_order_trigger_3131,test_qp_prev_close_gate}.py && rm -f option_seller/test_qp_boundary_integrity_gate.py` |
| 回滚（手册） | 改动前快照：`…rules_manual-…html.bbt-bak-20260915_191033`、`…rules_manual-…md.bak-20260915_191033`（覆盖回原文件即成） |
| 回滚（归档） | 删除本目录 + 删除 `bbt_trading_modules.html` 中模块 62 的表格行与 `<h3 id="mod-62">` 段落 |
