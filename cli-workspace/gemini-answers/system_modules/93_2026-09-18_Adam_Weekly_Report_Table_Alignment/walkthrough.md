# 验收报告 (Walkthrough) - Adam 周报表格化与列垂直对齐改造

## 1. 任务背景与对齐问题诊断
在 `http://127.0.0.1:5005/bbt_signals_large_timeframe`（大周期信号研判 -> Adam 信号研究进展）中，展开周报详情后发现三处排版与列对齐问题：
1. **Section ② 分层统计（基础微观层）**：原本使用 `<pre>` 等宽文本块打印 Python 字符串格式化输出。因中文字符（如 `全部反转事件`、`用途 swing_reversal`、`确认度高 conv≥4` 等）与英文字符在不同操作系统和浏览器等宽字体下的宽度映射差异（通常为 1.5 到 2 倍宽），导致后面的数值列（`n`, `d5`, `d10`, `d20`, `fav20`, `mae20`, `新低/高`, `p(d20)`）严重向右倾斜漂移，无法垂直对齐；
2. **Section ③ 样本外复现明细**：同样为 ASCII 文本格式，各分层项的训练期与验证期数值列错位，且下方的 `=== 复现判定（规则 11 条件③）===` 结论状态没有对齐的列结构；
3. **Section ⑦ 预注册特征清单**：原本通过 `<ul><li>` 无序列表显示，各特征标识（如 `qm_dper`）、名称和阈值混合排布在行内，缺乏列式结构。

---

## 2. 核心改动与工程实现

### (1) 分层统计表格化与列严格对齐 ([adam_feature_stats.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_stats.py))
- 新增 `build_html() -> tuple[str, bool, str]` 函数；
- 输出严格采用标准 Light Theme HTML 表格（`border-collapse: collapse;`），表头与行边框采用统一的浅灰高保真色阶（`#e2e8f0`、`#f1f5f9`）；
- 表头与单元格对齐规范：
  - `分层`：文本左对齐（`text-align: left`），根分层（`全部反转事件`）加粗突出并带浅灰底色；
  - `n`、`d5`、`d10`、`d20`、`fav20`、`mae20`、`新低/高`、`p(d20)`：数值全部右对齐（`text-align: right`），严格消除字体渲染偏差；
  - 显著性检验（Bonferroni 阈值达标）的 p 值以绿色加粗显示；
- 表格下方嵌入浅色卡片总结 `=== 规则(11) 门槛判定 ===`，同时保留 CLI 控制台输出纯文本支持。

### (2) 样本外复现明细表格化 ([adam_feature_oos.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_oos.py))
- 新增 `build_html() -> tuple[str, bool, str]` 函数；
- 将 4 大分层（`reversal_top`、`reversal_bottom`、`conv≥4`、`top 且 conv≥4`）在训练期与验证期的 8 行统计构建为标准 HTML 表格，`期` 列采用居中胶囊徽章，数值列全部右对齐；不同分层之间增加浅灰分隔线；
- 将 `=== 复现判定（规则 11 条件③）===` 升级为 3 列微型表格：
  - 列 1：`分层`（左对齐）
  - 列 2：`验证期统计`（如 `n=6 均值 -0.27%`，左对齐）
  - 列 3：`判定结果`（颜色状态徽章：未复现红色 ✗、样本不足灰色 ✗、成功绿色 ✓）
- 结论与自动下单规则整齐排列在卡片底部。

### (3) 预注册特征清单表格化 ([adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py))
- 将原本的无序列表 `<ul><li>` 改建为三列垂直对齐的标准 HTML 表格：
  - `特征标识 (Key)`：等宽代码样式（`<code>`）；
  - `特征名称与含义`：清晰文本；
  - `判定切分阈值 / 说明`：辅助说明文本；
- 彻底解决各特征名称长短不一导致的右侧括号错位问题。

### (4) 周报组装管道更新 ([adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py))
- 引入各模块导出的 `build_html` 函数，替换原本将 ASCII 文本包装在 `<pre>` 标签内的旧模式，生成端直接输出原生浅色 HTML 表格。

### (5) 数据库历史周报原子更新
- 重新计算今日（`2026-09-18`，id=93）的周报各分区内容，并将包含新 HTML 表格的 sections 写入 MySQL 数据库，确保前端直接刷新即可看到垂直对齐的表格。

---

## 3. 验证与测试结果

### (1) 模块执行验证
- 执行 `python3 -c "import adam_feature_stats; print(adam_feature_stats.build_html()[0][:200])"`：成功输出 `<div ...>反转事件样本: <b>63</b> 条...<table ...>`；
- 执行 `python3 -c "import adam_feature_oos; print(adam_feature_oos.build_html()[0][:200])"`：成功输出样本外主表格与复现判定微型表格；
- 执行 `python3 -c "import adam_feature_screen; print(adam_feature_screen.build()[1]['register'][:200])"`：成功输出预注册特征 3 列表格。

### (2) API 接口响应检查
调用 `/data/adam_research_reports?limit=5` 查询 id=93 周报记录：
```json
{
  "id": 93,
  "kind": "weekly",
  "data_date": "2026-09-18",
  "sections_count": 9,
  "section_2": "<table ...>（分层统计 9 列垂直对齐表格）",
  "section_3": "<table ...>（样本外复现 6 列主表格 + 3 列判定表格）",
  "section_7": "<table ...>（预注册特征 3 列表格）"
}
```

---

## 4. 交付文件与影响范围
- [PyTools/jobs/adam_feature_stats.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_stats.py)：增加 `build_html`，输出分层统计 9 列表格与门槛判定卡片；
- [PyTools/jobs/adam_feature_oos.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_oos.py)：增加 `build_html`，输出样本外复现明细表格与判定结果表格；
- [PyTools/jobs/adam_feature_screen.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_feature_screen.py)：将预注册特征清单输出由 `<ul>` 替换为 3 列表格；
- [PyTools/jobs/adam_weekly_retest.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/jobs/adam_weekly_retest.py)：周度复测报告组装接入 HTML 表格生成器；
- MySQL 数据库 `adam_research_reports` 表（id=93）：同步持久化更新。
