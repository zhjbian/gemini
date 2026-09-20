# 验收报告 (Walkthrough) - 条件单结构化信息拷贝与已触发条件单独立监控卡片

## 1. 任务概述
交易员在 `http://127.0.0.1:5005/bbt_option_seller` 监控与复盘过程中提出两项操作体验与透明度优化需求：
1. **对每个待触发条件单添加拷贝按钮**：点击可一键拷贝条件单的关键配置、点位差距与执行计划信息，便于在交易沟通或日志记录中复用。
2. **在待触发条件单下方新增【已触发条件单】卡片**：独立展示今日已自动达成条件并下达券商开仓的条件单列表，清晰呈现触发时间、触发标的价、生成交易持仓号等。

---

## 2. 核心改动明细

### (1) 后端 API 数据聚合与扩展
- **修改文件**: [option_seller_manager.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
- **改动说明**:
  在 `get_status_summary()` 状态汇总接口中，查询当日条件单流并将 `status == 'TRIGGERED'` 的记录聚合为 `triggered_orders_list`：
  - 提取字段：`id`, `created_date`, `created_time`, `trigger_symbol`, `trigger_condition`, `trigger_price`, `spread_action`, `risk_profile`, `dte`, `groups`, `fallback_mode`, `status`, `triggered_at`, `executed_spot`, `executed_trade_ids`, `notes`, `source`。
  - 按 `triggered_at` 倒序排列。
  - 在接口返回中提供 `triggered_conditional_orders` 列表以及 `triggered_conditional_orders_count` 计数。

### (2) 前端待触发条件单增加结构化拷贝功能
- **修改文件**: [bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html)
- **改动说明**:
  - 在待触发条件单卡片的操作列中增加 `<button class="btn btn-secondary" onclick="copyConditionalOrderInfo(${o.id}, this)"> <i class="fas fa-copy"></i> 拷贝</button>`。
  - 实现 `copyConditionalOrderInfo(orderId, btn)` 函数，使用纯文本格式规范输出条件单挂单编号、状态、标的、触发规则、触发阈值、标的现价、相差点数、执行策略、风险等级、DTE、组数、降级模式、创建时间、策略备注等。
  - 复制成功后按钮自动切换为 `<i class="fas fa-check"></i> 已拷贝` 并于 1.5 秒后复原。

### (3) 新增【已触发条件单监控】卡片区与展开/收起持久化
- **修改文件**: [bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html)
- **改动说明**:
  - 在待触发条件单监控（Pending Conditional Orders）正下方插入 `<section id="triggeredConditionalSection">`，采用护眼浅色主题（Light Theme，白底灰边框与清爽绿/蓝标签）。
  - 标题栏配备闪电图标、复制标题链接按钮、动态触发单数徽章（`#triggeredCondBadge`）以及【展开/收起】切换按钮。
  - 动态渲染今日已触发条件单卡片：
    - 展示挂单编号、创建时间、规则模式（如 `SPY ≤ 758.67`）、已触发徽章、策略方向、风险档、DTE、组数。
    - **触发执行结果**：清晰列出实际触发时标的现价（如 `触发价: $758.60`）、触发时间戳（如 `09:23:39`）、生成的交易持仓 Chips（如 `#306, #307`）、降级模式。
    - **已执行开仓计划**：展示执行策略与双批次阶梯止盈配置。
    - **操作栏**：提供【拷贝】（拷贝触发后的执行结果与结构化文本）与【详情】（打开模态框 Console 审查原始 JSON 与上下文）按钮。
  - 实现 `toggleTriggeredConditional(evt, force)`：默认保持展开，并自动将折叠偏好记忆至 `localStorage ('bbt_triggered_conditional_expanded')`。

---

## 3. 验证与测试结果

### (1) API 验证
执行接口验证，验证今日已触发条件单（例如挂单 `#69`）的完整数据：
```json
{
  "triggered_conditional_orders_count": 1,
  "triggered_conditional_orders": [
    {
      "id": 69,
      "created_date": "2026-09-18",
      "created_time": "07:16:15",
      "trigger_symbol": "SPY",
      "trigger_condition": "LTE",
      "trigger_price": 758.67,
      "spread_action": "BULLISH",
      "risk_profile": "BALANCED",
      "dte": 0,
      "groups": 1,
      "fallback_mode": "CREDIT",
      "status": "TRIGGERED",
      "triggered_at": "2026-09-18 09:23:39",
      "executed_spot": 758.6,
      "executed_trade_ids": [306, 307],
      "notes": "Auto-Armed Range Lower: SPY LTE 758.67 (L1=758.67, Moat Short Put <= 758.67 | Pos=7.4%) [SubScenario: RANGE_BOUND_LOWER_BOUNDARY] [QPLevel: L1] [L1H1: true] [Anchor: 758.67] [Groups=1] [TP=CONSERVATIVE]",
      "source": "AUTO"
    }
  ]
}
```
**结果**: 接口正常返回已触发单全部字段与关联交易持仓号 `[306, 307]`。

### (2) 单元测试
运行 Option Seller 单元测试集：
```bash
PYTHONPATH=.:PyTools /usr/local/bin/python3 -m unittest PyTools/option_seller/test_leg_cancellation_merge.py
```
**结果**: `Ran 2 tests in 0.085s. OK.` 全部通过，无回归隐患。

### (3) 前端页面渲染与函数加载测试
验证页面中注入的元素与函数：
- `triggeredConditionalSection`: True
- `copyConditionalOrderInfo`: True
- `toggleTriggeredConditional`: True

---

## 4. 规范归档
- **归档目录**: `/Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/91_2026-09-18_Option_Seller_Conditional_Order_Copy_And_Triggered_List/`
- **系统总览**: 更新 `bbt_trading_modules.html` 中的 M12 模块演进历程与超链接。
