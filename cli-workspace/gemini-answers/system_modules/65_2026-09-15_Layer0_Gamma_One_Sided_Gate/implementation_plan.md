# L0-F⑨「SPX Gamma 单边结构方向掩码」—— 实施计划

- **日期**：2026-09-15
- **模块**：65 `Layer0_Gamma_One_Sided_Gate`（归属能力域：**Option Seller 自动交易系统 · 第 0 层统一门槛**）
- **触发事件**：2026-09-15 06:52:04 流水 #5 `BULL_PUT_SPREAD`（`SPY0915P-756+754`，开仓金 $0.14 / 平仓 $0.33 / **实现盈亏 −$19.00** / `CLOSED_TIME_STOP`）—— 开仓时 SPX Gamma 结构明显偏空。
- **用户口径（本轮，原文）**：
  1. 「当 spx gamma 明显偏向一侧时，所有自动单触发机制不能触发反向单」⇒ 新增第 0 层闸门；
  2. Q1 判据 = **树方向评级 ∪ 墙体深度比 ≥ 2.5（含墙位侧校验）**，粘滞窗口 **K = 3 条 5m 读数**；
  3. Q2 范围 = **全部自动机制 ①–⑥ + 自动条件单触发侧**；
  4. Q3 手动边界 = **自动单 + UI 扫描单（`MANUAL_UI_SCAN`）硬拦截；纯手工单仅红色警示**（保留「逆势覆盖」留痕通道）；
  5. Q4 上线 = **直接启用**（无影子期）；
  6. 「如果不是绝对必要 不要让我确认」⇒ 实现阶段不再中断确认。
- **技术栈**：Python 3.11 · `PyTools/option_seller/`（`auto_mechanisms` 编排层 + `option_seller_manager` 执行层 + 探针）· `PyTools/order_flow_analysis/order_flow_sentinel.py` 装配层 · Flask（`bbt_data_web`）· unittest 契约测试 · 规则手册 HTML/MD 双写

---

## 1. 事故复核（先钉事实，再设计判据）

DB `spx_gamma_signals`（5m）2026-09-15 早盘原始读数：

| 时间 | SPX | 零 Gamma | 集群比 | Call Wall γ | Put Wall γ | 墙深比(空/多) | 树判定 |
|---|---|---|---|---|---|---|---|
| 06:45 | 7611.0 | 7622.5 | 0.97 | +1.20B | −2.01B | 1.67 | Neutral:Balanced |
| **06:49** | **7605.8** | **7607.5** | **0.68** | **+1.04B** | **−2.86B** | **2.76** | **Bearish_L1:Bearish** |
| 06:52 | 7608.6 | 7607.5 | 1.12 | +1.71B | −2.76B | 1.61 | Neutral:Balanced |
| 06:54 | 7608.1 | 7607.5 | 0.86 | +1.25B | −2.93B | 2.35 | Bearish_L1:Bearish |
| 06:59 | 7607.6 | 7607.5 | 0.84 | +1.30B | −3.26B | 2.52 | Bearish_L2:Bearish |

两条关键发现：
1. 树判定在 **06:49 已是 `Bearish_L1`**（用户截图即该条读数）⇒ 06:52 卖 Put 属**逆势单**；
2. **单条读数 3 分钟内翻面**（06:49 → 06:52 `Neutral:Balanced`）⇒ 只看「当前一条」的闸门会在 06:52 **漏放**，**粘滞窗口是必要条件而非增强项**。

## 2. 设计（三个决策点 + 一个接线缺口）

**① 判据：树方向 ∪ 墙体深度比（最新侧优先）**
- 偏向多头：树前缀 `Bullish` **或**（`|CallWallγ| / |PutWallγ| ≥ 2.5` 且 Call Wall 在现价上方）；
- 偏向空头：树前缀 `Bearish` **或**（`|PutWallγ| / `CallWallγ`| ≥ 2.5` 且 Put Wall 在现价下方）；
- `Neutral:*` 与旧 `Neutral-Bullish/Bearish:*` **一律不判**（其「禁令方向」与「柱色支配方向」自相矛盾，不替树做方向推断）；
- 掩码侧 = 偏向的**反向**（偏多 ⇒ 禁卖 Call / 掩码 BEARISH；偏空 ⇒ 禁卖 Put / 掩码 BULLISH）。

**② 粘滞：窗口 K=3，最新非中性读数优先**
- 中性读数**不解锁、不覆盖**；只有出现**对侧**单边读数才反转 ⇒ 单调、**每周期最多掩码一个方向**（无「双向同时掩码」死锁态；此点经 2026-09-11 实测校正——并集口径会导致 4 个极值点中 3 个双向掩码）。

**③ 数据纪律：fail-open**
- 缺数 / 最新读数陈旧 > 15 分钟 / 判定异常 ⇒ **不掩码**（写 `data_missing|stale` 留痕），可开关切换 fail-closed；与 L0-C 的「结构类判据不误伤」同哲学。

**④ 接线缺口（关键，必须同批修复）**
- 机制③「平衡日边界」**原先完全不消费 `masked_directions`**（方向在评分器内部 `bd['_direction']` 定案，编排层无法前置拦截）⇒ 掩码对该机制形同虚设；本次样本中 **6 笔逆 Gamma 亏损单（−62）全部出自该机制**。已改为**方向定案后立即施加 L0 掩码**。
- 触发侧（条件单价格触发）与「布防时中性、布防后转单边」的时序场景必须**兜底复校**；跨进程 / 跨日取数用 **DB 直读**（`resolve_l0f_gamma_mask()`，内存掩码以「交易日 + 5 分钟桶」为新鲜度键）。

## 3. 变更清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `PyTools/option_seller/auto_mechanisms.py` | 新增常量（`GAMMA_MASK_WALL_DEPTH_MIN=2.5` / `LOOKBACK_BARS=3` / `MAX_STALE_MIN=15` / `FAIL_OPEN=True`）；纯函数 `gamma_bias_side()`（单条读数偏向）、`gamma_cycle_bucket()`（5 分钟桶）、`spx_gamma_one_sided_mask()`（窗口 + fail-open + 详情）、`_gamma_inputs_brief()`；`check_layer0()` 新增 **L0-F⑨** 闸门（并入 `masked_directions` + `detail.gates`）；`evaluate_auto_entry_cycle()` 下传掩码（`_l0f_masked_directions` / `_l0f_bias` / `_l0f_masked_cycle_key`）并打印掩码日志 |
| 2 | `PyTools/option_seller/option_seller_manager.py` | `resolve_l0f_gamma_mask()`（内存周期掩码 → DB 直读 + 同源判定）；`l0f_gate_decision()` 决策表纯函数；`open_trade()` **choke point**（自动单 / UI 扫描单硬拦、纯手工单豁免、覆盖留痕）；机制③ `_mech_balanced_day_boundary` / `evaluate_balanced_day_channel` 消费掩码；`_evaluate_conditional_orders()` 触发侧兜底复校（`SKIPPED_GUARD` + 不消费）；`_build_mechanism_context` 传入 `gamma_history` |
| 3 | `PyTools/order_flow_analysis/order_flow_sentinel.py` | `gamma_dict` 增补 `call_wall_gamma` / `put_wall_gamma` / `signal_time` / **`history`**（最近 K 条 5m，升序）；**当前读数取数口径保持原样**（不限 timeframe 的最近一条）⇒ 机制① Gamma 打分零行为变化 |
| 4 | `PyTools/option_seller/backfill_option_seller_simulated_trades.py` | 回放路径同样装配 5m 粘滞窗口 ⇒ **回放与实盘同口径** |
| 5 | `PyTools/option_seller/intraday_probe.py` | `_load_gamma_row()` 装载 5m 窗口 + 墙位 Gamma；机制③ 判据表新增「L0 方向掩码（L0-B⑤/C⑥/F⑨）」行并计入 verdict |
| 6 | `bbt_data_web/data_app/bbt_option_seller.py` | 手动开仓控制台：`candidate_found` 返回 `gamma_one_sided_warning`（**确认弹窗前可见**）；`execute` 分支新增 `rejected_gamma_one_sided` 硬拦截 + `override_gamma_gate` 覆盖留痕 |
| 7 | `bbt_data_web/templates/bbt_option_seller.html` | 前端：红色预检提示、确认弹窗叠加逆势警告、**二次确认（逆势覆盖）**、`rejected_gamma_one_sided` 分支处理 |
| 8 | `PyTools/option_seller/test_l0_gamma_one_sided_gate.py`（新增） | 契约测试 **31 项**：判据（新旧 format / 中性不判 / 墙侧校验 / 阈值含等号 / 树优先 / 脏数据）、窗口（**事故点 06:52 回归** / 无窗口对照 / 镜像 / 最新侧优先 / 不得双向 / 陈旧 / 缺数 / fail-closed 开关 / 窗口长度）、接线（闸门读数 / 不终止周期 / 掩码下传 / 全掩码跳过）、机制③ 消费掩码（链前拦截 vs 放行对照）、choke point 决策表与端到端（自动单 / UI 扫描单 / 反向放行 / 跨周期转 DB）、触发侧兜底（拦截且不消费 / 放行触发） |
| 9 | `PyTools/option_seller/test_intraday_probe.py` | 闸门清单断言补 `L0-F⑨`；`test_l0_mask_row_reflects_own_side` 由「数据依赖断言」改为「逐点不变式 + L0-F 每周期最多一侧」 |
| 10 | `scratch/validate_l0f_gamma_gate.py`（新增） | 历史回放校验脚本（真实实现复算 1068 周期 + 105 笔流水 + 事故点） |
| 11 | 规则手册（`.html` + `.md`） | §3.1.1.1：L0 表新增 **L0-F** 行 + 完整明细块（判据 / 粘滞 / 数据纪律 / 常量 / 三处执行点 / 适用范围 / 回放标定 / 接线缺口）；§3.1 概览 bullet 补 L0-F；§2.4 决策树末尾新增「↳ 决策树下游消费者（卖方侧）」交叉引用 |

## 4. 验收标准

1. `test_l0_gamma_one_sided_gate.py` 31/31 通过；
2. `test_intraday_probe.py` / `test_qp_boundary_integrity_gate.py` / `test_conditional_order_trigger_3131.py` / `test_balanced_day_boundary_integrity_gate.py` / `test_balanced_day_prev_close_gate.py` / `test_force_dry_degrade.py` 全绿（`test_live_resting_limit_order.py` 的 1 项失败为**改动前既有**，已用基线文件对照确认）；
3. 历史回放：**双向死锁 = 0**；事故点 `06:50` / `06:55` 两个周期**均掩码 BULLISH**；
4. 规则手册 `.html` / `.md` 双写一致，`bbt_trading_modules.html` 演进行同步；
5. 回滚：常量开关（`GAMMA_MASK_FAIL_OPEN` / 阈值）或 `auto_mechanisms.py` 内 L0-F 调用点移除；判定与执行分离，回滚不改语义。

## 5. 取舍说明（供后续复议）

- **为何不把 `Compression-*` / `Exhaustion-*` 计入偏向**：树在这两态内部「禁令方向」与「柱色支配方向」冲突（`Exhaustion-Top` 绿柱支配却严禁卖 Put），强行取舍会把一种规则语义覆盖另一种；当前口径保留树的权威语义，只消费**无歧义**的两种证据。
- **为何不采用「并集」粘滞**：并集会产生双向同时掩码（2026-09-11 实测 3/4 极值点全掩码）⇒ 等价本周期不交易，过度阻断且不可解释；「最新非中性优先」在同等保护下把死锁率压到 0。
- **77.6% 周期会有单侧掩码**：这是把「gamma 单边 ⇒ 不逆势」落到实处的必然覆盖面；被掩码的只是**一侧**，顺势侧与墙位/边界机制照常可用（实测自动机制被拦 12/36 笔，净避免亏损 $48）。
