# L0-F⑨「SPX Gamma 单边结构方向掩码」—— 验收报告 (Walkthrough)

- **日期**：2026-09-15
- **模块**：65 `Layer0_Gamma_One_Sided_Gate`（归属能力域：**Option Seller 自动交易系统 · 第 0 层统一门槛**）
- **对应计划**：`implementation_plan.md`（同目录）
- **状态**：✅ 全部实现并验证通过（用户口径 Q4 = 直接启用，**无影子期**）
- **影响面**：期权卖家自动开仓链路（布防侧 / 触发侧 / choke point）+ 手动开仓控制台 + 探针 + 规则手册

---

## 1. 交付物清单（代码）

| 文件 | 交付内容 |
|---|---|
| `PyTools/option_seller/auto_mechanisms.py` | L0-F⑨ 判定与编排接线：`gamma_bias_side()` / `gamma_cycle_bucket()` / `spx_gamma_one_sided_mask()` / `_gamma_inputs_brief()` + 4 个常量；`check_layer0()` 第 9 个闸门；`evaluate_auto_entry_cycle()` 掩码下传 |
| `PyTools/option_seller/option_seller_manager.py` | `resolve_l0f_gamma_mask()`（内存 → DB 直读）、`l0f_gate_decision()`（决策表）、`open_trade()` choke point、机制③ 消费掩码、触发侧兜底复校、`gamma_history` 透传 |
| `PyTools/order_flow_analysis/order_flow_sentinel.py` | 实时装配 `gamma_dict.history`（最近 3 条 5m）+ 墙位 Gamma + `signal_time` |
| `PyTools/option_seller/backfill_option_seller_simulated_trades.py` | 回放装配同口径窗口 |
| `PyTools/option_seller/intraday_probe.py` | 探针装载 5m 窗口；机制③ 判据表新增 L0 掩码行并计入 verdict |
| `bbt_data_web/data_app/bbt_option_seller.py` | 手动控制台：预检返回 `gamma_one_sided_warning`；执行分支 `rejected_gamma_one_sided` + `override_gamma_gate` 留痕 |
| `bbt_data_web/templates/bbt_option_seller.html` | 红色预检提示 + 确认弹窗逆势警告 + 逆势覆盖二次确认 + 拦截分支处理 |
| `PyTools/option_seller/test_l0_gamma_one_sided_gate.py` | **新增契约测试 31 项** |
| `PyTools/option_seller/test_intraday_probe.py` | 闸门清单断言 + 掩码行不变式 |
| `scratch/validate_l0f_gamma_gate.py` | 历史回放校验脚本（只读） |

## 2. 判定语义（最终口径）

```
每条 5m 读数 → gamma_bias_side(rec)：
   树前缀 Bullish            → BULLISH
   树前缀 Bearish            → BEARISH
   否则 |PutWallγ|/|CallWallγ| >= 2.5 且 PutWall <= 现价   → BEARISH
   否则 |CallWallγ|/|PutWallγ| >= 2.5 且 CallWall >= 现价  → BULLISH
   其余（含全部 Neutral:*） → None（不判）

周期掩码 = 最近 3 条 5m 读数中「最新一条非中性读数」的反向
   BULLISH 偏向 → 掩码 BEARISH（禁卖 Call）｜BEARISH 偏向 → 掩码 BULLISH（禁卖 Put）
   每周期最多掩码一个方向；缺数/陈旧>15min/异常 → 不掩码（fail-open，留痕）
```

**执行点（三处，缺一即漏网）**：① 布防侧（`check_layer0` → 下发全部机制）② 触发侧（`_evaluate_conditional_orders` 复校，不消费条件单）③ `open_trade()` choke point（决策表）。
**适用范围**：自动机制单 ①–⑥ + 自动条件单触发 + **UI 扫描单** = 硬拦截；**纯手工单** = 红色警示 + 可「逆势覆盖」（二次确认 + `gamma_gate_override` 留痕）。

## 3. 验证证据

### 3.1 契约测试（全部通过）

| 套件 | 结果 |
|---|---|
| `test_l0_gamma_one_sided_gate.py`（新增） | **31 / 31 OK** |
| `test_intraday_probe.py` | 34 / 34 OK |
| `test_qp_boundary_integrity_gate.py` | 29 / 29 OK |
| `test_conditional_order_trigger_3131.py` | 9 / 9 OK |
| `test_balanced_day_boundary_integrity_gate.py` | 25 / 25 OK |
| `test_balanced_day_prev_close_gate.py` | 24 / 24 OK |
| `test_force_dry_degrade.py` | 18 / 18 OK |
| `test_live_resting_limit_order.py` | 13 / 14 —— **1 项失败为改动前既有**（已用改动前基线文件回放确认同项失败，与本轮无关） |

关键回归用例（锁定事故）：
- `test_incident_0652_current_neutral_still_masked`：06:52 单条读数已翻回 `Neutral:Balanced`，但 15 分钟窗口含 06:49 `Bearish_L1` ⇒ **仍掩码 BULLISH** ✅
- `test_current_only_neutral_is_not_masked`：对照证明「无窗口 ⇒ 06:52 判不出来」⇒ 粘滞窗口是必要条件 ✅
- `test_never_masks_both_sides` / `test_latest_non_neutral_reading_wins`：任意窗口组合最多掩码一侧 ✅
- `test_masked_direction_blocks_trigger_and_keeps_order`：触发侧拦截并落 `SKIPPED_GUARD` 且**不消费**条件单 ✅
- `test_masked_direction_is_blocked_before_chain`：机制③ 在**取期权链之前**被拦（验证接线缺口已修复）✅

### 3.2 历史回放校验（`scratch/validate_l0f_gamma_gate.py`，只读、用真实实现复算）

```
交易窗口内 5m 周期总数 : 1068
命中方向掩码的周期     : 829 (77.6%)
双向同时掩码（死锁）   : 0          ← 必须为 0
流水影响（105 笔，纸面）:
   AUTO_BALANCED_DAY_BOUNDARY   n=16 拦截=6  被拦PnL= -62   ← 接线缺口修复的直接收益
   AUTO_COUNTER_TREND_BOUNDARY  n=10 拦截=2  被拦PnL=  +6
   AUTO_QUANT_PIVOT_BOUNDARY    n= 6 拦截=2  被拦PnL=  +8
   AUTO_CONDITIONAL_ORDER       n= 2 拦截=2  被拦PnL=   0
   AUTO_5M_SYNTHESIS            n= 2 拦截=0
   → 自动机制合计被拦 12/36，净避免亏损 $48
   MANUAL_UI_SCAN               n=60 拦截=36 被拦PnL= +72   ← 含用户临场人工判断 ⇒ 默认拦截 + 覆盖通道
事故点校验:
   06:50 周期 ⇒ 掩码 ['BULLISH']  bias=BEARISH  ✓ 已拦下 Bull Put
   06:55 周期 ⇒ 掩码 ['BULLISH']  bias=BEARISH  ✓ 已拦下 Bull Put
```

### 3.3 规则手册与归档

- `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`：§3.1.1.1 L0 表新增 **L0-F** 行 + 完整明细块；§3.1 概览 bullet 补 L0-F；**§2.4 决策树末尾新增「↳ 决策树下游消费者（卖方侧）」交叉引用**；
- 同名 `.md` 同步（表格行 + 明细块 + §2.4 交叉引用）；
- 本归档目录 `65_2026-09-15_Layer0_Gamma_One_Sided_Gate/`（plan + walkthrough，md/html 双份）；
- `bbt_trading_modules.html`：Option Seller 模块演进行新增 1 行 + 计数/日期同步。

## 4. 运行与回滚

- **生效方式**：代码已落盘；`bbt_data_web`（5005，debug+reloader）与 5m 哨兵进程**下次启动/热重载即生效**。本次实施期间两个服务**均未运行**（已确认无进程），故无热重载副作用。
- **前端**：模板已改（预检提示 / 二次确认 / 拦截分支）⇒ 浏览器需**硬刷新**。
- **验证入口**：页面 `/bbt_option_seller`「当日自动触发机制检测（探针）」⇒ 逐点 L0 读数含 `L0-F⑨` 行与窗口读数；手动开仓控制台 ⇒ 逆 Gamma 单边结构时红色预警 + 二次确认。
- **回滚**：
  1. 阈值/开关层面：调 `GAMMA_MASK_WALL_DEPTH_MIN`（放宽到很大 ⇒ 等价关闭结构证据）、`GAMMA_MASK_FAIL_OPEN`；
  2. 闸门层面：移除 `auto_mechanisms.check_layer0()` 中 L0-F 调用块（其余接线为纯消费方，无掩码即无行为）；
  3. 文件层面：改动前原始副本在 `/tmp/bbt_backup_20260915_2033/`（7 个文件）。
- **已知取舍（供后续复议）**：77.6% 周期存在单侧掩码（顺势侧不受影响）；`Compression-*` / `Exhaustion-*` 未计入偏向（与树文案语义冲突，需用户另行定夺）；自动单样本仅 36 笔（多为 Force Dry 纸面），统计证据强度有限，需实盘继续累积。

## 5. 后续可选增强（未实施）

1. 把 `Compression-*` / `Exhaustion-*` 纳入偏向判定（需先裁定「以柱色支配侧为准」还是「以树禁令侧为准」）；
2. 「墙位顺手豁免」（价格已在敌对墙容差带内时不掩码）—— 更贴 Gamma 物理，但需新增回归面；
3. 掩码命中率的日度看板（`layer0.l0f` 落库统计）。
