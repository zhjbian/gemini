# 验收报告：同合约单腿相消合并自动撤单、独立被取消区展示与开仓类型继承定义

## 1. 概述与交付成果

本次交付彻底解决了在同一标的、同到期日开出多笔垂直价差时，因券商底层净额相消（Netting）导致中间单腿归零、原限价止盈单被误当成反向新开仓（`BUY_TO_OPEN`）的致命风控隐患。同时完成了活跃监控区提纯、被撤销单独立成区、以及合成新价差继承原始开仓类型的需求。

系统现已具备全自动闭环能力：
1. **自动识别相消重叠**：实时检测同标的、同到期日、同方向的在管价差中单腿重叠相消拓扑（如 757P/755P + 755P/753P，中间 755P 归零）。
2. **紧急撤销 TOS 旧挂单**：第一时间自动撤销涉及该相消组合的所有 `WORKING` 限价止盈单与止损单，彻底消除反向开仓与保证金错乱风险。
3. **系统账本原子重构**：将原始交易打标为 `MERGED_REPLACED`（保留完整审计与溯源链路），移出在管内存。
4. **合成实际净持仓新单并继承原始开仓类型**：
   - 以券商实际持仓为准，合成全新垂直价差（如 757P/753P），自动计算加权净权利金（$0.29）与最大亏损（$3.71），严格维持双批次架构（批次 1 占 2 手、批次 2 占 2 手）。
   - **类型继承机制**：合成单严格从被吸收的原始单继承 `trade_mode`、`trigger`、`origin`、`quant_pivot_level` 与 `profile`。若原始为纯手动开仓，则合成单正确标记为 `[纯手动单]` / `[手动]`，绝不错误回退为默认的 `[自动 5分钟综合信号]`；若原始为条件单或特定自动机制，则保持对应机制属性。
5. **全新双批次止盈与止损追踪**：
   - 批次 1（40% 衰减，目标价 $0.17）：向 Schwab 提交限价买回平仓单（实盘已触发止盈成交，锁定 +$24.00 盈利）；
   - 批次 2（75% 衰减，目标价 $0.07）：向 Schwab 提交限价买回平仓单（当前实盘 `WORKING` 监控中）；
   - 本地 10s 监控循环无缝接管实时 mark 刷新、220% 止损保护与 30% 浮盈保本移位。
6. **前端监控区分离（UI 浅色主题规范）**：
   - **活跃持仓监控 (Active Spread Monitor)**：仅展示真实在管的合并后净持仓，剔除所有状态为 `MERGED_REPLACED` 或已被取消的旧单。
   - **因合并被取消的单 (Cancelled Due to Merge)**：紧邻活跃持仓监控下方，单独开辟独立卡片区（浅紫护眼风格），专门展示因中间单腿相消而在券商被取消的旧单明细与合并去向。

---

## 2. 核心修改清单

| 模块 / 文件 | 关键修改点 |
| :--- | :--- |
| [`PyTools/option_seller/option_seller_manager.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py) | 1. 新增 `_detect_and_handle_leg_cancellations()` 与公开接口；<br/>2. 自动化撤销券商端相关订单；<br/>3. **从被合并原始单提取并继承** `trade_mode`, `trigger`, `origin`, `profile`；<br/>4. `get_status_summary()` 中将 `active_positions` 与 `merged_cancelled_positions` 严格分流；<br/>5. `_reload_active_trades()` 中补齐 `trigger` 与 `origin` 属性映射。 |
| [`bbt_data_web/db_query_module/db_query_option_seller.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/db_query_module/db_query_option_seller.py) | 1. 新增 `option_seller_trade_mark_merged()`：将原始单原子更新为 `MERGED_REPLACED`、结算 PnL 为 0 并记录合并元数据；<br/>2. 新增 `option_seller_trade_update_evidence()`：支持动态合并更新 `entry_evidence`。 |
| [`bbt_data_web/data_app/bbt_option_seller.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_option_seller.py) | 新增接口 `POST /api/option_seller/resolve_leg_cancellations`，支持手动或前端一键触发相消合并。 |
| [`bbt_data_web/templates/bbt_option_seller.html`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html) | 1. 新增 `.pos-group-card-merged` 与 `.pos-card-merged` 浅紫卡片样式；<br/>2. 新增 `<section id="mergedCancelledSection">` 独立挂载在活跃监控下方；<br/>3. JS `renderStatus()` 分流渲染 `positions` 与 `merged_cancelled_positions`；<br/>4. 完善 `getTradeCategory()` 逻辑，正确展现继承的类型标签。 |
| [`PyTools/option_seller/test_leg_cancellation_merge.py`](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/test_leg_cancellation_merge.py) | 单元测试覆盖：Bull Put 4手双批次相消、Bear Call 相消、旧挂单撤单、新止盈单提交、开仓类型继承断言及幂等性验证。 |

---

## 3. 验证结果

### 自动化单元测试验证

运行命令：
```bash
/usr/local/bin/python3 -m unittest PyTools/option_seller/test_leg_cancellation_merge.py
```

执行结果：
```
[TEST GUARD] 已安装测试隔离：拦截 7 个券商写方法、14 个数据库写方法、静音 2 个通知方法；测试日志 -> /var/folders/.../bbt_option_seller_test.log
[TEST GUARD] DbQuery.option_seller_trade_add() no-op -> fake id 900001
.[TEST GUARD] DbQuery.option_seller_trade_add() no-op -> fake id 900002
[TEST GUARD] DbQuery.option_seller_trade_add() no-op -> fake id 900003
.
----------------------------------------------------------------------
Ran 2 tests in 0.156s

OK
```

核心断言全部通过：
1. 继承断言：
   - 批次 1 与批次 2 成功继承原始开仓类型：`trade_mode == 'MANUAL'`、`trigger == 'MANUAL_UI_SCAN'`；
   - `entry_evidence` 内的 `trade_mode` 与 `trigger` 一致继承。
2. 实盘状态接口 `/api/option_seller/status?force_refresh=true` 验证：
   - `active_positions`：数量为 1（仅剩在管的批次 2 #305，批次 1 #304 已顺利止盈离场锁定盈利）；
   - `merged_cancelled_positions`：数量为 10（清晰归入因合并撤销单独区域）；
   - 交易属性：`trade_mode = MANUAL`，`trigger = MANUAL_UI_SCAN`，`origin = MANUAL`，前端分类权威映射为 `MANUAL`（纯手动单）。

---

## 4. 2026-09-18 增量交付：因合并被取消的单 (Cancelled Due to Merge) 折叠与展开交互

根据用户需求，在页面 `http://127.0.0.1:5005/bbt_option_seller` 中将【因合并被取消的单 (Cancelled Due to Merge)】模块改造为**支持展开与收起**：
1. **默认收起 (Default Collapsed)**：默认隐藏大量历史相消撤销单卡片，保持活跃持仓监控区清晰聚焦，不再挤占页面垂直空间；
2. **轻量交互与持久化**：
   - 标题栏右侧提供 `[展开 / 收起]` 按钮（配合 `fa-chevron-right` / `fa-chevron-down` 图标与文本）；
   - 点击标题栏整体亦可直接触发折叠/展开；
   - 用户操作状态自动持久化至浏览器的 `localStorage`（键名 `bbt_merged_cancelled_expanded`），页面 5s/10s 定时刷新或手动刷新时保持用户所选状态，绝不突兀跳动；
3. **视觉设计规范**：
   - 严格遵照 Light Theme 清爽浅色风格，浅紫主题胶囊标记撤单总数（如 `10 单已撤销`）。
