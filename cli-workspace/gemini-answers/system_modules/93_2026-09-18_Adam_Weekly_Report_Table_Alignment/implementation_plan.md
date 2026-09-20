# 实施计划 - Adam 周报表格化与列垂直对齐改造

## 1. 需求背景
交易员反馈 `http://127.0.0.1:5005/bbt_signals_large_timeframe`（大周期信号研判 -> Adam 信号研究进展）展开周报时：
- ② 分层统计（基础微观层）：原本由 Python 脚本以 ASCII 格式打印，在浏览器中由于中文字符宽度与英文不等，各列严重漂移失位，未垂直对齐；
- ③ 样本外复现明细：同样为 ASCII 格式，`分层`、`期`、`n`、`d20均值`、`命中率`、`p(d20)` 等列存在右向偏差，底部的 `=== 复现判定（规则 11 条件③）===` 各项未对齐；
- ⑦ 预注册特征筛选（单特征条件化）：原本为无序列表（`<ul><li>`），特征标识、名称及阈值混在同一行，无列对齐。

## 2. 改造方案
1. **Section ② 分层统计表格化 ([adam_feature_stats.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_stats.py))**：
   - 增加 `build_html() -> tuple[str, bool, str]` 函数，构建基于标准浅色主题（Light Theme）的 HTML 表格；
   - 表头包含 `分层`（左对齐）、`n`、`d5`、`d10`、`d20`、`fav20`、`mae20`、`新低/高`、`p(d20)`（数值全部右对齐）；
   - 下方结构化呈现 `=== 规则(11) 门槛判定 ===` 浅色卡片，保留 CLI 的纯文本打印输出。
2. **Section ③ 样本外复现明细表格化 ([adam_feature_oos.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_oos.py))**：
   - 增加 `build_html() -> tuple[str, bool, str]` 函数，将训练期与验证期分层构建为标准 HTML 表格，`期` 居中徽章显示，数值列全部右对齐；
   - 将 `=== 复现判定（规则 11 条件③）===` 转换为 3 列标准表格（分层、验证期统计、判定结果徽章），实现状态绝对垂直对齐。
3. **Section ⑦ 预注册特征清单表格化 ([adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py))**：
   - 将 `reg` 的 `<ul><li>` 列表转换为 3 列标准表格（`特征标识 (Key)`、`特征名称与含义`、`判定切分阈值 / 说明`）。
4. **周报组装调度更新 ([adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py))**：
   - 引入 `adam_feature_stats.build_html` 与 `adam_feature_oos.build_html`，将 section ② 和 ③ 由 `<pre>` 文本块升级为 HTML 原生表格。
5. **数据库实时同步更新**：
   - 重算并更新 `adam_research_reports` 表中已存在的周报记录（id=93），使页面立即展现对齐表格。

## 3. 验证方案
1. 运行 `python3` 测试 `adam_feature_stats.build_html()`、`adam_feature_oos.build_html()`、`adam_feature_screen.build()` 正常返回标准 HTML 表格。
2. 调用 `/data/adam_research_reports?limit=5` 确认 row 93 中 section ②、③、⑦ 均包含完整 table 结构。
3. 遵循规则 (5)，不自动打开浏览器测试，由用户刷新页面验证。
