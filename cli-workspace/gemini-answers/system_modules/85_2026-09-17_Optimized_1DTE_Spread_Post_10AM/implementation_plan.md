# RTH 后半程（10:00 PST 后）0DTE 自动回退至优化 1DTE Spread 实施计划

- **日期**：2026-09-17
- **模块编号**：85
- **所属系统**：Option Seller 自动化交易引擎与开仓仲裁系统（期权结构选型与到期自适应）

## 1. 目标与背景
在美西时间 10:00 PST（美东 13:00）之后，0DTE 远虚值期权权利金由于极限 Theta 衰减迅速贴近最低报价地板（$0.01~$0.02），无法满足全局最低 $0.10 的开仓门槛。
若回退到 1DTE 时依然沿用早盘 0DTE 的标准参数（Delta 0.16、宽度 2.0、安全垫 0.45%），由于次日到期合约在日内下午的远虚值时间价值衰减极慢、买卖腿 Greeks 互相对冲，会导致开出 Delta 仅 ~0.10、权利金约 $0.15 的鸡肋单（如 2026-09-17 流水 #3 SPY 0918P-753+751，持仓 2 小时在标的顺势上涨下权利金几乎不降）。

本次改动旨在实现「RTH 时间感知动态策略」：
美西时间 >= 10:00 PST（或显式开启），当 0DTE 净权利金不足（< $0.10）回退到 1DTE 时，自动使用 **优化版 1DTE Spread 配置**：
1. **Target Delta**: 提升至 `0.24`（区间 0.22 ~ 0.26，更靠近主波段，提升 Delta 灵敏度）；
2. **价差宽度 Width**: 扩大至 `3.0 点`（从 2.0 点扩大至 3.0 点，减少买腿对冲，Net Theta 翻倍至 -0.42）；
3. **最低净权利金 Min Credit**: 提升至 `>= $0.25`（实盘稳定获得 $0.35 ~ $0.45）；
4. **安全垫 Cushion**: 调整为 `>= 0.35%`（SPY 留出 4.5 ~ 6.0 点安全距离）；
5. **标记留痕**: 候选字典标记 `'optimized_1dte': True`。

## 2. 涉及代码与文档
- `PyTools/option_seller/option_seller_engine.py`
- `bbt_data_web/data_app/bbt_option_seller.py`
- `PyTools/option_seller/test_optimized_1dte_post_10am.py`
- `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md` & `.html`
- `bbt_trading_modules.html`
