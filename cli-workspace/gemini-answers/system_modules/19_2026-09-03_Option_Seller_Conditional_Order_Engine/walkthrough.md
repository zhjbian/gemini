# Option Seller 条件开仓控制台与触发展开引擎验收报告 (Module 19 Walkthrough)

- **模块标识**: `19_2026-09-03_Option_Seller_Conditional_Order_Engine`
- **交付日期**: `2026-09-03`
- **实施状态**: 已完成并通过全链路验证 (Verified & Delivered)

## 1. 交付目标与完成情况
本次迭代在期权卖家系统（Option Seller）中完整落地了**价格触碰条件开仓**能力，使交易员可以预埋 ES、SPX 或 SPY 关键点位触发单。

| 核心组件 | 状态 | 成果简述 |
| :--- | :---: | :--- |
| **前端导航与控制台** | **已完成** | 在【⚡ 手动开仓】后增设【🎯 设置条件开仓】按钮，支持弹窗配置标的、条件、点位、方向与风格。 |
| **实时点位与距离测算** | **已完成** | 前端每 4 秒轮询获取当前标的现价，实时动态计算距离目标点位绝对点数与百分比。 |
| **挂起条件单列表** | **已完成** | 弹窗内实时渲染今日挂起条件单，显示状态（监控中/已触发/已取消），支持一键撤单。 |
| **数据持久化与模型** | **已完成** | 新增 `order_flow_option_seller_conditional_orders` 表，ORM 与 DB Query CRUD 完备。 |
| **后台 10s 守护线程触发** | **已完成** | 在 `OptionSellerManager` 守护线程中自动比对实时价格并防重入触发执行 `open_trade`。 |
| **端到端 API 联调** | **已通过** | 创建、查询、取消、价格轮询接口均通过自动化测试，返回 HTTP 200。 |

## 2. 核心架构变更一览

### 2.1 数据库与 ORM 模型
在 [`bbt_data_web/models.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py) 中新增了 `OptionSellerConditionalOrder` 类：
- `trigger_symbol`: `ES` / `SPX` / `SPY`
- `trigger_condition`: `GTE` (`>=`) / `LTE` (`<=`)
- `trigger_price`: 目标触发点位（Decimal 10, 2）
- `spread_action`: `BULLISH` (看多卖 Put) / `BEARISH` (看空卖 Call)
- `risk_profile`: `CONSERVATIVE` / `BALANCED` / `AGGRESSIVE`
- `dte`: `0` / `1`
- `status`: `PENDING` / `TRIGGERED` / `CANCELLED`

### 2.2 后台管理器触发引擎
在 [`PyTools/option_seller/option_seller_manager.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py) 中：
- 新增 `get_live_spot_price(symbol)` 静态方法，实时获取 ES、SPX、SPY 价格；
- 新增 `_reload_conditional_orders()`，服务启动时加载挂起条件单；
- 在 `_monitor_loop()` 中新增 `_evaluate_conditional_orders()`，对达到价格阈值的条件单立即寻优期权链并执行双批次开仓（标记 `trade_mode: CONDITIONAL`）。

### 2.3 Web Controller 接口
在 [`bbt_data_web/data_app/bbt_option_seller.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_option_seller.py) 中新增：
- `GET /api/option_seller/conditional_orders`: 查询今日条件单列表；
- `POST /api/option_seller/conditional_order/create`: 提交创建条件单；
- `POST /api/option_seller/conditional_order/cancel`: 撤销挂起条件单；
- `GET /api/option_seller/current_spot_quotes`: 查询最新现价支持前端控制台展示。

### 2.4 UI 界面与交互体验
在 [`bbt_data_web/templates/bbt_option_seller.html`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html) 中：
- 严格遵循**浅色主题 (Light Theme)**；
- 增加湖蓝色渐变【🎯 设置条件开仓】按钮；
- 弹窗内置 6 大交互区域（标的选择、规则与点位、动作与风格、DTE与降级、实时挂起单列表及提交按钮）。

## 3. 验收验证记录

### 3.1 数据库与本地单元验证
```bash
Manager loaded successfully!
Live Quotes:
  ES: 7754.0
  SPX: 7744.41
  SPY: 772.78
Created test conditional order #: 1
Pending in DB: [1]
Cancelled test conditional order: True
Pending after cancel: []
```

### 3.2 运行环境 API 联调
- `GET /api/option_seller/current_spot_quotes`: 返回 HTTP 200，ES / SPX / SPY 现价正常输出；
- `POST /api/option_seller/conditional_order/create`: 返回 HTTP 200，条件单创建成功；
- `POST /api/option_seller/conditional_order/cancel`: 返回 HTTP 200，条件单撤单成功。
