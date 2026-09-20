# 实施计划 (Implementation Plan)

**模块编号**: 44 · **归档目录**: `44_2026-09-11_Option_Seller_KPI_Dashboard_Optimization` · **日期**: 2026-09-11
**核心模块名称**: 期权卖方首页 KPI 看板优化 (Option Seller KPI Dashboard Optimization)
**涉及技术栈**: Python / OptionSellerManager Status Summary / Jinja 模板内联 JS / Light-Theme UI

## 1. 需求（用户 2026-09-11）

1. 删除「活跃持仓数」卡片的静态副行 **「最大并发上限: 2 手」**（与实际实现不一致）。
2. 用户基本不关注 **净 Delta 暴露 / 净 Theta 收益率** → 更换为更重要的指标。
3. 在「活跃持仓数」**之后**新增一张 **未触发条件单** 卡片。

## 2. 方案

| 卡片 | 处理 | 依据 |
| --- | --- | --- |
| 活跃持仓数 | 删除静态副行 | 该值与实测实现不符，属误导性文案 |
| ~~净 Delta 暴露~~ → **今日卖出权利金 (Premium Collected)** | 后端新增 `premium_collected_today` = Σ(`net_credit`×100×手数)，LIVE；副行显示今日 LIVE 平仓构成 | 卖方收益来源规模，比方向性 Greeks 更可操作 |
| ~~净 Theta 收益率~~ → **最大亏损敞口 (Max Loss at Risk)** | 后端新增 `max_loss_at_risk` = Σ(|`max_loss`|×手数)，活跃 LIVE 持仓；副行显示活跃手数 | 卖方真实风险上限（`max_loss` 已是美元口径） |
| **未触发条件单数**（与「活跃持仓数」同卡、**紧凑两行式并列**：`标签：数值`） | 取 `pending_conditional_orders` 计数；来源拆分「系统自动 a · 手动 m」置于标签 tooltip | 二者为**并列信息**（非父子），且不使用大号 `metric-value`，以免卡片高度明显高于同排其它卡片 |

配套修正：`_reload_conditional_orders()` 补 `source`（原先仅内存态设置，DB 重载后丢失 → 无法区分自动/手动）。

## 3. 验收标准

| # | 项 | 判定 |
| --- | --- | --- |
| 1 | 卡片顺序 | 当日净收益 → 日内胜率 → 活跃持仓数（内置紧凑并列行：未触发条件单数）→ 今日卖出权利金 → 最大亏损敞口 |
| 2 | 文案清理 | 页面无「最大并发上限」「净 Delta 暴露」「净 Theta 收益率」 |
| 3 | 新指标数值正确 | 2026-09-11：今日卖出权利金 = (0.15+0.15+0.17+0.17)×100 = **$64.00**；平仓构成 止盈 2 / 保本 2 |
| 4 | 无空引用 | 历史日期分支改为带空值保护的占位更新（原 `getElementById('metricNetDelta')` 会抛错） |
