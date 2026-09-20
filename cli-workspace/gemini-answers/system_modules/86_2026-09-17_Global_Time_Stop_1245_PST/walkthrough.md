# 全局最晚平仓线由 12:30 调整为 12:45 PST 验收报告 (Walkthrough)

## 1. 概述
本演进完成了期权卖方交易系统（Option Seller）全局最晚强平时间止损线（Time Stop）的统一升级：将原 `12:30:00 PST` 顺延 15 分钟至 `12:45:00 PST`（美东 15:45:00），在 12:50 MOC 巨单风暴前安全离场的同时，最大限度榨取日内 Theta 归零价值。

## 2. 修改文件清单
1. `PyTools/option_seller/option_seller_manager.py`:
   - 增加常量 `TIME_STOP_START_PST = "12:45:00"`, `TIME_STOP_END_PST = "13:15:00"`；
   - 动态盯市循环中更新 `is_time_stop = (self.TIME_STOP_START_PST <= current_time_str <= self.TIME_STOP_END_PST)`；
   - 更新模块三重退出规则文档及行内注释。
2. `PyTools/option_seller/option_seller_notifier.py`:
   - 邮件通知标题由 `美西 12:30 时间强平完成` 更新为 `美西 12:45 时间强平完成`；
   - 状态说明更新为 `已达日内最晚持仓时间边界（12:45 PST），严格执行不隔夜原则市价清仓。`
3. `bbt_data_web/templates/bbt_option_seller.html`:
   - 更新前端第 3 步风控说明：`12:45 PST 强制时间全清`；
   - 更新手动开仓 0DTE 卡片说明：`美西 12:45 强平绝不过夜`。
4. 交易系统规则手册：
   - `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md` & `.html`
   - §3.3.4、§3.3.2、§3.3.3、§3.3.7 及中性宏观规则全面同步。

## 3. 测试验证
新增单元回归契约测试：`PyTools/option_seller/test_time_stop_1245.py`
- `test_time_stop_constants`: 验证常量准确配置为 `12:45:00` 与 `13:15:00`；
- `test_time_stop_boundary_eval`: 验证在 `12:44:59`、`10:13:00` 为 False；在 `12:45:00`、`12:50:00`、`13:15:00` 为 True；在 `13:15:01` 及夜间为 False；
- `test_evaluate_positions_triggers_time_stop_at_1245`: 验证到达 `12:45:05` 时精准触发 `CLOSED_TIME_STOP`；
- `test_evaluate_positions_does_not_trigger_time_stop_at_1244`: 验证在 `12:44:59` 时绝不误触发强平。
- 运行结果：**4/4 测试通过 (Ran 4 tests in 0.127s, OK)**。
