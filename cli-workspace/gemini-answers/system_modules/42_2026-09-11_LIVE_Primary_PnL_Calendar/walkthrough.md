# 验收报告 (Walkthrough)

**模块编号**: 42 · **归档目录**: `42_2026-09-11_LIVE_Primary_PnL_Calendar` · **日期**: 2026-09-11
**核心模块名称**: 期权卖方日历盈亏 LIVE 主显示改造 (LIVE-Primary PnL Calendar & Monthly Badge)

## 1. 交付

单文件改动：`bbt_data_web/templates/bbt_option_seller.html`（5 处 + 1 处稳健化）

| # | 位置 | 变更 |
| --- | --- | --- |
| 1 | 月度累计变量 | 新增 `monthLivePnl` / `monthDryPnl`（`monthTotalPnl` 保留作 tooltip） |
| 2 | 单元格数据段 | 提前计算 LIVE/DRY；配色改为跟随主显示值 LIVE；累计月度 LIVE/DRY |
| 3 | 单元格 DOM | 首行 `cal-pnl-val` = LIVE（仅负数带 `-`）；次行 `cal-trade-count` = `DRY $x All $y`（小一号） |
| 4 | 徽标色阶 | 由 `monthTotalPnl` 改为 `monthLivePnl` |
| 5 | 徽标 DOM | `月度盈亏: +$LIVE <span 0.82em>/ $DRY</span>`（DRY 小一号） |
| 6 | 稳健化 | 次行拆为 `DRY 组` / `All 组` 两个 nowrap 分组，避免窄格断成三行 |

## 2. 验收结果（headless CDP 实测，重载页面）

| 验收项 | 实测 |
| --- | --- |
| 月度徽标 | `月度盈亏: +$101.00 / $347.00`；主字号 12.16px、**DRY 9.97px（≈0.82 倍）** ✓ |
| 单元格（09-02） | 首行 `$0.00`（LIVE）、次行 `DRY $81.00 All $81.00`；次行字号 **10.88px < 首行 13.6px** ✓ |
| 单元格（09-10） | 首行 `$87.00`（LIVE）、次行 `DRY $0.00 All $87.00` ✓ |
| 配色一致性 | LIVE=0 / DRY>0 的日期（09-02/03/04/08）呈 `cell-even`（灰），与首行 `$0.00` 一致 ✓ |
| 窄格排版 | 双月视图（cell 73px / 98px）下次行 **2 行**（DRY 组 / All 组），非三行碎断 ✓ |
| 数据一致性 | Sep 合计 LIVE 101 / DRY 347 / All 448，与逐日分项求和一致 ✓ |

## 3. 规则手册处理

本次为 **UI 展示规范**（数值主次与字号），**不写入** `gemini_answer-trading_system_rules_manual`——依据既有裁定：仅"提供趋势判断/交易决策"的**决策性规则**入库，UI 展示规范、字段定义、格式表示法等工程实现不入库。

## 4. 回滚

将 `bbt_option_seller.html` 上述 6 处改回：单元格首行用 `pnl`(All)、次行用 `LIVE … · DRY …`；徽标用 `monthTotalPnl` 单值；配色判定改回 `pnl`。
