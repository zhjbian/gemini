# 验收报告 (Walkthrough) - Adam 周度复测研究报告 9 大部分完整落库与页面同步修复

## 1. 任务背景与问题诊断
交易员在对比 `http://127.0.0.1:5005/bbt_signals_large_timeframe`（大周期信号研判 -> Adam 信号研究进展）与实际接收到的邮件报告时，发现：
- 邮件端完整包含 9 个部分（含 ⑥ Setup 发现、⑦ 预注册特征筛选、⑧ 落地通道、⑨ Adam 判定被 order flow 验证率 117 条等）；
- 而页面上的周度复测报告展开后只显示到 ⑤ 说明，缺失了 ⑥ ~ ⑨ 全部内容。

### 根因排查：
1. **周度报告保存与邮件发送分支不一致**：在 [adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py) 中，`send_research_report` 传入了全部 9 个 sections，而调用 `save_research_report("weekly", ...)` 时仅硬编码传入了前 5 个 sections，导致写入 `adam_research_reports` 数据库的 JSON 数据本就只存了 ① ~ ⑤；
2. **特征筛选脚本字段容错缺陷**：[adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py) 对预注册的 `tickflip_5m` 等组合假设字段使用 `r[feat]` 导致 `KeyError`，阻断了筛选模块的独立运行；
3. **前端渲染分段连接符优化**：在 [bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html) 的 `adamRenderSections` 中，对数组项使用了 `b.join('')`，导致未包含 HTML 标签的纯文本行挤压成一行；同时 Markdown 粗体语法 `**...**` 缺乏转义解析。

---

## 2. 核心改动明细

### (1) 周度复测脚本统一 9 大板块入库 ([adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py))
- 提取统一的 `_weekly_sections` 列表，完整包含：
  - `① 门槛判定（规则 11）`
  - `② 分层统计（基础微观层）`（带 `<pre>` 等宽代码块包装）
  - `③ 样本外复现明细`（带 `<pre>` 等宽代码块包装）
  - `④ 历史门槛趋势`
  - `⑤ 说明`
  - `⑥ Setup 发现（Adam × 自家引擎交叉）`（`_disc_sec`）
  - `⑦ 预注册特征筛选（单特征条件化）`（`_scr_sec`）
  - `⑧ 落地通道（候选 → 草稿 → 待确认）`（`_land_sec`）
  - `⑨ Adam 判定被 order flow 验证率`（`_vsec`，包含 117 条判定统计汇总与各分类表格）
- 确保 `save_research_report` 与 `send_research_report` 接收完全一致的 9 大部分数据对象。

### (2) 预注册特征筛选脚本容错修复 ([adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py))
- 将 `r[feat]` 替换为安全取值 `r.get(feat)`，保证预注册但尚未累积入库字段的平滑容错，消除 `KeyError` 异常。

### (3) 前端报告渲染管道排版与语法增强 ([bbt_signals_large_timeframe.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals_large_timeframe.html))
- 在 `adamRenderSections` 中，将数组项安全映射后通过 `<br>` 连接，确保分行语义；
- 增加 `**...**` 转义为 `<b>...</b>` 的 Markdown 粗体支持；
- 保持内部原生表格（`<table>`）与等宽块（`<pre>`）的浅色主题完整渲染。

### (4) 历史数据同步补全
- 针对数据库 `adam_research_reports` 表中已存在的今日（`2026-09-18`，id=93）周度报告，重算并原子更新入库，恢复包含 ⑥ 至 ⑨ 全量 9 大部分数据。

---

## 3. 验证与测试结果

### (1) API 输出验证
调用服务端 `/data/adam_research_reports?limit=10` 验证：
```json
{
  "kind": "weekly",
  "data_date": "2026-09-18",
  "sections_count": 9,
  "sections": [
    "① 门槛判定（规则 11）",
    "② 分层统计（基础微观层）",
    "③ 样本外复现明细",
    "④ 历史门槛趋势",
    "⑤ 说明",
    "⑥ Setup 发现（Adam × 自家引擎交叉）",
    "⑦ 预注册特征筛选（单特征条件化）",
    "⑧ 落地通道（候选 → 草稿 → 待确认）",
    "⑨ Adam 判定被 order flow 验证率"
  ]
}
```
验证第 ⑨ 部分内容完全契合：
- 摘要：`累计逐帖判定 117 条：验证 36 · 部分 63 · 未验证 18 ✓（占位：样本仍少 ⇒ 仅累积 ✓ 不做结论 ✗）`
- 结构化表格：完整列出 `trend_continuation`、`commentary`、`intraday_0dte`、`reversal_top` 等类别被 order flow 验证的具体笔数分布。

---

## 4. 系统模块归档 (Rule 10)
- **归档目录**: `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/92_2026-09-18_Adam_Weekly_Report_Full_Sections_Sync/`
- **总览更新**: 更新 `bbt_trading_modules.html` 中 **M17. Adam Set 社媒信号研判与事件研究系统** 的演进历程（由 4 次更新为 5 次）并追加第 92 次演进记录与直达链接。
