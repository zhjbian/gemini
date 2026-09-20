# 全局最晚平仓线由 12:30 调整为 12:45 PST 实施计划 (Implementation Plan)

## 1. 需求背景与核心目标
- **业务痛点**：原最晚时间止损点设定在 `12:30:00 PST`（美东 15:30），距离收盘仍有 30 分钟。对于 0DTE 价差，最后半小时是 Theta 衰减最陡峭的区间；在 12:30 强平时，虚值期权仍残留 $0.03~$0.04 成本，被迫支付多余平仓金；对于 10:00 之后开立的 1DTE 或中盘仓位，持仓时间被压缩至不足 2 小时，难以消化时间价值。
- **调整目标**：将全局最晚平仓线统一由 `12:30:00 PST` 调整为 `12:45:00 PST`（美东 15:45:00）。
- **风控优势**：
  1. 提前于美东 15:50（美西 12:50 PST）MOC（Market On Close）巨额订单不平衡公布前 5 分钟安全离场，规避尾盘剧烈跳空与脉冲；
  2. 预留 15 分钟充足的券商 API 挂单、追单及对账容错窗口；
  3. 彻底规避券商风控台（Risk Desk）在 15:45-15:50 针对行权分派（Pin Risk）的机器强制市价介入。

## 2. 变更范围
- `PyTools/option_seller/option_seller_manager.py`:
  - 增加类常量 `TIME_STOP_START_PST = "12:45:00"`, `TIME_STOP_END_PST = "13:15:00"`；
  - 判定逻辑更新为 `(self.TIME_STOP_START_PST <= current_time_str <= self.TIME_STOP_END_PST)`；
  - 同步更新文档注释与日志说明。
- `PyTools/option_seller/option_seller_notifier.py`:
  - 邮件通知标题及文案由 12:30 更新为 12:45。
- `bbt_data_web/templates/bbt_option_seller.html`:
  - 前端控制台卡片描述与步骤说明更新为 12:45 PST。
- 规则手册同步更新：
  - `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md` & `.html`。
- 测试验证：
  - `PyTools/option_seller/test_time_stop_1245.py`。
