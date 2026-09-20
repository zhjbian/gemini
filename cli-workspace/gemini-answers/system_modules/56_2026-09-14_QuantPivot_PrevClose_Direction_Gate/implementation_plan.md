# 卖家系统：机制 ②「QuantPivot边界反向」新增前置条件 ③「昨收方向」（缺口日保护）实施计划

- **日期**：2026-09-14
- **模块**：期权卖家自动触发机制 ②（QuantPivot边界反向，`AUTO_QUANT_PIVOT_BOUNDARY`）
- **归档目录**：`56_2026-09-14_QuantPivot_PrevClose_Direction_Gate`
- **技术栈**：Python 3.11 / `QuantPivotCalculator`（yfinance 日线）/ `OptionSellerEngine` 判定层 / `OptionSellerManager` 条件单触发侧 / 只读探针 `intraday_probe` / unittest 契约测试 / 规则手册（HTML + MD）

---

## 1. 背景与问题（真实事故）

用户报障：`http://127.0.0.1:5005/bbt_option_seller` →「今日交易流水账本」第 5 笔：

```
序列: #5 | 类型: 自动 | 开仓类型: 自动条件单 (系统自动武装) | 标的: SPY
时间: 08:41:50 -> 08:44:16 | 结构: BEAR_CALL_SPREAD (批次1)
合约: SPY0914C-764+766 | TOS: .SPY260914C764-.SPY260914C766 | 周期: 0DTE
策略: BALANCED | 开仓金: $0.12 | 平仓价: $0.26 | 实现盈亏: $-14.00
退出状态: CLOSED_STOP_LOSS | 运行模式: LIVE
```

用户观察（附 TradingView SPY 5m 截图）：**「今天大幅低开，H1 还远低于昨天收盘价，这时开空仓很危险」**。

### 只读 DB 复核（DB id，非页面序列号）

| id | 触发机制 | QP 级别 | 子场景 | 条件单 | trigger_price | 状态 / PnL |
|---|---|---|---|---|---|---|
| **238** | `AUTO_QUANT_PIVOT_BOUNDARY` | **H1** | `RANGE_BOUND_UPPER_BOUNDARY` | #60 | **761.53** | `CLOSED_STOP_LOSS` / **$-14.00** (LIVE) |
| **239** | 同上 | H1 | 同上 | #60 | 761.53 | `CLOSED_STOP_LOSS` / $-14.00 (LIVE) |

### 当日 QuantPivot（复算，只读）

```
prev_close (2026-09-11 RTH Close) = 764.29
2026-09-14 RTH Open               = 759.00   ← 缺口低开 −0.69%
H1 = 761.53   H2 = 764.28   L1 = 756.50   L2 = 754.81
⇒ H1 (761.53) < prev_close (764.29)   ★ 甚至 H2 (764.28) 亦 < prev_close
```

**机理**：H1/H2 是「以当日 RTH 开盘为锚 + 30 日平均上行扩张」算出的**相对阻力**。大幅低开时，
整个 H1/H2 阻力带可能**整体仍落在昨收之下**；此时在 H1/H2 卖 Call = **在缺口回补（向昨收回归）的必经路径上逆势站空**，
被反弹打穿 2.20× 硬止损属高概率事件。旧判据只校验「波幅 / 日内位置 / 容差带」，**不含任何「相对于昨收的绝对位置」方向保护**。

## 2. 用户指令（需求原文）

> 需要添加一个新的前置条件：
> **H1: 只有 H1 高于昨天收盘价时才能开空仓**
> **L1: 只有 L1 低于昨天收盘价时才能开多仓**

**同日口径澄清（第二轮回话，已据此修订实现）**：

> **昨收方向 只适用于 H1 和 L1，不适用于 H2 和 L2。**

⇒ 本项为**档位级**约束而非「轨道级」约束：H2 做空 / L2 做多**完全豁免**，照常按触发点位与容差带判定。

参照：规则手册 `§3.1.3.1 开仓规则 (Entry Rules)`。

## 3. 实施目标

| 目标 | 交付 |
|---|---|
| 新增前置条件 ③「昨收方向」（**仅 H1 / L1**） | 做空 **H1** 要求 `H1 > 昨收`；做多 **L1** 要求 `L1 < 昨收`；**H2 / L2 豁免**（`applicable=False` / `N/A`） |
| 档位级生效（非轨道级） | 判据在**已判定档位**（`qp_level`）之后执行 ⇒ H1 单拦、H2 单放行；L1 单拦、L2 单放行 |
| 双路径同时生效 | **QUALIFIED（直接开仓）与 ARMED（布防哨兵单）都不得绕过**（H1 / L1 档位） |
| 单一权威 | 判定逻辑收敛为一个纯函数，引擎 / 触发侧 / 探针三处共用，口径不漂移 |
| 数据同源 | `prev_close` 与 H1/L1 由同一份 30 日日线序列产出，可直接比较 |
| 缺数据 fail-closed | 无法验证的安全前置不得静默放行（与 §3.1.1.1 L0-A③ 同口径） |
| 不影响机制 ④ | 趋势日极限终点沿 SPX Gamma 墙开仓，**不受**本项约束 |
| 可观测 | 探针（当日高低点自动触发机制检测）新增前置③判据行；`debug_info` 留痕 |

## 4. 关键设计

### 4.1 数据层：`prev_close` 随 QuantPivot 一并产出

`PyTools/pivots/quant_pivot.py :: QuantPivotCalculator._calculate_from_market_data()`
在已有 30 日样本 `hist_days`（`date_str < target_date`、升序）基础上直接取：

```python
prev_close = float(hist_days.iloc[-1]['Close'])     # 上一交易日 RTH 收盘
```

并写入**两条 return 路径**（Gap-Adaptive 与 Standard）的返回字典 `'prev_close': round(prev_close, 2)`。
⇒ 与 `h1/h2/l1/l2` **同源同口径**（同一份 adjusted 日线），不存在「平台昨收 vs 计算昨收」两套数字。

### 4.2 判定层：单一权威纯函数

`PyTools/option_seller/option_seller_engine.py` 新增：

```python
@staticmethod
def check_qp_prev_close_direction(level, quant_pivot) -> (ok, reason, detail)
```

- `H1` → 要求 `H1 > prev_close`（`detail['applicable'] = True`）；
- `L1` → 要求 `L1 < prev_close`（`detail['applicable'] = True`）；
- `H2` / `L2` → **`N/A`（放行，`applicable = False`）** —— 1-SD 极值档位不受本项约束；
- 其他级别 → `N/A`；
- **适用档位**缺 `prev_close` / H1 / L1 或值 `<= 0` ⇒ **fail-closed**，`detail['data_missing'] = True`；
  H2 / L2 天然不因缺数据拦截。

> 修订说明：初版把方向门放在**轨道分支入口**（H1 基准覆盖整个上轨，含 H2），属「轨道级」；
> 用户澄清后改为**档位级** —— 把校验下移到 `qp_level` 判定之后，并以 `qp_level` 为入参调用纯函数。

### 4.3 机制 ② 判定：前置③ 按**已判定档位**校验

在 `evaluate_counter_trend_boundary_opportunity()` 的 `scenario in (None, 'QP')` 块内，
**先完成档位判定**（`is_at_h2` / `is_at_l2` ⇒ `qp_level = 'H2'|'H1'` / `'L2'|'L1'`），
**再以 `qp_level` 为入参**调用纯函数，并把结果作为后续 QUALIFIED / ARMED 的**合取条件**：

```python
is_at_h2 = (h2_val > 0 and (qp_curr_p >= (h2_val - qp_tol) or qp_zone in ['AT_OR_ABOVE_H2', 'TESTING_H2_RESISTANCE']))
qp_level = 'H2' if is_at_h2 else 'H1'

# ★ 前置③：仅 H1 档位适用（H2 档位返回 N/A）；本项在 QUALIFIED / ARMED 之前
_pc_ok_h, _pc_reason_h, _pc_detail_h = OptionSellerEngine.check_qp_prev_close_direction(qp_level, qp)
debug_info['prev_close_gate_upper'] = _pc_detail_h
if not _pc_ok_h:
    debug_info['veto_reasons'].append(_pc_reason_h)
...
if _pc_ok_h and is_testing_or_above_h1:          # ← H1 档位的 QUALIFIED
elif _pc_ok_h and dist_to_h1 > qp_tol and ...:   # ← H1 档位的 ARMED
```

（下轨同构，入参 `qp_level ∈ {'L2','L1'}`。）⇒ 由于 `H2` / `L2` 会被纯函数判为 `N/A`（`applicable=False`，返回 `True`），
**H2 做空 / L2 做多天然放行**；而 H1 / L1 档位的 `return` 都在分支内部，**QUALIFIED 与 ARMED 两条路径天然同时被拦**。

### 4.4 触发侧兜底：`option_seller_manager.py`

条件单触发路径（`_evaluate_conditional_orders`）在既有「② 多次开仓三维准入」之后**再校验一次**同一前置：

```python
_pc_ok, _pc_reason, _pc_detail = OptionSellerEngine.check_qp_prev_close_direction(qp_level, qp_order)
if not _pc_ok:
    ... record_conditional_order_event('SKIPPED_GUARD', ...) ; continue   # 不消费 pending
```

覆盖：① 热重载 / 重启前遗留的 PENDING 单；② 跨进程重新取数的 QuantPivot。

### 4.5 探针可观测：`intraday_probe.py`

`_mech_counter_trend(..., 'QP')` 新增判据行「前置③ 昨收方向（做空：H1 > 昨收 · **仅 H1 档位适用**）」/「（做多：L1 < 昨收 · **仅 L1 档位适用**）」。
探针**按引擎同口径**先做档位代理（现价 `≥ H2 − 0.2` ⇒ 本点为 H2 单；`≤ L2 + 0.2` ⇒ L2 单），
据此给出 `pc_applicable` 与**有效值** `pc_ok = (not applicable) or raw`，
并把它**纳入 `side_pass`**（`pos_ok and range_ok and pc_ok and any(side_hits)`）；
`side_view` 增 `prev_close_ok`（有效值）与 `prev_close_applicable`；判据行 actual 会标注「（现价已达 H2/L2 ⇒ 按 H2/L2 档位，本项不适用）」；
未通过且适用时 `rationale` 显式列出该阻断项。

## 5. 改动清单

| # | 文件 | 位置 | 改动 |
|---|---|---|---|
| 1 | `PyTools/pivots/quant_pivot.py` | `_calculate_from_market_data` + 两条 return | 新增 `prev_close`（+文档字符串） |
| 2 | `PyTools/option_seller/option_seller_engine.py` | 新增静态方法；QP 上/下轨分支 | `check_qp_prev_close_direction()`；上/下轨前置③ 总闸；`debug_info.prev_close` / `prev_close_gate_*` |
| 3 | `PyTools/option_seller/option_seller_manager.py` | 条件单触发侧 RANGE_BOUND 守卫 | 前置③ 兜底校验 + `SKIPPED_GUARD` 事件 |
| 4 | `PyTools/option_seller/intraday_probe.py` | `_mech_counter_trend` | 前置③ 判据行 + 纳入 `side_pass` + `prev_close_ok` |
| 5 | `PyTools/option_seller/test_qp_prev_close_gate.py` | 新增 | **21 条契约测试**（纯函数 9 / 引擎 8 / 探针 4），含 **H2 / L2 豁免对照** |
| 6 | `PyTools/option_seller/test_conditional_order_trigger_3131.py` | 夹具 `_QP` | 补 `prev_close: 770.00`（缺键会 fail-closed 拦截） |
| 7 | `PyTools/option_seller/test_quant_pivot_option_seller.py` | Test 01 | 断言 `prev_close` 随取数产出且 > 0 |
| 8 | 规则手册 | `§3.1.3.1` | 新增**前置规则 ③**（HTML + MD 双份） |
| 9 | 归档 | 本目录 | Plan / Walkthrough（md + html） |

## 6. 验收口径

| 层 | 手段 | 通过标准 |
|---|---|---|
| 纯函数 | `test_qp_prev_close_gate.TestPrevCloseGateUnit` | 9 条：H1 / L1 通过、严格不等边界、**H2 / L2 ⇒ N/A + `applicable=False`**、缺数据 fail-closed、非边界 N/A |
| 引擎（真实事故复现） | 用当日真实 QuantPivot（H1=761.53 / 昨收=764.29） | H1 点 ⇒ `REJECTED` + 否决理由含 `Prev-Close gate (H1 short) failed`；**QUALIFIED 与 ARMED 两路径都无输出** |
| 引擎（豁免对照） | 当日同数据推至 H2（=764.28 < 昨收 764.29） | H2 点 ⇒ **`QUALIFIED`**（`applicable=False`，非阻断项）；L2 侧严格反向对称 |
| 引擎（放行对照） | 令 `prev_close < H1` / `> L1` | 行为不变（`QUALIFIED` + 锚位仍为 H1/L1） |
| 触发侧 | `test_conditional_order_trigger_3131` | 9/9 通过（夹具补 `prev_close` 后不回归） |
| 探针 | `test_intraday_probe` | 33/33 通过；前置③ 行随本侧方向出现、计入 `side_pass` |
| 无回归 | 6 套件 | 全绿：quant_pivot 4/4 · intraday_probe 33/33 · qp_meta 20/20 · strike_anchor 11/11 · l1h1 1/1 · journal×3 + force_dry 亦全绿 |
| 真实数据 | 只读 DB / yfinance | `prev_close=764.29`、`H1=761.53` ⇒ 事故单 238/239 **今日即可被拦** |
| 语法 | `py_compile` ×4 | 通过 |

## 7. 风险与回滚

| 项 | 说明 |
|---|---|
| 风险 1：`prev_close` 来源偏差 | 采用与 H1/L1 **同一份**日线序列（yfinance adjusted daily）的上一交易日 `Close`，与 QuantPivot 内部口径完全一致；不引入第二套「平台昨收」数字（否则会因除权/时区产生 ±数点误差） |
| 风险 2：漏接调用点 | 全仓 `evaluate_counter_trend_boundary_opportunity` 共 3 个调用点（实时 manager、只读探针、回填脚本），全部经引擎 ⇒ 一处生效、处处生效；回填脚本的 `qp_dict` 亦由 `get_quant_pivot()` 产出（含 `prev_close`） |
| 风险 3：缺数据误伤 | 理论极罕见（`prev_close` 与 H1 同字典产出）；即便出现也是 **fail-closed + 显式 `veto_reasons` / 探针行**（不静默），符合手册 L0-A③ 既定纪律 |
| 生效方式 | 纯 `.py` 改动，Flask debug-reloader 自动重载；探针 / 手册无需重启 |
| 回滚 | 代码在 `PyTools/.git` 版本控制下：`git -C PyTools checkout -- <files>`；规则手册改动前已留时间戳快照（HTML：`….html.bak-20260914_225330`（初版插入前）与 `….html.bak-20260914_230048`（口径修订前）；MD：`….md.bak-20260914_230103`） |
