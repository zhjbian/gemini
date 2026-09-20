# 实施计划 - Adam 周度复测研究报告 9 大部分完整落库与页面同步修复

## 1. 需求背景
交易员在对比 `http://127.0.0.1:5005/bbt_signals_large_timeframe` 与实际接收的邮件时发现：
- 邮件报告包含完整的 9 大部分（含 ⑥ Setup 发现、⑦ 预注册特征筛选、⑧ 落地通道、⑨ Adam 判定被 order flow 验证率等）；
- 页面上的报告只显示到 ⑤ 说明，缺少后 4 个关键板块。

## 2. 改造方案
1. **周度任务修复 ([adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py))**：将 `save_research_report` 改为传入完整的 `_weekly_sections`（包含 9 大部分），与 `send_research_report` 保持严格一致。
2. **特征筛选容错 ([adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py))**：将 `r[feat]` 改为 `r.get(feat)`，消除未入库预注册特征导致的 `KeyError`。
3. **前端渲染优化 ([bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html))**：增强 `adamRenderSections` 的数组换行与粗体语法支持，保证原貌渲染。
4. **历史数据补全**：更新当前数据库（id=93）周度报告的 `sections` 字段，补齐 9 大部分。

## 3. 验证方案
1. 运行 `/usr/local/bin/python3 -m py_compile` 验证脚本语法。
2. 验证 `/data/adam_research_reports?limit=10` 输出，确认返回 9 个 sections，且第 ⑨ 部分数据完整。
3. 归档至 `system_modules/92_2026-09-18_Adam_Weekly_Report_Full_Sections_Sync/` 并更新 `bbt_trading_modules.html`。
