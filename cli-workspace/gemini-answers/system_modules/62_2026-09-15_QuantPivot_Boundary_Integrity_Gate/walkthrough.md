# 机制 ②「QuantPivot边界反向」新增前置条件 ④「边界有效性（未被有效突破）」验收报告 (Walkthrough)

- **日期**：2026-09-15
- **归档目录**：`62_2026-09-15_QuantPivot_Boundary_Integrity_Gate`
- **一句话结论**：**真实事故（流水 #27，SPY 跌破 L1 达 1.48 点后从下方回抽，11:10:38 错开 Bull Put Spread）在同一参数下已被硬拦（QUALIFIED 与 ARMED 双路径 `REJECTED`，不再产生任何布防单）；严格反向对称的 H1 「破位后回抽」同样被拦；未突破 / 缺数据时行为不变。**

---

## 1. 事故复现与拦截验证（真实参数，非夹具）

投入参数（全部取自 `order_flow_option_seller_trades` id 280/281 的 `entry_evidence.debug_info` 与当日 `order_flow_signals`）：

| 参数 | 值 | 来源 |
|---|---|---|
| `L1` / `L2` | `757.82` / `756.35` | `entry_evidence.debug_info`（QuantPivot 判定期实时值） |
| `H1` / `H2` | `761.32` / `765.10` | 同上 |
| SPY 现价 | `757.63` | 同上（落入 `[L1−0.2, L1+0.2]` ⇒ 旧判据 QUALIFIED） |
| `price_position_pct` | `34.0` | 同上（∈ [5%, 40%] ⇒ 下轨位置闸门通过） |
| `rth_range_pct` / `pts` | `0.50%` / `38.25` ES 点 | 同上（≤ 0.85% 且 ≤ 45 点 ⇒ 震荡日闸门通过） |
| `prev_close` | `760.88` | 同上（`L1 < 昨收` ⇒ 前置③ 昨收方向通过） |
| 当日 RTH 极值 | high `7684.50` / low `7646.25`（ES） | DB `order_flow_signals` 11:10 行 |

**极值解析（SPY 口径）**：

```
range_spy = 757.63 × 0.50% = 3.7885
当日最低  = 757.63 − 0.34 × 3.7885 = 756.34      当日最高 = 757.63 + 0.66 × 3.7885 = 760.13
drop_to_L1 = 757.82 − 756.34 = 1.478 点  ≥ 0.8 点  ⇒ 有效跌破
```

**引擎实跑（`evaluate_counter_trend_boundary_opportunity(scenario='QP')`）**：

| 场景 | 投入 | 结果 | 留痕 |
|---|---|---|---|
| **QUALIFIED**（现价 757.63 正扎入容差带） | 真实 11:10 参数 | **`REJECTED` / `NONE`** | `veto_reasons`: `Boundary integrity gate (L1 long) failed: session low 756.34 is 1.48 pts below L1=757.82 (>= 0.8 pts) -> L1 Bull Put blocked (broken level retested from below).`；`boundary_integrity_lower = {level:L1, ref_value:757.82, day_low:756.34, drop_pts:1.478, threshold:0.8, source:pct_derived, data_missing:false}` |
| **ARMED**（现价 757.40，距 L1 0.42 点 ∈ (0.2, 0.5%]） | 同上 | **`REJECTED` / `NONE`，`armed_order = None`** | `day_low = 756.11`，`drop = 1.71` ⇒ 拦（**不布防 LTE 哨兵单**） |
| **放行对照**（Pos 34% → 10%） | 最低抬至 `757.25`（仅低 L1 0.57 点） | **`QUALIFIED` / `BULLISH`** | 无 `Boundary integrity gate` 否决项 |

⇒ **修复前后同参数对比：修复前 11:10:38 开出 `SPY0916P-749+747`（$-6.00 时间止损）；修复后同一时刻判定 `REJECTED`，不产生任何开仓与布防。**

**反向对称复现（H1 破位后回抽）**：`H1=761.32`、现价 `761.30`（扎入容差带）、`Pos=66%`、`RangePct=0.50%`
⇒ 当日最高 `762.59`（高于 H1 达 **1.27 点**）⇒ 上轨做空 **`REJECTED`**，`boundary_integrity_upper.level='H1'`。
放行对照（`Pos=80%` ⇒ 最高未破 H1）⇒ 照常 `QUALIFIED / BEARISH`，锚位仍为 H1。

## 2. 触发侧兜底（"布防之后才破位"这一场景）

该场景布防时点无法拦下：布防时价格距 L1 仅 0.3 点（尚未突破），布防后价格先**跌破 L1 达 0.8 点以上**，
再**回抽触碰 L1** 触发 `LTE` ⇒ 若不复检，仍会开出「破位回抽」的 Bull Put。

| 用例（`test_qp_boundary_integrity_gate.TestTriggerSideGate`） | 结果 |
|---|---|
| `resolve_day_extremes_spy_for_gate` 返回破位极值 `(756.34, 760.13, …)` | **`open_trade` 未被调用**；落 `SKIPPED_GUARD`（`detail.reason` 含 `Boundary integrity gate`、`detail.boundary_integrity.level='L1'`）；**pending 条件单保留**（不消费，可复核后人工处置） |
| 返回未破位极值 `(771.00, 774.00, …)` | 照常 `open_trade`，pending 正常消费 |
| 返回 `(None, None, 'missing')` | fail-open 照常开仓（幅度类判据缺数不停摆） |

**真实链路冒烟（本机实跑，只读 DB）**：

```python
OptionSellerManager.resolve_day_extremes_spy_for_gate(757.63)
# -> (756.5877, 760.3778, 'es_snapshot_pct_derived')      ← 当日 ES 快照（7687.00 / 7643.50，波幅 0.57%）折算
OptionSellerEngine.check_qp_boundary_integrity('L1', 'BULLISH', {'l1': 757.82, ...}, session_extremes=ext)
# -> (False, 'Boundary integrity gate (L1 long) failed: session low 756.59 is 1.23 pts below L1=757.82 …')
```

## 3. 测试与回归

| 套件 | 结果 |
|---|---|
| **`test_qp_boundary_integrity_gate.py`（新增）** | **28/28 通过** —— 极值解析 5（真实案例折算 756.34/760.13、直给 SPY 优先、`range_pts` 退路标记、缺数据、**非有限值 `inf/nan` 视为缺数据**）/ 纯函数 10（含等号边界 0.8、内侧放行 0.79、反向对称、**逐档位独立**（跌破 L1 不连带拦 L2）、SPX 档位 8.0 点、极值缺数据 fail-open、档位值缺失 fail-open、**档位值 `nan` 按缺失处理**、非档位 N/A）/ 引擎 6（QUALIFIED 拦、ARMED 拦、H1 反向拦、双向放行对照、缺数据 fail-open）/ 探针 4 / 触发侧 3 |
| `test_qp_prev_close_gate.py`（前置③） | **21/21 通过**（夹具波幅 0.60%→0.30%，原因见 §5） |
| `test_conditional_order_trigger_3131.py` | **9/9 通过**（夹具 patch 极值解析为固定「未突破」值，单元测试不读实时 DB） |
| `test_intraday_probe.py` | OK |
| `test_qp_meta_parse.py` | OK |
| `test_strike_anchor_3131.py` | OK |
| `test_force_dry_degrade.py` | OK |
| `test_min_open_credit_dte_fallback.py` | OK |
| `test_balanced_day_prev_close_gate.py`（模块 57） | OK |
| `test_l1_h1_breakeven_stop.py` | OK（中文成功流断言） |
| `test_journal_filter_catalog / group_key / mode_filter / tv_export_scopes` | 全部 OK |
| `test_quant_pivot_option_seller.py` | 4/4 通过（需以 `PyTools` 为工作目录 + 项目根入 `sys.path`） |
| `test_live_resting_limit_order.py` | **1 项失败 —— 经基线复跑确认「既有失败」**：`git stash push -u` 回退本次全部改动后该用例**仍然失败**（`_evaluate_active_positions` 内 `get_order_status('ENT9')`），与本模块代码路径完全不相交（本模块改动只落在 `_evaluate_conditional_orders` 与引擎判定层） |
| `py_compile`（engine / manager / probe） | 通过 |

## 4. 规则归档（规则 11）

| 文件 | 改动 |
|---|---|
| `gemini_answer-trading_system_rules_manual-…html` | `§3.1.3.1 开仓规则` 前置规则表新增 **④ 边界有效性前置（未被有效突破 · 逐档位 H1/H2/L1/L2）**：规则（双向）、逐档位独立、阈值口径与含等号、单调熔断、**数据来源与绝对点位铁律**、缺数据 fail-open、执行位置（布防 + 触发双点）、机制归属、**事故依据（2026-09-15 流水 #27）**；收口句更新为「实际准入 = 触发点位与容差带 + 前置规则（波幅/位置 + 三维准入 + 昨收方向 + 边界有效性）」 |
| `gemini_answer-trading_system_rules_manual-…md` | 同名 ④ 行 + 同一收口句；并登记 §4.1 的百分比折算口径与「绝对点位不得 ÷10」铁律 |
| 手册备份（改动前） | `…html.bbt-bak-20260915_191033`、`…md.bak-20260915_191033` |
| HTML 结构校验 | 相对基线：`<div>` +2 / `</div>` +2、`<ul>` +1 / `</ul>` +1、`<li>` +8 / `</li>` +8 —— **全部闭合**（`<p>` 的 157/156 不配平为基线既有状态，非本次引入） |

## 5. 两处夹具调整（据实登记，均为「测试隔离」而非口径放松）

1. **`test_qp_prev_close_gate.py`**：原夹具 `rth_range_pct = 0.60%`、`pts = 40.0` 在 `Pos=75%/25%` 下隐含
   「当日最高已高出 H1/H2、最低已低于 L2 逾 0.8 点」⇒ 四个「放行对照 / 豁免对照」用例被**前置④ 独立拦截**，
   从而掩盖该文件真正要测的前置③。夹具波幅收至 `0.30% / 24.0` 后 **21/21 通过**，前置③ 的判据与豁免语义未被削弱。
2. **`test_conditional_order_trigger_3131.py`**：触发侧新增复检会读取**实时 DB 快照**，会使断言随当日行情抖动；
   夹具内 patch `resolve_day_extremes_spy_for_gate` 为固定「未突破」极值 `(771.0, 774.0, 'test_fixture')`，
   保证单元测试与实时数据解耦（「有效突破 ⇒ 拦截」由新套件覆盖）。

## 6. 已知限制与待确认项（诚实登记）

1. **缺数据语义 = fail-open**（放行 + `data_missing=True` 留痕）。理由：本项是**幅度类**判据，缺极值时前置① 波幅/位置与容差带仍在把关；
   若要求「无法验证一律拦截」（与前置③ 昨收方向同口径的 fail-closed），改动为一行（`data_missing` 分支返回 `False`），需用户确认。
2. **ES↔SPY 基差异常（既有数据问题，模块 57 亦已登记）**：2026-09-15 实测算得 ES 对 SPY 的基差 ≈ **0.9%（约 70 ES 点）**，
   与 SPX 现价（`spx_spot`）口径相差更大 —— 本模块因此**明确禁止**用绝对 ES 点位换算 SPY 点位；
   但该基差本身是否正常（合约月份 / 数据源）建议另行复核。
3. **单调熔断偏严（设计选择）**：一旦某档位当日被有效突破，该档位当日**后续一律禁止反向开仓**，
   不区分现价从哪一侧接近（用户口径以「当日最低点/最高点」定义，本实现严格照此；若要求「仅禁止从突破侧回抽」需引入路径状态机）。
4. **L2 / H2 是否应同样受限（超出用户字面口径的推广，待确认）**：用户原文只点名 L1 与「反方向最对称处理」（⇒ H1）；
   本实现按「逐档位独立」把同一规则施加到 L2 / H2（跌破 L1 不连带拦 L2；L2 自身被跌破 0.8 点才拦 L2）。
   若用户希望**仅约束 L1 / H1**（与前置③ 的 H2/L2 豁免口径对齐），改动为纯函数内 4 行白名单。
5. **触发侧快照口径**：触发侧读「当日 ES `order_flow_signals` 最新一行（回溯 ≤ 24 行 / ≈2 小时）中极值与 `price_position_pct` 齐备者」，
   若整段回溯窗口都没有合格行 ⇒ `missing` ⇒ fail-open。该表由 5 分钟哨兵持续写入（实测 09-15 当日 12:55 之后的行缺 `price_position_pct`，回溯机制已生效并取到 11:10 之后的行）。
6. **`nan` 防御（本次顺带加固）**：QuantPivot 取数异常会产出 `nan`（实测：只读探针 `intraday_probe` 跑 2026-09-15 时输入契约 `qp` 的 `open/h1/h2/l1/l2` **全为 `nan`**，**基线（`git stash` 回退本次改动后）复跑结果完全相同 ⇒ 既有数据/探针问题，非本次引入**）。
   本模块判据对 `nan / inf` 一律按「值缺失」处理（`math.isfinite` 守卫 + 单测覆盖）⇒ 该情形下 **fail-open + `data_missing=True`**，
   绝不出现「`nan` 参与比较导致静默放行或误拦」。**建议另行排查**：探针对历史日期的 QuantPivot 取数为何产出 `nan`（会连带使「容差带 / 布防」等既有判据行也显示 `nan`）。
7. **未做历史回测**：本项为硬约束，历史成交样本中若期望统计「本项拦下了多少笔」，可用只读回填脚本
   （`backfill_option_seller_simulated_trades.py` 的 `of_eval_metrics` 目前不含 `rth_range_pct`，如需回测需补该字段）。

## 7. 回滚

```bash
# 代码（PyTools 是独立 git 仓库）
cd ~/Documents/Workplace/PycharmProjects/BBTrading/PyTools
git checkout -- option_seller/option_seller_engine.py \
                option_seller/option_seller_manager.py \
                option_seller/intraday_probe.py \
                option_seller/test_conditional_order_trigger_3131.py \
                option_seller/test_qp_prev_close_gate.py
rm -f option_seller/test_qp_boundary_integrity_gate.py

# 规则手册（改动前快照）
cd ~/.gemini/cli-workspace/gemini-answers/system_modules
cp gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html.bbt-bak-20260915_191033 \
   gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html
cp gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md.bak-20260915_191033 \
   gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md
```
