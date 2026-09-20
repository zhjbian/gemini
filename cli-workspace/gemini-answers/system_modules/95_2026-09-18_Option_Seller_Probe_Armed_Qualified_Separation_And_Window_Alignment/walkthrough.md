# 验收报告 - Option Seller 极值探针布防与到位状态分离及窗口展示口径优化

## 1. 概述与改造背景
交易员在复盘 `http://127.0.0.1:5005/bbt_option_seller` 的「当日高低点自动触发机制检测」时提出：
- 2026-09-18 的点位 `高点#2 11:20 SPY 760.64 · ES 7703.25 ... 触发机制: QuantPivot边界反向 (QUALIFIED)` 并不是全天第二高点，且在 11:20 之后股价暴涨近 30 个 ES 点。
- 经分析确认，该现象源于两点：
  1. **状态定义混淆**：11:20 时 SPY 距 H1 边界有 2.84 点（未达到 ±0.2 点容差带到位触发），仅满足 `<= 0.5%` 逼近布防条件（ARMED 警戒）。但探针代码将 `near`（布防）一并判定为了 `QUALIFIED`，误导交易员以为建议立即市价卖 Call。
  2. **时段截断认知割裂**：探针基于策略手册 §3.1 尾盘（11:30 PST 之后）不开新仓的纪律，仅对 `[06:30, 11:30]` 窗口进行极值提取，而全天真正逼空暴涨发生在此截断窗口之后（13:10 突破 7729.25）。

本次改动针对 **需求 1（状态定义分离）** 与 **需求 2（展示口径与复盘认知对齐）** 进行了系统性优化。

---

## 2. 核心修改明细

### 2.1 后端判据严格分离到位触发与逼近布防 ([intraday_probe.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/intraday_probe.py))
- 在 `_mech_counter_trend` 评估器中，对做空侧（卖 Call）与做多侧（卖 Put）双向严格执行分流：
  - **到位触发 (QUALIFIED)**：当且仅当价格真正触及容差带（做空侧 `hit_h1` 或 `hit_h2`；做多侧 `hit_l1` 或 `hit_l2`）时，才给出 `verdict = 'QUALIFIED'`；
  - **逼近布防 (ARMED)**：未触及容差带但满足 `0.2 点 < 距离 <= 0.5%` 时，准确给出 `verdict = 'ARMED'`，说明“进入逼近布防区（警戒中），未到位触及”；
  - **拒绝 (REJECTED)**：前置未过或均未命中。
- 消除原先将 `near` 直接并入 `side_pass` 导致武断评为 `QUALIFIED` 的漏洞。

### 2.2 前端徽章与复制文本精细化适配 ([bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html))
- **时段限定提示**：在探针卡片顶部增加醒目浅蓝提示条：
  `【开仓时段限定提示】本探针严格按照策略手册 §3.1 限制在 06:30–11:30 PST（尾盘不开仓截断）窗口内筛选候选高低点。11:30 之后的走势或极值不计入开仓候选点。`
- **独立布防徽章**：
  - 到位触发：保持绿色 `<i class="fas fa-check-circle"></i> 触发机制: ... (QUALIFIED)`；
  - 仅逼近布防：渲染浅琥珀色警备徽章 `<i class="fas fa-shield-halved"></i> 布防机制: ... (ARMED)`（文字颜色 `#b45309`、背景 `#fffbeb`、边框 `#fde68a`）；
  - 单项机制标题左侧边框及文字对应应用琥珀色，视觉上与绿色 QUALIFIED 清晰隔离。
- **高低点标签与复制格式明确口径**：
  - 高低点标题显示为 `▲ 高点#2 开仓窗口`（带灰色时段标签，悬浮提示说明尾盘不计入）；
  - 复制文本输出为 `-> 高点#2(开仓窗口) 11:20 SPY 760.64 · ES 7703.25 ... 布防机制: QuantPivot边界反向 (ARMED)`，不再混为一谈。

---

## 3. 验证与回归测试结果

### 3.1 2026-09-18 实际回测输出验证
运行探针诊断验证脚本：
- **11:20 点位**：
  - `AUTO_QUANT_PIVOT_BOUNDARY`: `verdict = 'ARMED'`
  - `Rationale`: `高点统一口径【做空】：进入 H1 逼近布防区（距边界 <= 0.5%），未到位触及容差带 ⇒ 布防警戒（引擎自身：ARMED · BEARISH）`
  - 前端渲染：琥珀色徽章 `布防机制: QuantPivot边界反向 (ARMED)`。
- **07:15 点位（做多对称性验证）**：
  - `AUTO_QUANT_PIVOT_BOUNDARY`: `verdict = 'ARMED'`
  - `Rationale`: `低点统一口径【做多】：进入 L1 逼近布防区（距边界 <= 0.5%），未到位触及容差带 ⇒ 布防警戒`。
- **09:25 点位（到位触发验证）**：
  - `AUTO_BALANCED_DAY_BOUNDARY`: 依然稳定输出 `QUALIFIED`，不受影响。

### 3.2 语法与模板编译检查
- Python 3.11 语法编译通过（`py_compile` 退出码 0）。
- HTML 模板中的嵌入式 JavaScript 代码块通过 Node.js AST 语法校验，无语法错误。
