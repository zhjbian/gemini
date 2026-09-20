# 机制 ③「平衡日边界」边界级前置 —— 昨收方向（缺口日保护） 验收报告

- **日期**：2026-09-14
- **归档目录**：`57_2026-09-14_Balanced_Day_PrevClose_Boundary_Gate`
- **用户指令**：**「对不同的边界，针对开仓方向，做和昨天收盘价的限制」**（推广自模块 56 的机制 ② H1/L1 昨收方向）
- **波及机制**：③ `AUTO_BALANCED_DAY_BOUNDARY`（平衡日边界）

---

## 1. 规则与实现

| 开仓方向 | 依据的边界（归属侧 + 最近） | 前置判据 | 不满足后果 |
|---|---|---|---|
| **BEARISH**（卖 Bear Call） | 上侧边界族中**距现价最近**者（`day_high` ∪ {关键位 ≥ 现价}） | `最近上侧边界 > ES 昨收` | 该方向**一票否决** |
| **BULLISH**（卖 Bull Put） | 下侧边界族中**距现价最近**者（`day_low` ∪ {关键位 ≤ 现价}） | `最近下侧边界 < ES 昨收` | 该方向**一票否决** |

**执行位置**：评分器的**方向选择处**（`nearest_boundary_values()` + `check_balanced_boundary_prev_close()`，由 `_select_direction_with_prev_close()` 统一裁决）
⇒ **v1 / v2 同规则**，且探针 / 影子回放**自动继承**。

**回退**：首选方向被拦 ⇒ **回退校验另一方向**；两侧全被拦才 `veto`（不静默降级为「不出信号」）。

### 1.1 ⚠️ 尺度铁律（本模块最重要的口径）

机制 ③ 边界族为 **ES 点**，昨收必须是 **ES 昨收**：

```
ES  昨收（ES=F 上一交易日 Close） = 7659.50     ← 与边界族同尺度 ✅
SPY 昨收 × 10（SPY 764.29）       = 7642.90     ← 差 16.6 点 ❌
```

**反例（实测纯函数）**：ES 边界 `7650` 时 —— 用 ES 昨收 ⇒ 做空**被拦**（正确）；用 SPY 昨收 ⇒ 会**误放行**（结论相反）。

### 1.2 结构性质：至多拦截一侧

上侧边界 `≥` 下侧边界恒成立 ⇒ **正常双边界下本项至多拦截一侧**
（BEARISH 被拦 ⟺ 上边界 ≤ 昨收；BULLISH 被拦 ⟺ 下边界 ≥ 昨收；同时成立要求「上 = 下 = 昨收」的零宽度退化）
⇒ **本前置不会把机制整体静默关掉**，只拦掉「逆缺口」的那一侧。

## 2. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | **ES 昨收**取数（与边界族同尺度）+ 上下文字段 `prev_close` | `PyTools/option_seller/balanced_day_data.py` |
| 2 | 纯函数 + 方向选择接入（v1/v2 同规则，含回退与留痕） | `PyTools/option_seller/balanced_day_boundary.py` |
| 3 | 通道传参（`evaluate_balanced_day_channel`） | `PyTools/option_seller/option_seller_manager.py` |
| 4 | 只读探针：传参 + 新增判据行 | `PyTools/option_seller/intraday_probe.py` |
| 5 | 影子回放同口径 | `PyTools/option_seller/balanced_day_shadow.py` |
| 6 | 契约测试 **24 条** | `PyTools/option_seller/test_balanced_day_prev_close_gate.py` |
| 7 | 规则手册 §3.1.4.1.8（HTML）/ §3.1.4.2（MD） | 交易系统规则手册 |

## 3. 验收证据

### 3.1 新增契约测试 24/24 通过

```
/usr/local/bin/python3 PyTools/option_seller/test_balanced_day_prev_close_gate.py
Ran 24 tests in 0.416s — OK
```

| 组 | 测试 | 断言 |
|---|---|---|
| 纯函数（8） | `test_bearish_passes_when_boundary_above_prev_close` | `上侧边界 > 昨收` ⇒ 放行，`applicable=True` |
| | `test_bearish_blocked_when_boundary_below_prev_close` | 边界 7700 / 昨收 7717 ⇒ 拦截（理由含两数） |
| | `test_bearish_blocked_when_boundary_equals_prev_close` | **严格不等**：相等亦拦 |
| | `test_bullish_passes_when_boundary_below_prev_close` | `下侧边界 < 昨收` ⇒ 放行 |
| | `test_bullish_blocked_when_boundary_above_or_equal` | 上/相等 ⇒ 拦截 |
| | `test_missing_data_is_fail_closed` | 6 组缺项组合 ⇒ 全拦 + `data_missing=True` |
| | `test_non_directional_is_na` | `NONE` ⇒ N/A |
| | **`test_spy_scale_prev_close_would_be_wrong`** | **尺度反例：SPY 昨收会得出相反结论** |
| 最近边界（4） | `test_picks_nearest_on_each_side` | 上 7717 / 下 7690（关键位比 day_low 更近） |
| | `test_includes_key_levels_only_on_their_side` | 上/下侧各取最近 |
| | `test_empty_side_is_none` / `test_none_price_returns_none` | 空侧 / 空现价 ⇒ None |
| 方向选择（4） | `test_primary_passes` | 首选通过，无 blocked |
| | **`test_fallback_to_opposite_when_primary_blocked`** | **主方向被拦 ⇒ 回退对侧并通过** |
| | **`test_at_most_one_side_blocked_for_normal_two_sided_boundaries`** | **结构性质：正常双边界至多拦一侧** |
| | `test_both_blocked_only_in_degenerate_case` / `test_empty_candidates` | 零宽度退化两侧全拦 / 空候选 |
| 评分器（7） | `test_v2_allowed_when_upper_boundary_above_prev_close` | `veto=None`、`_direction=BEARISH`、score ≥70、groups=1 |
| | `test_v2_blocked_when_upper_boundary_below_prev_close` | score None、groups 0、`veto` 含 `balanced BEARISH` |
| | `test_v2_missing_prev_close_is_fail_closed` | 同上前提为缺数据 |
| | **`test_v2_fallback_records_both_sides`** | 回退到 BULLISH，且 gate 明细**两方向都留痕** |
| | `test_v2_without_prev_close_kwarg_still_runs` | 向后兼容：**不传参也 fail-closed**（不再静默放行） |
| | **`test_v1_same_rule`** | **v1 与 v2 同规则**（安全前置不随评分器版本漂移） |
| 尺度守卫（1） | `test_prev_close_is_es_scale` | ES 昨收 > 1000、== QuantPivot ES `prev_close`、与 SPY×10 差 > 5 点 |

### 3.2 只读探针（2026-09-14 实跑）

```
/usr/local/bin/python3 -c "…intraday_probe.probe(date_str='2026-09-14')"

09:45 高点 | mandated=BEARISH | verdict=QUALIFIED
   前置：昨收方向（边界级 · 上侧边界） | actual= 最近边界=7708.25 / 昨收(ES)=7659.5 | passed= True
   理由: …③ 边界命中 score=75.0 >= 70.0、方向=BEARISH 与本点一致、组数=1、路径=R
09:50 高点 | mandated=BEARISH | verdict=QUALIFIED
   前置：昨收方向（边界级 · 上侧边界） | actual= 最近边界=7717.0 / 昨收(ES)=7659.5 | passed= True
07:40 / 07:55 低点 | mandated=BULLISH | verdict=REJECTED
   前置：昨收方向（边界级） | actual= 本侧未出方向候选 ⇒ 未评估 | passed= None
```

⇒ 判据行按**本点统一口径方向**取「该侧最近边界」；当日下侧边界（7690 / 7665.25）**均 ≥ ES 昨收 7659.5**，
故 **BULLISH 侧无候选**（未评估），当日全部命中为 BEARISH（上侧边界 7708–7717 > 昨收 ⇒ 放行）。

### 3.3 影子回放（同口径，只读）

```
/usr/local/bin/python3 PyTools/option_seller/balanced_day_shadow.py --date 2026-09-14 --scorer v2
  2026-09-14      25 次触发  日型 趋势↑
  方向: BULL=0 / BEAR=25        ← 与「下侧边界 ≥ ES 昨收 ⇒ 做多被拦」一致
  质量: 有效 20 / 假信号 5 ⇒ 假信号率 20%（目标 ≤40%）
```
⇒ 影子路径**未被 fail-closed 清空**（昨收取数正常），且方向分布体现了前置的实际作用。

### 3.4 回归（全绿）

| 套件 | 结果 |
|---|---|
| `test_balanced_day_prev_close_gate.py`（新增） | **24/24** |
| `test_intraday_probe.py`（含新增 1 条判据行契约） | **34/34** |
| `test_quant_pivot_option_seller.py` | 4/4 |
| `test_qp_prev_close_gate.py`（模块 56） | 21/21 |
| `test_conditional_order_trigger_3131.py` | 9/9 |
| `test_qp_meta_parse.py` | 20/20 |
| `test_strike_anchor_3131.py` | 11/11 |
| `test_l1_h1_breakeven_stop.py` | 1/1 |
| `test_force_dry_degrade.py` | 18/18 |
| `test_journal_filter_catalog.py` / `_mode_filter` / `_group_key` | 11 / 9 / 12 |

### 3.5 语法

```
python3 -m py_compile PyTools/option_seller/balanced_day_boundary.py \
    PyTools/option_seller/balanced_day_data.py PyTools/option_seller/balanced_day_shadow.py \
    PyTools/option_seller/intraday_probe.py PyTools/option_seller/option_seller_manager.py   → COMPILE OK
```

## 4. 规则手册已同步（规则 11）

- **HTML**：新增子节 **`§3.1.4.1.8 边界级前置：昨收方向（缺口日保护）`**（含规则表、**尺度铁律**告警块、
  作用层级、回退规则、**结构性质**、fail-closed、留痕与影子同口径）；并在 `§3.1.4.1.1 ③ 上侧/下侧归属与距离阈值` 增加交叉引用条目。
- **MD**：`§3.1.4.2 评分与方向` 增加同名规则摘要（含尺度铁律与全部要点），并更新「以 HTML 为准」的收口清单。

## 5. 行为变化摘要（对使用者）

| 场景 | 旧行为 | 新行为 |
|---|---|---|
| 大幅低开日，**上侧边界仍 ≤ 昨收**（阻力未收复昨收） | 可卖 Bear Call 做空 | **该方向拦截**（若对侧通过则改用对侧） |
| 大幅低开日，上侧边界 > 昨收 | 做空 | **不变**（放行） |
| 大幅高开日，**下侧边界仍 ≥ 昨收**（支撑仍在昨收上方） | 可卖 Bull Put 做多 | **该方向拦截**（对称） |
| 大幅高开日，下侧边界 < 昨收 | 做多 | **不变** |
| 正常双向边界 | 原逻辑 | **至多一侧被拦**，机制不会被整体关掉 |
| 昨收 / 边界数据缺失 | （无此校验） | **fail-closed**（记录 `data_missing`，不静默放行） |

## 6. 遗留 / 建议（据实登记）

- **边界数据本身的异常（非本模块引入）**：实测 2026-09-14 `order_flow_signals` 的 ES 价格（7669–7717）
  比同日 `spx_gamma_signals` SPOT（7594.84–7645.03）高约 **75 点**；机制 ③ 的 `day_high/day_low` 直接来自前者。
  本前置只能与**传入的边界同尺度**比较；建议单独复核该日 ES 数据源（是否错用了其它合约/会话）。
- **D 维（真空）与 v1 影子**不受本项影响；`v1_shadow` 仍按同规则计算（便于对照）。

## 7. 回滚

- 代码：`git -C PyTools checkout -- option_seller/balanced_day_boundary.py option_seller/balanced_day_data.py option_seller/option_seller_manager.py option_seller/intraday_probe.py option_seller/balanced_day_shadow.py option_seller/test_intraday_probe.py`，并删除 `option_seller/test_balanced_day_prev_close_gate.py`。
- 规则手册：改动前已留时间戳快照 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html.bak-20260914_231410`（HTML；另有同批 `…_231354`）与 MD 同批快照。
