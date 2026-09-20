# 开仓权利金硬下限（$0.10）+ 0DTE→1DTE 自动回退 —— 验收报告

- **日期**：2026-09-14
- **模块**：58 `Min_Open_Credit_DTE_Fallback`
- **归档目录**：`58_2026-09-14_Min_Open_Credit_DTE_Fallback`
- **技术栈**：Python 3.11 / MySQL `bb_trade` / Flask + Jinja2 / Schwab 期权链 / 原生 JS / 浅色主题 / unittest
- **规则归档**：交易规则手册 **§3.4 开仓权利金硬下限与 0DTE→1DTE 到期回退规则**（规则 11）

---

## 1. 结论先行

| 需求 | 结果 |
|---|---|
| R1 全局最低开仓权利金 $0.10 | ✅ 引擎 `find_optimal_spread` 抬升下限（覆盖全部调用方）+ `open_trade` 单一 choke point 复核 |
| R2 0DTE 不足 ⇒ 同策略 1DTE | ✅ `find_optimal_spread_with_dte_fallback`；4 个自动/条件单调用点接入 |
| R3 手动阻止 + 提示 + 推荐 1DTE | ✅ 前端提示条 + 一键采用；后端 `rejected_low_credit` + `dte1_candidate` |
| R4 通用性 | ✅ 看多/看空同一套规则；回退仅 0DTE→1DTE 且不放宽其它约束 |
| 测试 | ✅ 新增 12 项全绿；既有套件无新增失败 |
| 规则手册 | ✅ §3.4（HTML + MD）+ §3.3.1 加全局下限注记 + 侧边目录 |

## 2. 处理逻辑（落地为代码）

### 2.1 全局硬下限（地板，非天花板）

```python
# option_seller_engine.py
MIN_OPEN_CREDIT = 0.10          # 全局最低开仓权利金
DEFAULT_DTE_FALLBACK = 1        # 0DTE → 1DTE

# find_optimal_spread 内：
use_credit = float(min_credit) if min_credit is not None else pcfg['min_credit']
use_credit = max(use_credit, MIN_OPEN_CREDIT)   # ★ 任何调用方都不得低于 $0.10
```

实际生效下限 = `max(profile_min_credit, $0.10)`：
CONSERVATIVE $0.03→**$0.10** · BALANCED $0.05→**$0.10** · AGGRESSIVE $0.12→**$0.12**（保持更严）。

### 2.2 到期回退助手

```python
cand = cls.find_optimal_spread(..., target_dte=target_dte, **kwargs)
if cand is not None:
    cand['dte_fallback'] = False
    return cand
cand2 = cls.find_optimal_spread(..., target_dte=dte_fallback, **kwargs)   # 同一套 kwargs ✓
if cand2 is not None:
    cand2['dte_fallback'] = True
    cand2['dte_fallback_from'] = int(target_dte)
return cand2
```

`find_optimal_spread` 内已强制 `净权利金 ≥ $0.10` ⇒ 0DTE「找不到候选」≡「0DTE 无 ≥ $0.10 候选」。

### 2.3 接入点（全部路径）

| 路径 | 改动 |
|---|---|
| `_open_from_engine`（自动机制族） | `find_optimal_spread_with_dte_fallback(target_dte=0)` |
| `evaluate_balanced_day_channel`（平衡日边界） | 同上 |
| `evaluate_pm_big_trade_ema_pullback_trade`（盘前大单回调） | 同上 |
| `_evaluate_conditional_orders`（自动条件单） | 同上，`dte_fallback=(1 if target_dte==0 else None)` |
| `open_trade`（**全部路径**） | `net_credit < MIN_OPEN_CREDIT ⇒ 拒绝 + 警告日志` |
| `/api/option_seller/scan_now`（手动） | `_scan_variants(dte)` 双档降级 + 0DTE→1DTE 回退 + execute 闸门 |

### 2.4 手动路径（阻止 + 提示 + 推荐）

- **后端**：`execute:true` 且 `net_credit < $0.10` ⇒ `status='rejected_low_credit'`，
  同时用同策略参数扫 1DTE 并回传 `dte1_candidate`；`candidate_found` 响应增
  `min_open_credit` / `dte_fallback` / `dte1_candidate` / `message`。
- **前端**：`MIN_OPEN_CREDIT_UI = 0.10`（同口径镜像）；`#manualCreditNotice` 提示条；
  `executeManualTrade` 先客户端拦截（含「是否切换为 1DTE 候选」确认）；
  服务端拒绝分支同样提示并可 `adoptManualDte1Candidate()` 一键采用。

### 2.5 可观测性

`entry_evidence` 新增 `entry_dte` / `dte_fallback` / `dte_fallback_from` ⇒ 流水账本与复盘可直接筛选
「哪些单是靠 1DTE 回退成交的」。

## 3. 实测证据

### 3.1 同链开关地板对比（真实 Schwab 链 · target_delta=0.02 / width=1.0 / CONSERVATIVE）

| 地板 | 选中结构 | 净权利金 | credit/width | 最大亏损 |
|---|---|---|---|---|
| $0.01（旧口径） | BEAR_CALL_SPREAD **768/769** | **$0.04** | 4.0% | $96.00 |
| **$0.10（新口径）** | BEAR_CALL_SPREAD **766/767** | **$0.10** | **10.0%** | $90.00 |

> 旧口径选中的正是**事故同型**（$0.04 权利金）；新口径把不可接受的薄权利金剔出候选集，
> 引擎自动退到权利金达标的更近行权价。

### 3.2 手动扫描端点（真实链 · `execute:false`）

```
status          : candidate_found
min_open_credit : 0.1            ← 新字段 ✓
dte_fallback    : False          ← 0DTE 有 ≥ $0.10 候选 ⇒ 不回退 ✓
candidate       : BEAR_CALL_SPREAD 765/767 dte=0 credit=0.27 max_loss=173.0
options keys    : ['credit', 'cushion']
```

`target_delta` 从 0.02 扫到 0.06，候选净权利金**恒 ≥ $0.10**（未再出现 < $0.10 的候选）。

### 3.3 单元测试（新增 12 项 · 全绿）

```
Ran 12 tests in 0.065s   OK
```

| 用例 | 断言 |
|---|---|
| `test_constant_is_010_and_raises_looser_profiles` | 常量 = 0.10；CONSERVATIVE/BALANCED < 0.10、AGGRESSIVE ≥ 0.10 |
| `test_profile_default_is_raised_to_floor` | BALANCED 默认口径下 $0.02 的 0DTE **无候选** |
| `test_explicit_low_min_credit_cannot_bypass_floor` | 显式传 0.01 / 0.04 / 0.05 **均被抬升** |
| `test_stricter_profile_keeps_its_own_higher_floor` | ≈$0.11：BALANCED 收、AGGRESSIVE（0.12）拒 |
| `test_credit_at_or_above_floor_is_returned` | ≥ $0.10 正常返回 |
| `test_falls_back_to_1dte_when_0dte_below_floor` | 0DTE 不足 ⇒ 1DTE，`dte_fallback=True`、`dte_fallback_from=0` |
| `test_no_fallback_when_0dte_qualifies` | 0DTE 达标 ⇒ `dte_fallback=False` 且无 `_from` 字段 |
| `test_fallback_disabled_returns_none` | `dte_fallback=None` ⇒ 退化行为 |
| `test_no_fallback_when_1dte_also_below_floor` | 1DTE 也不足 ⇒ **None（不造假）** |
| `test_default_fallback_dte_is_1` | 缺省回退 = 1DTE |
| `test_open_trade_rejects_below_floor` | **复现事故参数 $0.04 / $0.09 ⇒ 均拒绝** |
| `test_open_trade_accepts_at_or_above_floor` | $0.10（含等号）⇒ 接受 |

### 3.4 回归

| 套件 | 结果 |
|---|---|
| `test_strike_anchor_3131.py` | 11 OK |
| `test_qp_prev_close_gate.py` | 21 OK |
| `test_balanced_day_prev_close_gate.py` | 24 OK |
| `test_force_dry_degrade.py` | 18 OK |
| `test_journal_*`（4 个） | 11 / 12 / 9 / 8 OK |
| `test_intraday_probe.py` | 34 OK |
| `test_qp_meta_parse.py` | 20 OK（已兼容新调用名 ✓） |
| `test_l1_h1_breakeven_stop.py` | OK |
| **`test_live_resting_limit_order.py`** | 14 中 1 失败 —— **非本次改动**（`_evaluate_active_positions` 内的 `get_order_status` 调用，本模块未触碰该函数；属既有状态） |

### 3.5 前端

headless Chrome 断言：`MIN_OPEN_CREDIT_UI = 0.1` ✓、`#manualCreditNotice` 存在 ✓、
`adoptManualDte1Candidate` / `setManualCreditNotice` / `executeManualTrade` 均为函数 ✓、
**JS 报错 0 条** ✓。

## 4. 页面 / 接口改动

| 位置 | 改动 |
|---|---|
| `POST /api/option_seller/scan_now` | 响应增 `min_open_credit` / `dte_fallback` / `dte1_candidate` / `message`；execute 增 `rejected_low_credit` |
| `bbt_option_seller.html` | `#manualCreditNotice` 提示条 + `setManualCreditNotice` / `adoptManualDte1Candidate`；确认开仓前拦截 < $0.10；服务端拒绝分支处理 |

## 5. 回滚

| 项 | 回滚方式 |
|---|---|
| 全局地板 | `option_seller_engine.MIN_OPEN_CREDIT = 0.0`（等价关闭）或还原 `use_credit = max(...)` 一行 |
| 到期回退 | 4 个调用点把 `find_optimal_spread_with_dte_fallback` 改回 `find_optimal_spread`（去掉 `dte_fallback` 参数） |
| choke point | 删 `open_trade` 内 `if net_credit < MIN_OPEN_CREDIT:` 段 |
| 手动路径 | 还原 `_scan_variants` 为原来的 Option A/B 两段 + 删 execute 闸门 + 删响应新字段 |
| 前端 | 删 `#manualCreditNotice` 与 3 个新函数、恢复 `executeManualTrade` 原分支 |
| 规则手册 | 删 §3.4 与 §3.3.1 注记（备份 `<file>.bak-<ts>` 可就地还原） |

## 6. 遗留与后续

1. **§3.3.1 手册口径与代码不一致（已注记，建议对齐）**：手册写 CONSERVATIVE ≥ $0.08 / BALANCED ≥ $0.18 /
   AGGRESSIVE ≥ $0.28，而代码 `min_credit` 为 0.03 / 0.05 / 0.12；本次只加了「全局 $0.10 下限」注记，
   **是否把三档目标口径回写成手册所述值，需用户确认**（会显著减少开仓机会）。
2. **≥20 手大单层**：与本次无关，仍在原计划中（P1/P3 大额否决）。
3. **回退统计**：`entry_evidence.dte_fallback` 已落库，可后续统计「1DTE 回退单」的实际胜率与盈亏，
   用于判断是否需要把回退上限扩展到 2DTE 或引入时变下限。
4. **时变下限**：当前为固定 $0.10；若后续数据表明「距 11:30 越近应越严」，可在此规则上叠加时段系数
   （属于 §3.4 的扩展，需新数据支持）。
