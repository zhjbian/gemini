# 待触发条件单增加拷贝功能 与 新增已触发条件单展示区实施计划

本方案针对 http://127.0.0.1:5005/bbt_option_seller 的条件单模块进行两项增强：
1. **为待触发条件单卡片增加拷贝按钮**：一键复制结构化条件单关键信息（触发标的、触发阈值、现价距离、执行策略、来源属性、布防依据等）；
2. **在待触发条件单下方新增「已触发条件单 (Triggered Conditional Orders)」区域**：实时展示今日已触发开仓的条件单列表，包括触发时间、触发时标的成交价、关联生成的持仓单号（如 `#306, #307`）以及支持一键拷贝与查看详情。

---

## 用户需知与设计确认 (User Review Required)

- **已触发条件单展示范围**：展示今日（当前交易日）状态为 `TRIGGERED` 的条件单列表，按触发时间倒序排列（最新的在最上方）。
- **折叠展开交互**：为了保持页面整洁，新增的「已触发条件单」支持点击标题栏或右上角按钮折叠/展开（可默认展开或记住偏好）。
- **浅色主题规范**：严格遵循浅色（Light Theme）清新护眼风格，卡片采用淡绿/微青边框标识已触发状态，与待触发单的深蓝/橙色形成清晰视觉对比。

---

## 拟变更内容 (Proposed Changes)

### 1. 后端数据聚合与 API 拓展

#### [MODIFY] [`PyTools/option_seller/option_seller_manager.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
- 在 `get_status_summary()` 中，查询当日条件单中 `status == 'TRIGGERED'` 的记录；
- 格式化输出为 `triggered_conditional_orders` 列表，包含：
  - `id`, `trigger_symbol`, `trigger_condition`, `trigger_price`, `spread_action`, `risk_profile`, `dte`
  - `created_time`, `triggered_at`, `executed_spot`, `executed_trade_ids`, `notes`, `source` 等字段；
- 在返回字典中增加 `triggered_conditional_orders` 与 `triggered_conditional_orders_count`。

---

### 2. 前端界面与交互设计

#### [MODIFY] [`bbt_data_web/templates/bbt_option_seller.html`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html)
1. **待触发条件单卡片操作栏改造**：
   - 在每张待触发单的操作按钮组（原 `[详情]` `[撤单]`）中新增 `[拷贝]` 按钮（配合 `<i class="far fa-copy"></i>` 图标）；
   - 点击调用 `copyConditionalOrderInfo(orderId, this)`，将清晰格式化的文本写入系统剪贴板，并提供「已复制!」动态反馈。
2. **新增已触发条件单展示区域**：
   - 紧随 `pendingConditionalSection` 下方插入 `<section id="triggeredConditionalSection">`；
   - 标题栏包含：绿色闪电图标 `<i class="fas fa-bolt"></i>`、标题文本、状态徽标（如 `1 单已触发`）、说明文字以及 `[展开/收起]` 按钮；
   - 渲染容器 `<div id="triggeredConditionalList">`。
3. **已触发条件单卡片渲染逻辑**：
   - 展示触发点位、触发时间、触发时标的价（`executed_spot`）、关联生成的持仓单号（支持高亮跳转/识别）；
   - 卡片右侧配备 `[详情]` 和 `[拷贝]` 操作按钮。
4. **JavaScript 工具函数**：
   - 实现 `copyConditionalOrderInfo(orderId, btn)`，支持同时从 pending 字典和 triggered 字典中读取数据并格式化复制。
   - 实现 `toggleTriggeredConditional(evt, force)` 折叠展开交互。

---

## 验证方案 (Verification Plan)

### 自动化测试
- 运行 Option Seller 相关单元测试：
  ```bash
  /usr/local/bin/python3 -m unittest PyTools/option_seller/test_leg_cancellation_merge.py
  /usr/local/bin/python3 -m unittest PyTools/option_seller/test_live_resting_limit_order.py
  ```
- 运行 API 测试脚本，验证 `/api/option_seller/status` 是否返回 `triggered_conditional_orders` 且包含今日单号 `#69`。

### 人工验收（遵照规则 5，用户在浏览器中测试）
- 访问 `http://127.0.0.1:5005/bbt_option_seller`；
- 检查【待触发条件单监控】每张卡片右侧是否出现【拷贝】按钮，点击验证剪贴板内容是否准确；
- 检查下方是否新增【已触发条件单】区域，是否正确显示今日已触发的条件单 #69；
- 验证已触发单上的【拷贝】与【详情】按钮功能，以及区域折叠/展开效果。
