# 平衡日边界机制 v2 实施计划（趋势日门控 + 评分器 v2 + 命名统一）

- **日期**：2026-09-13
- **模块**：Option Seller 触发层机制 ③「平衡日边界」（`AUTO_BALANCED_DAY_BOUNDARY`）
- **归档目录**：`47_2026-09-13_Balanced_Day_V2_Trend_Gate_And_Scorer`
- **技术栈**：Python 3.11 / MySQL `bb_trade`（`order_flow_signals`、`smashelito_analysis`）/ yfinance SPY 1 分钟 / Flask API + Jinja2（`bbt_data_web`）/ 规则手册五部分级

---

## 1. 背景与问题

机制 ③ 的口径与代码长期脱节，本轮由数据回放（12 交易日）定位出四类问题：

1. **趋势日判据错误**：旧口径 `is_trend_up = (last_px − open_px) ≥ 0.6 × 实时振幅` 判别方向为反——被它标为「非趋势日」的信号假信号率 **19%**，标为「趋势日」的仅 **6%**；且 12/12 天都被标过趋势日（行占比 12–90%）。根因是「运行振幅」为自我参照量。
2. **机制实际没有趋势门控**：系统存在全局统一 SPY 趋势引擎（`quantdata.trend_regime.evaluate_intraday_trend_regime`，被 `spx_gamma_analyst` / `ai_tape_analyst` / `order_flow_rules_optimizer` 使用），但 `order_flow_sentinel.py:852` 调用 `evaluate_5m_synthesis_trade(...)` 时未传 `is_trend_day_bullish/bearish` ⇒ `MechanismContext` 两字段恒为 `False`。
3. **评分器维度冗余与反向**：v1 的 A(35) 与 C(20) 在 188 个「已出方向」样本上**完全共线**（`A>0 ⇔ C 到达`，零例外）；D(真空) 命中时假信号 **31%** vs 未命中 5%。
4. **组数映射与数据相反**：85+ ⇒ 2 组 的分档假信号 **15%**、净 **−0.2**；70–84 档 6%、净 **+5.2**。

## 2. 实施目标

| 目标 | 交付 |
|---|---|
| 趋势日判据换成全局 SPY 引擎并施加**方向匹配否决** | 引擎新增可选 `window_end`；机制侧新增门控三档 + fail-closed |
| 评分器 v2：消除共线、删除负向维、组数与数据一致 | `score_balanced_day_boundary_v2`（P45/M20/B25/E10，D 停用，一律 1 组） |
| v1 可回退、可对照 | v1 函数与配置零改动 + `evidence.v1_shadow` + `scorer_version` 开关 |
| 命名统一（`move_end` 概念已删除） | 机制 ③ 全线 `balanced_day`，旧名保留为显式兼容薄壳 |
| 文档与代码一致 | 手册 §3.1.4.1 具体化、§3.1.4.4.5 证据节、机器校验脚本 |

## 3. 关键设计与参数

### 3.1 趋势日门控（新增）

- 引擎：`evaluate_intraday_trend_regime(target_ts, window_end=(11, 30))`（SPY 1 分钟；四条件：脱离全日极值 ≥1.00 点、开盘后回撤 ≤2.00 点、极值回撤 ≤2.00 点、5m 收盘逆 15m EMA13 ≤1 次）
- 机制侧只取**布尔结论**（不搬 SPY 点阈值，避免 ES/SPY 混比）
- 档位：`veto_opposing`（缺省，逆向趋势 ⇒ 否决）/ `require_range`（任意趋势日 ⇒ 否决）/ `off`
- 失效保护：引擎无结论（取数失败 / 越窗口）⇒ `trend_gate_fail_closed=true` **否决不放行**
- 窗口对齐：机制窗口 06:35–11:30，引擎原定义域 06:30–11:00 ⇒ 以 `window_end=11:30` 对齐

### 3.2 评分器 v2

| 维度 | 权重 | 变化 |
|---|---|---|
| **P 边界到位度** | 45 | 连续：`P = 45 × max(0, 1 − d/(1.5×boundary_tol))`，`d=0⇒45`、`d≥6.0⇒0`（取代 A的贴边前提 + C 的二值 20/10） |
| **M 动能衰竭** | 20 | 原 A 的信息性子项 ×(20/35)；按 P 更近一侧定向 |
| **B 吸收与反制挂单** | 25 | 算术不变 |
| **E 时间 / 幅度** | 10 | 算术不变 |
| **D 真空 / 流动性** | 0（停用） | 仍计算、记 `D_shadow_pts`；`d_enabled=true` 可回开 |

- 方向准入 45 分（P 到位即达）；**出分门槛 70**（= 到达边界 + M/B/E ≥25 分佐证）
- **组数一律 1 组**（`groups_cap=1`）；取消「≥85 ⇒ 2 组」
- 边界确认收紧：v1 允许 `C_half` 半接近 ⇒ v2 要求**信号侧到达**（≤ `boundary_tol` 4.0 点，ES 口径）

### 3.3 命名统一

`balanced_day_data.py`（`load_balanced_day_context`）、`balanced_day_shadow.py`（`--scorer v2/v1`）、`BALANCED_DAY_CFG` / `BALANCED_DAY_DEFAULTS`、`load/save/get/set_balanced_day_config`、`self.balanced_day_config`、`evaluate_balanced_day_channel`、`/api/option_seller/balanced_day_config`；旧名薄壳（`move_end_data.py` / `move_end_shadow.py` / `move_end_evaluator.py`）与旧别名保留。

### 3.4 配置（`Config/option_seller_balanced_day.json`）

```json
{"enabled": true, "scorer_version": "v2", "score_threshold": 70, "boundary_tol": 4.0,
 "groups_cap": 1, "d_enabled": false, "trend_gate": "veto_opposing",
 "trend_gate_fail_closed": true, "trend_window_end": "11:30",
 "path_r_enabled": true, "path_t_enabled": true, "require_boundary_confirm": true}
```

## 4. 验证方案

1. **趋势判据判别力对比**（旧口径 vs SPY 引擎；分组看假信号率/净收益）
2. **v1 有效性审计**（分档校准、逐维命中与留一消融 LOO）
3. **v2 标定网格**（门槛 45–80 × 门控三档 ⇒ 次/日、假信号率、净）
4. **文档↔代码机器校验**（35 项断言 + 4 组数据复刻）

## 5. 风险与回退

- **fail-closed 依赖 yfinance SPY 1 分钟**：取数失败 ⇒ 不出信号（漏做而非逆势）；周末/节假日必然无结论。临时放宽：`trend_gate_fail_closed=false`（不建议，放行组假信号 19%）。
- **样本小**：49–92 次命中、2–8 个假信号；4% 的 95%CI 为 1–14%。
- 全部改动**无需改代码即可回退**：`scorer_version=v1`、`trend_gate=off`、`d_enabled=true`、`groups_cap=2`。
