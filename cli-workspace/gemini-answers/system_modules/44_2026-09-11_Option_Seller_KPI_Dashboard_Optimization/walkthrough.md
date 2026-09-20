# 验收报告 (Walkthrough)

**模块编号**: 44 · **归档目录**: `44_2026-09-11_Option_Seller_KPI_Dashboard_Optimization` · **日期**: 2026-09-11
**核心模块名称**: 期权卖方首页 KPI 看板优化

## 1. 交付

| 层 | 文件 | 变更 |
| --- | --- | --- |
| 后端 | `PyTools/option_seller/option_seller_manager.py` | `get_status_summary()` 新增 `premium_collected_today` / `max_loss_at_risk` / `exit_mix`（写入 `today_stats`）；`_reload_conditional_orders()` 补 `source` 字段 |
| 前端 | `bbt_data_web/templates/bbt_option_seller.html` | 删除「最大并发上限: 2 手」副行；将「未触发条件单数」并入「活跃持仓数」卡片，采用**紧凑两行式并列**（`活跃持仓数：0` / `未触发条件单：0`，0.95rem + 等宽加粗数值），去掉大号数值与分隔线以控制卡片高度；Delta/Theta 两卡替换为「今日卖出权利金」「最大亏损敞口」；历史日期分支改为空值保护更新 |

## 2. 验收结果

**后端接口实测**（`GET /api/option_seller/status`）：

```
today_stats.premium_collected_today = 64.00      # (0.15+0.15+0.17+0.17)*100
today_stats.max_loss_at_risk        = 0          # 当前 0 活跃持仓
today_stats.exit_mix                = {"保本": 2, "止盈": 2}
pending_conditional_orders          = []         # 当前处于 11:00–23:30 截断窗口，禁止布防
```

**页面静态核验**（服务端返回的 HTML，卡片顺序）：

```
当日净收益 ( → 日内胜率 ( → 活跃持仓数 ( → 活跃持仓数（内置紧凑并列行：未触发条件单数）→ 今日卖出权利金 ( → 最大亏损敞口 (
```

- 新元素存在：`未触发条件单 (Pending Conditional Orders)`、`metricPendingCondCount`、`metricPendingCondSub` 各 1/2/2 处；
- 旧文案清除：`最大并发上限` = 0、`净 Delta 暴露` = 0、`净 Theta 收益率` = 0、`metricNetDelta` / `metricNetTheta` = 0（残留的第二处引用已改为带空值保护的占位更新，避免 null 抛错中断渲染）。

## 3. 说明

- 「未触发条件单」当前显示 **0**，原因是此刻处于 **11:00–23:30 PST 时段截断窗口**（module 41 规则：窗口外禁止布防且无 PENDING）；在 23:30–11:00 布防窗口内或引擎布防后将显示实际数量与来源拆分。
- 未观察到的其它可选指标（时段窗口倒计时、止损距阵、盈亏比、可用资金/保证金占用）已在会话中列为候选，未实施。

## 4. 回滚

- 前端：还原三处卡片与 JS（可从本文件与 `git` 记录还原）。
- 后端：移除 `premium_collected_today` / `max_loss_at_risk` / `exit_mix` 计算与 `source` 字段（不影响既有字段与统计）。
