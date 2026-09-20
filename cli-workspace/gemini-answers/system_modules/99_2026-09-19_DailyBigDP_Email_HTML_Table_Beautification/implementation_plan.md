# DailyBigDP 暗盘大单统计邮件 HTML 表格美化实施计划

## 1. 需求背景与痛点
系统每日收盘后通过 `PyTools/dp/dp_daily_big.py` 统计并发送全市场主要标的（SPY, QQQ, NVDA, AAPL 等）暗盘成交名义金额超标的提醒。
此前邮件采用纯文本单行格式输出：
```text
DailyBigDP
AAPL: 28621 > 2500.0
AMD: 8908 > 1000
AMZN: 9504 > 2500.0
...
```
- **排版杂乱**：等宽字符未对齐，金额缺乏千分位与单位换算，手机端与桌面端可读性较差。
- **重点不突出**：无法一眼识别超标倍数最高、资金量最大的巨鲸机构动向。

## 2. 实施目标与设计原则
1. **浅色主题与视觉质感 (Light Theme)**：统一遵循白色背景 (#ffffff)、浅灰与柔和浅蓝配色，严禁深色黑底，符合系统设计规范。
2. **移动端首屏预读 (Preheader)**：嵌入隐形摘要文本，在 iPhone Mail 及 Gmail 邮件列表预览中即可预览超标标的及最大资金规模。
3. **结构化信息表格**：
   - 包含：标的、暗盘成交额 (含 $M 与 $B 换算)、基准阈值、超标倍数胶囊标签。
   - 默认按成交额降序排序，突出大资金权重。
   - 底部提供合计汇总行。
4. **双通道平滑兼容**：
   - Gmail 邮件通道切换为 HTML 富文本渲染 (`BBSms.send_to_gmail_html`)。
   - 手机短信 SMS 通道保持纯文本 (`BBSms.send_with_check`)，避免手机短信显示未经渲染的 HTML 标签。

## 3. 涉及文件与变更清单
- **修改文件**：
  - [PyTools/dp/dp_daily_big.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/dp/dp_daily_big.py)：新增 `render_daily_big_dp_html` 函数，并在 `main()` 中集成结构化数据归集与 HTML 邮件发送。

## 4. 验证方案
- 单元语法与导入测试。
- 使用真实样本数据离线渲染并输出 HTML 文件校验样式结构。
