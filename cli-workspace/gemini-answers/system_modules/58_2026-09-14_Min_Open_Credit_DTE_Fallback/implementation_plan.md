# 开仓权利金硬下限（$0.10）+ 0DTE→1DTE 自动回退 —— 实施计划

- **日期**：2026-09-14
- **模块**：58 `Min_Open_Credit_DTE_Fallback`（期权卖家系统 · 结构选型层规则）
- **技术栈**：Python 3.11 / MySQL `bb_trade` / Flask（bbt_data_web 127.0.0.1:5005）/ Schwab 期权链 / Jinja2 + 原生 JS / 浅色主题
- **触发**：用户在流水账本发现一单 **净权利金 $0.04** 的 0DTE 价差

---

## 1. 需求（用户原话拆解）

> 「不管开仓策略是哪个，所有开仓 **权利金不能小于 0.1**；如果到 RTH 后期 0DTE 很便宜、不能满足，
> **自动查找同样开仓策略的 1DTE**；**手动开仓也要阻止** 小于 0.1，**并提示**，且**自动查找推荐 1DTE**。」

拆成四条可验收需求：

| # | 需求 | 验收口径 |
|---|---|---|
| R1 | 全局最低开仓权利金 **$0.10** | 任意 profile / 任意路径，净权利金 < $0.10 ⇒ 拒绝开仓 |
| R2 | 0DTE 不足 ⇒ 自动改搜**同策略 1DTE** | 0DTE 无 ≥ $0.10 候选时返回 1DTE 候选，且**参数完全相同** |
| R3 | 手动路径**阻止 + 提示 + 自动推荐 1DTE** | 前端提示条 + 后端 `rejected_low_credit` + `dte1_candidate` 可一键采用 |
| R4 | 通用性（规则 6） | 看多 / 看空同一套规则；不针对某一天特例化 |

## 2. 现状调研（改动前的四条路径 + 闸门）

| 路径 | 选单调用 | 改动前的 min_credit |
|---|---|---|
| 自动机制族（`_open_from_engine`，全部 `_mech_*`） | `find_optimal_spread(target_dte=0)` | profile 默认（0.03 / 0.05 / 0.12） |
| 平衡日边界（`evaluate_balanced_day_channel`） | 同上 | profile 默认 |
| 盘前大单回调（`evaluate_pm_big_trade_ema_pullback_trade`） | 同上 | profile 默认 |
| 自动条件单（`_evaluate_conditional_orders`） | 同上（`target_dte=order['dte']`） | `profile` 或 `min(0.05, profile)` |
| **手动扫描（`/api/option_seller/scan_now`）** | Option A/B 两次调用 | A = profile；**B = `min(0.04, profile×0.8)` ⇒ $0.04** ⚠️ |
| **最终开仓（`OptionSellerManager.open_trade`）** | — | **无任何权利金下限** ⚠️ |

**事故根因**：手动扫描「💰 降低权利金 (CREDIT)」降级把下限硬编码放宽到 `min(0.04, profile×0.8)`，
且 `candidate = cand_cushion or cand_credit` ⇒ 选项 A 找不到时**自动落到 $0.04**；
`open_trade()` 不做复核 ⇒ $0.04 直接成交。
（事故单：SPY 765/767 BEAR_CALL_SPREAD，宽 $2.00 ⇒ 最大盈利 $4 / 最大亏损 $196，**风险回报比 1:49**。）

**链数据调研**：Schwab 链 `callExpDateMap` / `putExpDateMap` 的 key 为 `'<date>:<dte>'`，
SPY 日频到期同时含 0DTE / 1DTE ⇒ 同一份 `chain_data` 即可完成回退检索（无需二次取链）。

## 3. 方案设计（四层，尽量少改动点）

1. **引擎硬下限（覆盖全部调用方）**：`option_seller_engine.MIN_OPEN_CREDIT = 0.10`；
   `find_optimal_spread` 内 `use_credit = max(use_credit, MIN_OPEN_CREDIT)`。
   —— 一处改动让 profile 默认值与手动降级值**同时**被抬到 ≥ $0.10。
2. **到期回退助手**：新增 `find_optimal_spread_with_dte_fallback(...)`：
   先按 `target_dte` 找 → 找不到则用**同一套 kwargs** 改试 `dte_fallback`（缺省 1）；
   返回候选附加 `dte_fallback` / `dte_fallback_from`。
3. **单一 choke point**：`OptionSellerManager.open_trade()` 在算 `net_credit` 后复核
   `< MIN_OPEN_CREDIT ⇒ return None`（所有路径的兜底 + 审计日志）。
4. **手动路径提示 + 推荐**：`/api/option_seller/scan_now` 增加 0DTE→1DTE 回退检索，
   并在 execute 时返回 `rejected_low_credit` + `dte1_candidate`；前端提示条 + 一键采用。

**关键设计取舍**：

- 「全局下限」是**地板不是天花板** ⇒ AGGRESSIVE $0.12 保持更严口径（`max(profile, $0.10)`）。
- 回退**只允许 0DTE → 1DTE**，且**不得放宽其它约束**（delta/宽度/安全垫/锚位照旧）——
  否则「回退」会变成绕过风控的后门。
- 手动路径**不豁免**：手动只是在「机制是否触发」上自由，**不改变可成交候选的准入标准**。

## 4. 改动清单

| 文件 | 改动 |
|---|---|
| `PyTools/option_seller/option_seller_engine.py` | `MIN_OPEN_CREDIT` / `DEFAULT_DTE_FALLBACK` 常量；`find_optimal_spread` 抬升下限；新增 `find_optimal_spread_with_dte_fallback` |
| `PyTools/option_seller/option_seller_manager.py` | `open_trade` 权利金复核；4 个调用点改走回退助手；`entry_evidence` 增 `entry_dte` / `dte_fallback` / `dte_fallback_from` |
| `bbt_data_web/data_app/bbt_option_seller.py` | 手动扫描：`_scan_variants(dte)` + 0DTE→1DTE 回退；execute 增 `rejected_low_credit` 闸门；响应增 `min_open_credit` / `dte_fallback` / `dte1_candidate` |
| `bbt_data_web/templates/bbt_option_seller.html` | `MIN_OPEN_CREDIT_UI` 镜像 + `#manualCreditNotice` 提示条 + `adoptManualDte1Candidate()`；执行前拦截 + 服务端拒绝处理 |
| `PyTools/option_seller/test_min_open_credit_dte_fallback.py` | 新增 12 项契约测试 |
| `PyTools/option_seller/test_qp_meta_parse.py` | 静态时序断言兼容新调用名（时序不变量不变） |

## 5. 测试计划

- **单元**：全局地板（profile 默认 / 显式低值 / 边界 $0.10）/ 地板非天花板（AGGRESSIVE $0.12）/ DTE 回退（触发 / 不触发 / 禁用 / 1DTE 也不足）/ `open_trade` choke point（$0.04 拒、$0.10 收）。
- **回归**：`PyTools/option_seller/` 全量测试套件。
- **端到端**：真实链 调 `scan_now`（`execute:false`）验证 `min_open_credit` 与候选 ≥ $0.10；
  同链开关地板对比，证明旧口径会选 $0.04、新口径选 $0.10。

## 6. 风险与回滚

| 风险 | 缓解 |
|---|---|
| 全局抬高下限 ⇒ 合法机会减少 | 这是**规则意图**；0DTE 不足时 1DTE 回退补回机会；日志可审计 |
| 回退改变到期口径 ⇒ 隔夜风险 | 仅 0DTE→1DTE；`entry_evidence.dte` 与实际到期如实落库，页面/账本可见 |
| 前端缓存旧 JS | 页面改动需硬刷新（`/bbt_option_seller` 已带 `Cache-Control:no-store`） |
| 回滚 | 见 walkthrough「回滚」节（引擎常量置 0 / 还原 3 个调用名 / 删页面提示） |

## 7. 验收标准

1. 净权利金 < $0.10 的任何路径（含手动）**无法开仓**，且拒绝有日志。
2. 0DTE 无 ≥ $0.10 候选时返回 **1DTE 同策略**候选，`dte_fallback=True`。
3. 手动路径被阻止时页面**有提示**且**一键可采用 1DTE 推荐**。
4. 新增 12 项测试全绿；既有套件无新增失败。
5. 决策规则已按规则 (11) 写入交易规则手册 §3.4。
