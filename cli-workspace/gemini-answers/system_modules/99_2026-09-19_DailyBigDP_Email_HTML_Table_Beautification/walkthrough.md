# DailyBigDP 暗盘大单统计邮件 HTML 表格美化交付与验收报告

## 1. 概述与核心变更

针对每日盘后发送的 `DailyBigDP` 暗盘大单统计邮件，完成了从无序纯文本到现代化浅色主题 (Light Theme) 邮件卡片表格的升级：

### 核心变更点
1. **模块文件**：[PyTools/dp/dp_daily_big.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/dp/dp_daily_big.py)
2. **新增渲染函数 `render_daily_big_dp_html`**：
   - **浅色主题与阴影卡片**：纯白底板 (`#ffffff`)、轻柔浅蓝主表头渐变 (`#f0f9ff` 到 `#e0f2fe`)，浅灰边框 (`#cbd5e1`)，严禁大面积深色背景。
   - **移动端 Preheader 隐形预览**：通过隐藏 span 在邮件未打开前提供诸如 `DailyBigDP · 2026-09-18 · 共 18 标的超标 · NVDA $36.7B, AAPL $28.6B, SPY $25.4B...` 的预览。
   - **机构大单权重排序**：按总成交额从高到低自动降序排列。
   - **千分位与十亿单位智能换算**：成交额及阈值超过 1,000M 时自动标注 `($XX.XB)`。
   - **超标倍数分级胶囊徽章**：
     - 超标 >= 5.0x：高亮淡蓝底深蓝字胶囊徽章。
     - 超标 >= 2.5x：翡翠绿底深绿字胶囊徽章。
     - 其他超标：浅灰底色胶囊徽章。
   - **汇总统计行 (Footer)**：标明超标标的总数与合计名义成交额。
3. **双通道平滑分发**：
   - 邮件通道：`BBSms.send_to_gmail_html(html_big_dp)`
   - 短信通道：保持原有纯文本 `BBSms.send_with_check(sms_big_dp_str)`，确保短信终端不产生乱码标签。

---

## 2. 表格展示结构对比

### 原有纯文本输出
```text
DailyBigDP
AAPL: 28621 > 2500.0
AMD: 8908 > 1000
AMZN: 9504 > 2500.0
APP: 2705 > 1000
...
```

### 美化后 HTML 邮件卡片样式
- **表头**：`🏛️ 暗盘大单统计 (Daily Big DP)` 带有当前生成时间戳。
- **副标题**：`📅 交易日: YYYY-MM-DD` | `共 18 只标的超标` 徽章。
- **数据行**：
  | 标的 | 暗盘成交额 | 基准阈值 | 超标 |
  | :--- | :--- | :--- | :---: |
  | **NVDA** | $36,709M ($36.7B) | $8,000M ($8.0B) | `4.6x` |
  | **AAPL** | $28,621M ($28.6B) | $2,500M ($2.5B) | `11.4x` |
  | **SPY** | $25,390M ($25.4B) | $6,000M ($6.0B) | `4.2x` |
  | **MSFT** | $17,127M ($17.1B) | $2,500M ($2.5B) | `6.9x` |
  | ... | ... | ... | ... |
- **合计行**：`合计 (18只)` | `$187,058M ($187.1B)`

---

## 3. 验证与测试
- 语法与导入编译测试通过 (`python3 -m py_compile /Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/dp/dp_daily_big.py`)。
- 完整数据集离线测试生成 HTML 卡片，HTML 标签闭合、行高与各端兼容性完整达标。
