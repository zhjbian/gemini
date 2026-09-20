# 机制 ②「QuantPivot边界反向」前置条件 ③「昨收方向」 验收报告

- **日期**：2026-09-14
- **归档目录**：`56_2026-09-14_QuantPivot_PrevClose_Direction_Gate`
- **用户指令**：需要添加一个新的前置条件 —— **H1: 只有 H1 高于昨天收盘价时才能开空仓；L1: 只有 L1 低于昨天收盘价时才能开多仓**
- **同日口径澄清（已据此修订）**：**昨收方向 只适用于 H1 和 L1，不适用于 H2 和 L2** ⇒ 本项为**档位级**约束，H2 做空 / L2 做多豁免
- **关联事故**：账本第 5 笔（DB id 238/239）`BEAR_CALL_SPREAD 764/766`，08:41:50 触发、08:44:16 止损，**$-14.00 / 腿（LIVE）**

---

## 1. 事故 → 根因 → 修复

| 环节 | 内容 |
|---|---|
| **现象** | 大幅低开日（昨收 764.29 → RTH 开 759.00），机制 ② 在 **H1=761.53** 自动布防并触发 **卖 Call 做空**，3 分钟内被反弹打穿 2.20× 止损 |
| **根因** | H1/H2 是「以当日 RTH 开盘为锚 + 平均上行扩张」的**相对阻力**；低开日整个阻力带可**整体落在昨收之下**。旧判据只查「波幅 / 日内位置 / 容差带」，**无任何「相对昨收的绝对位置」方向保护** ⇒ 在缺口回补的必经路径上逆势站空 |
| **修复** | 新增**前置条件 ③「昨收方向」**（<b>仅 H1 / L1</b>）：做空 **H1** 要求 `H1 > 昨收`、做多 **L1** 要求 `L1 < 昨收`；**H2 / L2 豁免**。判据在**已判定档位**（`qp_level`）之后执行 ⇒ H1 / L1 档位的 QUALIFIED 与 ARMED 两路径同时被拦；触发侧兜底复核；探针新增判据行（含适用性标注） |

### 真实数据佐证（只读复算）

```
prev_close (2026-09-11 RTH Close) = 764.29
2026-09-14 RTH Open               = 759.00        ← 低开 −0.69%
H1 = 761.53   H2 = 764.28   L1 = 756.50   L2 = 754.81
⇒ H1 (761.53) < prev_close (764.29)   →  新规则判定「禁止开空仓」
⇒ 事故单 238/239（BEAR_CALL_SPREAD，trigger_price=H1=761.53）今日即可被拦
```

## 2. 交付物

| # | 交付 | 位置 |
|---|---|---|
| 1 | QuantPivot 新增 `prev_close`（昨收） | `PyTools/pivots/quant_pivot.py` |
| 2 | 单一权威纯函数（**仅 H1 / L1 适用，H2 / L2 返回 N/A**）+ 按档位判定的前置③ | `PyTools/option_seller/option_seller_engine.py` |
| 3 | 条件单触发侧兜底复核（`SKIPPED_GUARD`） | `PyTools/option_seller/option_seller_manager.py` |
| 4 | 只读探针前置③ 判据行（含 H1/L1 适用性）+ 纳入 `side_pass` | `PyTools/option_seller/intraday_probe.py` |
| 5 | 契约测试 **21 条** | `PyTools/option_seller/test_qp_prev_close_gate.py` |
| 6 | 规则手册 §3.1.3.1 新增前置规则 ③ | `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` / `.md` |

## 3. 验收证据

### 3.1 新增契约测试 21/21 通过

```
/usr/local/bin/python3 PyTools/option_seller/test_qp_prev_close_gate.py
Ran 21 tests in 0.000s — OK
```

| 组 | 测试 | 断言 |
|---|---|---|
| 纯函数（9） | `test_short_passes_when_h1_above_prev_close` | `H1 > 昨收` ⇒ 放行，`detail.ref_level='H1'`、`applicable=True` |
| | `test_short_blocked_when_h1_below_prev_close` | 事故值 `H1=761.53 / 昨收=764.29` ⇒ 拦截，理由含两数 |
| | `test_short_blocked_when_h1_equals_prev_close` | **严格不等**：相等亦拦 |
| | **`test_h2_and_l2_are_not_gated`** | **H2 / L2 ⇒ 放行（N/A）、`applicable=False`、`ref_level=None`** |
| | `test_long_passes_when_l1_below_prev_close` | `L1 < 昨收` ⇒ 放行 |
| | `test_long_blocked_when_l1_above_prev_close` | 高开日 `L1=764.00 / 昨收=760.00` ⇒ 拦截 |
| | `test_long_blocked_when_l1_equals_prev_close` | 相等亦拦 |
| | `test_missing_prev_close_is_fail_closed` | H1/L1 档位缺 `prev_close` / `qp=None` / `prev_close=0` ⇒ 全拦 + `data_missing=True` |
| | `test_non_boundary_level_is_na` | 非 L1/L2/H1/H2 ⇒ 放行（N/A） |
| 引擎（8） | `test_gap_down_short_qualified_blocked` | **H1** 点扎入容差带（本应 QUALIFIED）⇒ `REJECTED`，**无方向、无 `armed_order`**，`applicable=True` |
| | `test_gap_down_short_armed_blocked` | **H1** 点距 H1 ∈ (0.2, 0.5%]（本应 ARMED）⇒ `REJECTED`，**不布防** |
| | `test_gap_up_long_qualified_blocked` | 高开日 **L1** 档位做多 ⇒ `REJECTED`（严格反向对称） |
| | **`test_gap_down_h2_short_not_blocked`** | **低开日 H2 点（H2=764.28 < 昨收 764.29）⇒ `QUALIFIED`，档位 H2、`applicable=False`、无否决项、锚位 H2** |
| | **`test_gap_up_l2_long_not_blocked`** | **高开日 L2 点 ⇒ `QUALIFIED` / 锚位 L2（严格反向对称豁免）** |
| | `test_valid_short_still_passes` | 昨收 < H1 ⇒ `QUALIFIED` / 锚位 H1，行为不变 |
| | `test_valid_long_still_passes` | 昨收 > L1 ⇒ `QUALIFIED` / 锚位 L1 |
| | `test_missing_prev_close_blocks_in_engine` | **H1** 档位且引擎内缺昨收 ⇒ fail-closed |
| 探针（4） | `test_bearish_row_present_and_blocks` | 「前置③ 昨收方向（做空：H1 > 昨收 **· 仅 H1 档位适用**）」行存在、`passed=False`、`prev_close_ok=False`、verdict=`REJECTED`、rationale 含阻断项 |
| | `test_bullish_row_present_and_blocks` | 做多侧同构（仅 L1 档位适用） |
| | **`test_h2_point_gate_not_applicable`** | **现价已达 H2 ⇒ 判据行 `passed=True` + actual 标「不适用」、`prev_close_applicable=False`、verdict=`QUALIFIED`** |
| | `test_passing_case_ready_to_qualify` | 通过时**不**成为阻断项 |

### 3.2 引擎真实事故复现（只读复算，非夹具）

```
$ /usr/local/bin/python3 -c "…evaluate_counter_trend_boundary_opportunity(quant_pivot=<当日真实 qp>, scenario='QP')"
prev_close 764.29  H1 761.53  H2 764.28  L1 756.5  L2 754.81

# ① 事故点：现价 761.59 = H1 容差带内 ⇒ 档位 H1
H1 point  -> REJECTED NONE
gate_upper: {'level':'H1','prev_close':764.29,'ref_level':'H1','ref_value':761.53,
             'comparison':'H1 > prev_close','data_missing':False,'applicable':True}
veto: ['Prev-Close gate (H1 short) failed: H1=761.53 <= PrevClose=764.29
        -> H1 Bear Call blocked (gap-down / weak-open day).']

# ② 豁免对照：同一日把现价推到 H2 之上 ⇒ 档位 H2（H2=764.28 亦 < 昨收 764.29，但本项不适用）
H2 point  -> QUALIFIED BEARISH
gate_upper: {'level':'H2','prev_close':764.29,'ref_level':None,'ref_value':None,
             'comparison':None,'data_missing':False,'applicable':False}
```

⇒ 同一套判据下：**事故当日的 H1 档位输入被拦**，而**H2 档位照常放行**（档位级约束，非轨道级），
令 `prev_close < H1` 时 H1 单也照常 `QUALIFIED`（无过度拦截）。

### 3.3 回归（全绿）

| 套件 | 结果 |
|---|---|
| `test_quant_pivot_option_seller.py` | **4/4 OK**（含新增 `prev_close` 产出断言；H1/H2/L1/L2 exact 值不变） |
| `test_intraday_probe.py` | **33/33 OK**（含 `test_qp_bands_filtered_to_mandated_side` 等既有一致性契约） |
| `test_conditional_order_trigger_3131.py` | **9/9 OK**（夹具 `_QP` 补 `prev_close: 770.00`） |
| `test_qp_meta_parse.py` | **20/20 OK** |
| `test_strike_anchor_3131.py` | **11/11 OK** |
| `test_l1_h1_breakeven_stop.py` | **1/1 OK** |
| `test_force_dry_degrade.py` | **18/18 OK** |
| `test_journal_filter_catalog.py` | **11/11 OK** |
| `test_journal_mode_filter.py` | **9/9 OK** |
| `test_journal_group_key.py` | **12/12 OK** |

### 3.4 语法

```
python3 -m py_compile PyTools/pivots/quant_pivot.py \
    PyTools/option_seller/option_seller_engine.py \
    PyTools/option_seller/option_seller_manager.py \
    PyTools/option_seller/intraday_probe.py        → COMPILE OK
```

## 4. 规则手册已同步（规则 11）

`§3.1.3.1 开仓规则 (Entry Rules)` 前置规则表新增 **③ 昨收方向前置（缺口日保护 · 仅 H1 / L1）**，内容含：
**适用范围（只约束 H1 / L1；H2 / L2 豁免）**、做空（仅 H1）/ 做多（仅 L1）判据、
**H2 / L2 豁免理由**、数据来源与口径、缺数据 fail-closed（含 `applicable` 标记）、
执行位置（判定层按档位 + 触发侧兜底）、机制归属（仅机制 ②）、以及本次事故依据。
同步更新「机制 ② 的实际准入」收口说明（波幅/位置 + 三维准入 + **昨收方向**）。HTML 与 MD 双份已改。

## 5. 行为变化摘要（对使用者）

| 场景 | 旧行为 | 新行为 |
|---|---|---|
| 大幅低开日（`H1 ≤ 昨收`）现价触及/逼近 **H1** | 卖 Call 做空（直接开仓或布防） | **拦截**（`REJECTED`，记 `veto_reasons`） |
| 大幅低开日现价进入 **H2** 档位（即便 `H2 ≤ 昨收`） | 卖 Call 做空 | **完全不变**（H2 豁免，照常 QUALIFIED / 布防） |
| 大幅高开日（`L1 ≥ 昨收`）现价触及/逼近 **L1** | 卖 Put 做多（直接开仓或布防） | **拦截**（严格反向对称） |
| 大幅高开日现价进入 **L2** 档位（即便 `L2 ≥ 昨收`） | 卖 Put 做多 | **完全不变**（L2 豁免） |
| 正常日 / 缺口已收复（`H1 > 昨收` 且 `L1 < 昨收`） | 原逻辑 | **完全不变** |
| 机制 ④ 趋势日极限终点 | 沿 SPX Gamma 墙 | **完全不变**（不受本项约束） |

## 6. 回滚

- 代码：`PyTools` 为独立 git 仓库 ⇒ `git -C PyTools checkout -- option_seller/option_seller_engine.py option_seller/option_seller_manager.py option_seller/intraday_probe.py pivots/quant_pivot.py option_seller/test_conditional_order_trigger_3131.py option_seller/test_quant_pivot_option_seller.py`（并删除 `option_seller/test_qp_prev_close_gate.py`）。
- 规则手册：改动前已留时间戳快照（HTML：`.bak-20260914_225330` 初版插入前 / `.bak-20260914_230048` 口径修订前；MD：`.bak-20260914_230103`）。
