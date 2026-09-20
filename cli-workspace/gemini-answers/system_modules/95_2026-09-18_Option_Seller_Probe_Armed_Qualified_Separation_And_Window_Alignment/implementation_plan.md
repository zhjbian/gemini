# 实施计划 - Option Seller 极值探针布防与到位状态分离及窗口展示口径优化

## 1. 问题背景与深度归因

用户在 `http://127.0.0.1:5005/bbt_option_seller` 的「当日高低点自动触发机制检测」中发现：
- 2026-09-18 显示：`高点#2 11:20 SPY 760.64 · ES 7703.25 (收盘 760.35 / 7700.25) 检测方向: 做空 (卖 Call) L0: 通过 触发机制: QuantPivot边界反向 (QUALIFIED)`
- 用户指出：**11:20 并不是当天真正的第二个高点，且之后股价大幅上涨了近 30 个 ES 点**。

经底层代码与日内 5 分钟 K 线逐笔回溯，发现两个根本原因：
1. **语义混淆（ARMED 逼近布防 vs QUALIFIED 到位触发）**：
   - 11:20 时，SPY 收盘价为 760.35，QuantPivot H1 为 763.19，两者相差 2.84 点（未达到 `|close - H1| <= 0.2` 的触及容差带）；
   - 但因为距离 <= 0.5% 满足“逼近布防”阈值，引擎内部实际评定为 `st = 'ARMED'`；
   - 探针 `_mech_counter_trend` 却将 `near`（布防）直接纳入 `side_pass`，并武断赋予 `verdict = 'QUALIFIED'`，导致前端顶部概览错误渲染为绿色的“触发机制: QuantPivot边界反向 (QUALIFIED)”，误导交易员以为系统建议立即市价卖 Call。
2. **窗口截断认知割裂（开仓有效窗口 06:30–11:30 PST vs 全天实际行情）**：
   - Option Seller 策略手册规定尾盘（11:30 PST / 14:30 EST 之后）严格禁开新仓；
   - 探针为了筛选开仓候选点，算法强行将分析窗口截断在 `[06:30, 11:30]`；
   - 在该截断窗口内，11:20 确实是除 06:30 外价格最高的 K 线；但全天真正的单边逼空主升浪和最高点（13:10 突破 7729.25）完全发生在 11:30 截断之后；
   - 界面上简单标注 `▲ 高点#2`，使得盘后复盘时交易员产生“系统错误识别了全天高点”的巨大困惑。

---

## 2. 改造方案

### 方案 1：状态定义分离（ARMED 逼近布防 vs QUALIFIED 到位触发）
1. **后端判据细分 ([intraday_probe.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/intraday_probe.py))**：
   - 在 `_mech_counter_trend` 中：
     - 做空侧（卖 Call）：当 `range_ok`、`pos_ok`、`pc_ok`、`bi_ok` 均通过时：
       - 若 `hit_h1` 或 `hit_h2` 为 True（触及 ±0.2 容差带）⇒ `verdict = 'QUALIFIED'`，说明“到位触及容差带”；
       - 若未触及容差带，但 `near` 为 True（<= 0.5% 逼近布防）⇒ `verdict = 'ARMED'`，说明“进入逼近布防区（警戒中），未到位触及”；
       - 否则 ⇒ `verdict = 'REJECTED'`。
     - 做多侧（卖 Put，严格对称）：
       - 若 `hit_l1` 或 `hit_l2` 为 True ⇒ `verdict = 'QUALIFIED'`；
       - 若仅 `near` 为 True ⇒ `verdict = 'ARMED'`；
       - 否则 ⇒ `verdict = 'REJECTED'`。
2. **前端与复制逻辑状态适配 ([bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html))**：
   - 区分到位触发列表 `qualifiedList` 与布防列表 `armedList`：
     - 若有点位命中 `QUALIFIED`：渲染绿色徽章 `<i class="fas fa-check-circle"></i> 触发机制: ... (QUALIFIED)`；
     - 若无 QUALIFIED 但命中 `ARMED`：渲染醒目的浅黄色/琥珀色布防徽章（背景 `#fffbeb`、文字 `#b45309`、边框 `#fde68a`，图标 `<i class="fas fa-shield-halved"></i> 布防机制: ... (ARMED 布防中)`）；
     - 若两者均无：渲染灰色 `<i class="fas fa-minus-circle"></i> 触发机制: 无`；
   - 复制文本中同步输出，如 `布防机制: QuantPivot边界反向 (ARMED)`，不再笼统写为 `触发机制: ... (QUALIFIED)`。

---

### 方案 2：展示口径与复盘认知对齐（开仓窗口 vs 全天极值）
1. **点位标签口径明确化**：
   - 在高低点第一行概览中，将 `▲ 高点#2` 调整为 `▲ 窗口高点#2 (06:30–11:30)` 或 `▲ 高点#2 (开仓窗口)`；
   - 悬浮提示（`title`）明确说明：`策略开仓许可窗口 [06:30, 11:30 PST] 内的波段高点，尾盘 11:30 后的行情不计入开仓候选`；
   - 复制文本同步调整为：`高点#2(开仓窗口) 11:20 SPY ...`。
2. **卡片头部规则醒目化**：
   - 在卡片副标题或说明区域清晰标注：
     `【开仓窗口限定】探针按策略手册 §3.1 仅分析 06:30–11:30 PST（尾盘不开仓时限截断）窗口；11:30 后的尾盘行情不计入开仓候选点。`

---

## 3. 用户审核要点 (User Review Required)

> [!IMPORTANT]
> **状态口径变更影响说明**：
> 1. 原先因为 `near <= 0.5%` 被判定为 `QUALIFIED` 的点位，重构后将精确回归为 `ARMED`（布防中），不再在概览行被误认作“立即开仓信号”；
> 2. 历史落库数据或前端展示中，仅当价格真实打入容差带（±0.2 点）时，才会出现绿色 `QUALIFIED`；
> 3. 高低点名称加上 `(开仓窗口)` 标识，确保盘后复盘时与全天全局走势清晰区分。

---

## 4. 验证计划

### 自动化与接口验证
1. 运行 Python 脚本重新执行 2026-09-18 的 `probe('2026-09-18')`：
   - 验证 11:20 点位的 `AUTO_QUANT_PIVOT_BOUNDARY` 机制 `verdict` 正确输出为 `ARMED`，而非 `QUALIFIED`；
   - 验证其 `rationale` 正确反映“进入逼近布防区（距边界 <= 0.5%），未到位触及”；
   - 验证做多侧（卖 Put）逻辑对等有效。
2. 验证语法与静态检查：使用 Python 3.11 编译 `intraday_probe.py`，无语法错误。

### 手动验收与归档
1. 检查前端 `http://127.0.0.1:5005/bbt_option_seller` 页面（遵照规则 (5) 不自动打开浏览器，由用户测试）：
   - 检查 11:20 行显示的徽章是否已变为琥珀色 `布防机制: QuantPivot边界反向 (ARMED)`；
   - 检查高低点标签是否标注 `(开仓窗口)`；
   - 点击复制按钮，检查剪贴板文本格式是否精准对应。
2. 按照规则 (10) 归档实施计划与验收报告至 `system_modules/` 并更新 `bbt_trading_modules.html`。
