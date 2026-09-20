# 卖家系统：机制 ③「平衡日边界」新增边界级前置 —— 昨收方向（缺口日保护）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家自动触发机制 ③（平衡日边界，`AUTO_BALANCED_DAY_BOUNDARY`）
- **归档目录**：`57_2026-09-14_Balanced_Day_PrevClose_Boundary_Gate`
- **关联**：**模块 56**（同日在机制 ② QuantPivot 边界反向 的 H1/L1 上新增同类前置）；本模块把同一思想推广到机制 ③ 的**边界族**
- **技术栈**：Python 3.11 / `balanced_day_boundary`（v1+v2 评分器）/ `balanced_day_data`（只读取数）/ `OptionSellerManager` 通道 / 只读探针 `intraday_probe` / 影子回放 `balanced_day_shadow` / unittest 契约测试 / 规则手册（HTML + MD）

---

## 1. 需求（用户原文）

> 类似的，请对 … 手册 → **3.1.4 平衡日边界机制 (Balanced-Day Boundary Mechanism)** 加前置条件
> **对不同的边界，针对开仓方向，做和昨天收盘价的限制**

即：机制 ③ 的**每一个边界**，按其服务的**开仓方向**，与**昨收**做方向性校验 —— 与模块 56（机制 ② 的 H1/L1 昨收方向）同源同思想。

## 2. 规则设计

机制 ③ 的**边界族**（Bounds Family）= `day_high` / `day_low`（当日运行极值，行价格）+ Smashelito 4 点位 `ut1` / `fut` / `dt1` / `fdt`（ES 点）。
边界按**与现价的位置**归属：`≥ 现价` ⇒ **上侧**（服务 BEARISH）；`≤ 现价` ⇒ **下侧**（服务 BULLISH）。

| 开仓方向 | 依据的边界 | 前置判据 | 不满足后果 |
|---|---|---|---|
| **BEARISH**（卖 Bear Call） | 上侧边界族中**距现价最近**者 | `最近上侧边界 > ES 昨收` | 该方向**一票否决** |
| **BULLISH**（卖 Bull Put） | 下侧边界族中**距现价最近**者 | `最近下侧边界 < ES 昨收` | 该方向**一票否决**（严格反向对称） |

机理与模块 56 一致：大幅低开 / 跳空缺口日里「阻力」仍落在昨收之下 ⇒ 在此卖 Call 等于逆着缺口回补的必经路径站空；高开日对做多同理。

### 2.1 ⚠️ 关键口径：**尺度铁律**（本模块最大的实现风险点）

机制 ③ 的边界族是 **ES 点**（实测 2026-09-14：`day_high/day_low = 7717.0 / 7665.25`，Smashelito `ut1/fut/dt1/fdt = 7735/7775/7690/7659`），
而 **SPY 收盘价是 SPY 尺度**（`764.29`）。两者**不可直接比较**：

```
ES  昨收（ES=F 上一交易日 Close） = 7659.50     ← 与边界族同尺度 ✅
SPY 昨收 × 10                     = 7642.90     ← 差 16.6 点 ❌
```

⇒ 因此 `prev_close` **必须取 ES 昨收**（`balanced_day_data.load_prev_close_es()` →
`QuantPivotCalculator.get_quant_pivot('ES', target_date=…, gap_adaptive=False)['prev_close']`）。
**反例验证**：某 ES 边界 7650 时，用 ES 昨收（7659.5）⇒ 做空被拦（正确）；用 SPY 昨收（764.29）⇒ 会**误放行**（结论相反）。
本项已写成单元测试（`test_spy_scale_prev_close_would_be_wrong` / `test_prev_close_is_es_scale`）。

### 2.2 作用层级：**边界级 + 方向级**，在评分器的**方向选择处**执行

不新增独立的通道闸门，而是把校验放进评分器的方向选择：这样 **v1 / v2 两个评分器版本自动同规则**（安全前置不随评分器版本漂移），
且**探针 / 影子回放自动继承**（它们都调同一个评分器）。

### 2.3 回退规则与结构性质

- **回退**：方向候选按得分降序逐个校验；首选方向被拦 ⇒ **回退校验另一方向**；两侧全被拦才 `veto`（**不静默降级为「不出信号」**）。
- **结构性质**：上侧边界 `≥` 下侧边界恒成立 ⇒ **正常双边界下本项至多拦截一侧**（同时被拦要求「上 = 下 = 昨收」的零宽度退化）。
  ⇒ 本前置**不会把机制整体静默关掉**，只拦掉「逆缺口」的那一侧（已写成结构性测试）。
- **数据缺失 ⇒ fail-closed**：边界值或昨收缺失 / `≤ 0` ⇒ 该方向拦截，`detail.data_missing=True`（与 §3.1.1.1 L0-A③ 同口径）。

## 3. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `PyTools/option_seller/balanced_day_data.py` | 新增 `load_prev_close_es()`；上下文新增 `"prev_close"` | **ES 昨收**（与边界族同尺度）；`__main__` 自检打印也带上 |
| 2 | `PyTools/option_seller/balanced_day_boundary.py` | 新增 `nearest_boundary_values()` / `check_balanced_boundary_prev_close()` / `_select_direction_with_prev_close()`；v1、v2 的方向选择处接入 | 方向候选按得分序逐个过闸，含回退；`breakdown.prev_close_gate` 留痕 |
| 3 | `PyTools/option_seller/option_seller_manager.py` | `evaluate_balanced_day_channel` 的 `_score_kw` | 传 `prev_close=ctx.get("prev_close")` |
| 4 | `PyTools/option_seller/intraday_probe.py` | `_mech_balanced_day` | 传 `prev_close`；新增判据行「前置：昨收方向（边界级 · 上侧/下侧边界）」 |
| 5 | `PyTools/option_seller/balanced_day_shadow.py` | 逐日回放 | 逐日取 ES 昨收并施加同一前置（**否则影子与实盘口径分叉**） |
| 6 | `PyTools/option_seller/test_balanced_day_prev_close_gate.py` | 新增 | **24 条**契约测试 |
| 7 | `PyTools/option_seller/test_intraday_probe.py` | 新增 1 条 | 探针必须给出该判据行（34/34） |
| 8 | 规则手册 | HTML `§3.1.4.1.8`（新增子节 + `§3.1.4.1.1` 交叉引用）；MD `§3.1.4.2` 摘要 | 规则正文 |
| 9 | 归档 | 本目录 | Plan / Walkthrough（md + html） |

## 4. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| 纯函数 | `TestPrevCloseGateUnit` | 8 条：上/下侧通过、**严格不等**（相等亦拦）、缺数据 fail-closed、非方向 N/A、**SPY 尺度反例** |
| 最近边界 | `TestNearestBoundaryValues` | 4 条：混排取最近、空侧为 None、现价 None |
| 方向选择 | `TestDirectionSelectionFallback` | 4 条：首选通过 / **回退对侧** / **至多拦一侧**（结构性质）/ 零宽度退化两侧全拦 |
| 评分器 | `TestScorerIntegration` | 7 条：v2 放行、v2 被拦（veto）、缺昨收 fail-closed、回退双留痕、**不传参即 fail-closed**、**v1 同规则** |
| 尺度守卫 | `TestPrevCloseEsScale` | 1 条：ES 昨收 > 1000 且 == QuantPivot ES `prev_close`，且与 SPY×10 差 > 5 点 |
| 探针 | `test_intraday_probe` | 34/34；机制 ③ 必须出现该判据行 |
| 影子回放 | `balanced_day_shadow.py --date 2026-09-14` | 正常出分（未被 fail-closed 清空）；方向与「缺口侧」一致 |
| 无回归 | 10 套件 | 全绿（见 Walkthrough §3.3） |
| 语法 | `py_compile` ×5 | 通过 |

## 5. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 1：**尺度用错** | 本模块最大风险。已用「ES 昨收」并加两条守卫测试；手册以「⚠️ 尺度铁律」显式登记 |
| 风险 2：`order_flow_signals` 边界数据本身可能偏移 | 实测 2026-09-14 该表 ES 价格（7669–7717）比同日 `spx_gamma_signals` SPOT（7594.84–7645.03）高 ~75 点（**既有数据异常，非本模块引入**）。本前置只能与传入的边界同尺度；建议另行复核该日 ES 数据源 |
| 风险 3：yfinance 依赖 | ES 昨收取自 ES=F 日线（进程内缓存）。取不到 ⇒ 两侧 fail-closed ⇒ 机制不出信号（**loud**：评分器返回 veto、探针判据行标 `data_missing`）。与机制 ③ 既有趋势日门控（同样依赖 yfinance 且缺省 fail-closed）口径一致 |
| 生效方式 | 纯 `.py` 改动，Flask debug-reloader 自动重载；探针无需重启 |
| 回滚 | 代码在 `PyTools/.git` 下：`git -C PyTools checkout -- option_seller/balanced_day_boundary.py option_seller/balanced_day_data.py option_seller/option_seller_manager.py option_seller/intraday_probe.py option_seller/balanced_day_shadow.py PyTools/option_seller/test_intraday_probe.py`（并删除 `option_seller/test_balanced_day_prev_close_gate.py`）；规则手册留有 `.bak-*` 时间戳快照 |
