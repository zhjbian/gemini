# 期权卖家系统「券商未跟踪持仓」独立成区展示（价差配对 + 单腿列出） 验收报告 (Walkthrough)

## 1. 任务概述

按交易员指令：券商有但系统未跟踪的仓位，必须显示在
`http://127.0.0.1:5005/bbt_option_seller` → **活跃持仓监控 (Active Spread Monitor) 下方的新 section**，
尽力**配成价差**展示，**单腿仓位也要列出**。

## 2. 交付内容

### 2.1 页面新 section

- `活跃持仓监控 (Active Spread Monitor)` 之下新增 **「券商未跟踪持仓 (Untracked Broker Positions)」**；
  无未跟踪仓位时整区隐藏（`display:none`），不影响日常视图。
- 标题行：两个计数徽章 `N 组价差` / `M 单腿` + 数据来源标注
  `来源: Schwab get_account(POSITIONS) · 仅观测不处置`。
- **配对价差卡片**（浅色主题，白底 + 浅红边框）：类型与到期、×数量、成因标签、双腿表格
  （方向/行权价/合约/开仓均价/标记价/浮盈）、汇总行（组合净市价 / 组合开仓净价 / 浮动盈亏 / 市值 / 关联流水 #N）。
- **未配对单腿表格**：合约、说明、方向、数量、开仓均价、标记价、市值、浮盈、成因。
- 底部红色提示：这些仓位无止盈/止损、不会被自动平仓；可用「恐慌平仓」或券商端人工处置。

### 2.2 后端配对（与恐慌平仓共用同一实现）

`_pair_untracked_legs()`：按合约族（root+YYMMDD+C/P）分组 → 组内**最近行权价贪心配对** →
产出 `spreads`（含 `spread_type` / 双腿实际方向 / `net_mark` / `net_avg` / `pnl` / `market_value` / 成因）
与 `singles`（单腿）。`_reconcile_broker_positions()` 结果新增 `untracked_spreads` / `untracked_legs`；
`flat_uncovered_broker_positions()`（恐慌平仓）重构为复用同一配对结果，杜绝"展示能配对、平仓却按行配对"的漂移。

展示数字口径（新增）：
- 标记价 `mark = |marketValue| / (|quantity| × multiplier)`；
- 浮盈 `(mark − avgPrice) × 带符号数量 × multiplier`；
- 组合净市价 `mark_long − mark_short`、组合开仓净价 `avg_long − avg_short`。

## 3. 验证结果

### 3.1 单元测试（22 项全通过）

```bash
PYTHONPATH=PyTools:bbt_data_web /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  -m unittest test_orphan_position_reconcile
```

```text
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、13 个数据库写方法
......................
----------------------------------------------------------------------
Ran 22 tests in 0.741s
OK
```

新增 5 项覆盖：

| 用例 | 守护的不变量 |
| :--- | :--- |
| `test_reconcile_pairs_untracked_into_spread` | 反向价差配成 1 组；`net_mark=0.31`、`net_avg=0.38`、**`pnl=−7.00`**、`market_value=31.00`（与 TOS 实测逐项一致） |
| `test_reconcile_lists_single_leg_when_no_pair` | 只有一条腿时**不得硬凑价差**，必须落 `untracked_legs` |
| `test_pair_untracked_legs_call_spread_plus_stray_leg` | 看涨价差正常配对、多余腿单列；不跨标的/到期/类型误配 |
| `test_pair_untracked_legs_splits_quantity_across_matches` | 空 2 / 多 1 ⇒ 1 组 + 剩余 1 张（数量守恒） |
| `test_reconcile_payload_always_has_display_keys` | 无漂移时 `untracked_spreads` / `untracked_legs` 仍存在（前端依赖） |

### 3.2 前端渲染校验（Node 桩 DOM 直接调用渲染函数）

```text
section display: ""            // 有数据 -> 显示
badges: 1 组价差 / 1 单腿
contains 754/752: true | 0.310: true | 0.380: true | -7.00: true | 31.00: true
contains 288: true | 反向执行为开仓: true | 未跟踪: true
empty -> display: "none" | list cleared: true
```

### 3.3 实盘只读验证

```json
"broker_reconcile": { "...", "untracked_spreads": [], "untracked_legs": [] }
```

状态接口已返回新字段（当前账户无持仓，故为空 ⇒ 新 section 自动隐藏）；租约仍为单实例
（`monitor_lease.is_leader=true`，leader pid 随重载滚动到最新子进程）。

### 3.4 全量回归

期权卖家套件全量执行（582+ 项），仅剩既有、与本次改动无交集的
`test_absorption_reversal_module` 门槛样本失败。

## 4. 使用与回滚

- **使用**：打开 `http://127.0.0.1:5005/bbt_option_seller`（模板已改动，浏览器需**硬刷新** ⌘⇧R）。
  当券商侧出现系统未跟踪仓位时，页面自动出现该 section：先看配对价差卡片判断敞口结构，
  再看单腿表格；需要处置时用「恐慌平仓」（会按同一配对结果提交平仓单）或券商端人工处理。
- **回滚**：删除模板中的 `untrackedBrokerSection` 与 `renderUntrackedBrokerPositions()` 调用；
  后端删除 `_pair_untracked_legs` / `_broker_symbol_map` / `_uncovered_legs` / `_leg_excess` 及
  `reconcile` 结果里的两个新键（`★ 2026-09-16` 注释可定位），并把 `flat_uncovered_broker_positions`
  恢复为内联配对版本。
