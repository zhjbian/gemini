# 5分钟多维共振期权卖方综合决策引擎实施计划 (5-Minute Multi-Factor Option Seller Synthesis Engine)

本方案旨在彻底解决此前期权卖方自动交易过于依赖“5分钟哨兵信号”与“单一HIGH确信度”导致的触发频率极低、策略错配与容易空转的问题。

通过以 **5 分钟为主周期（美西 06:35 至 11:30 PST 每 5 分钟检测一次）**，深度融合 **Order Flow 微观盘口、SPX 0DTE Gamma 结构、Smashelito Pivot 拍卖关键位与 15m/5m EMA 13-21 趋势防护盾** 四维要素，构建专属于期权卖方的双向（看多卖 Put / 看空卖 Call）稳态共振决策系统。

---

## 核心架构与决策流图 (Architecture & Decision Flow)

```
[美西 06:35 ~ 11:30 PST: 每 5 分钟定时心跳触发]
                  │
                  ▼
   [前置状态闸门: 当前是否绝对空仓?]
   ├── 已有活跃持仓 ──> [直接跳过，绝不加仓/绝不重叠]
   └── 当前绝对空仓 ──> [进入四维微观数据聚合]
                                │
                                ▼
        ┌─────────────────────────────────────────────────┐
        │ 1. 5m Order Flow: Delta、吸收、竭尽、失衡        │
        │ 2. SPX 0DTE Gamma: 现价 vs ZGL、Call/Put Wall   │
        │ 3. Smashelito Pivot: 核心 Pivot、阻力R / 支撑S   │
        │ 4. EMA 13-21: 15m 多空排列、5m 回踩均线企稳确认   │
        └───────────────────────┬─────────────────────────┘
                                │
                                ▼
                   [刚性一票否决安全过滤]
   ├── 5m DOM 虚假撤单陷阱 (is_spoof_trap) ──────> [REJECTED 拒绝]
   ├── 15m 趋势日反向逆大势 (Trend Day Shield) ──> [REJECTED 拒绝]
   └── 均线严重粘合多空混沌 (EMA Tangled) ───────> [REJECTED 拒绝]
                                │
                                ▼ [通过否决过滤]
              [四维共振打分与策略自适应匹配]
   ├── 四维全要素共振 (>= 75分) ─> ⚡ 激进型 (Aggressive: 宽2.0/Δ0.25/垫0.30%/权利金>=0.28)
   ├── 三维标准共振 (55~74分)   ─> ⚖️ 平衡型 (Balanced: 宽2.0/Δ0.16/垫0.45%/权利金>=0.18)
   ├── 双维偏弱共振 (40~54分)   ─> 🛡️ 保守型 (Conservative: 宽1.0/Δ0.10/垫0.60%/权利金>=0.08)
   └── 得分低于 40 分          ─> ❌ 拒绝入场 (REJECTED)
                                │
                                ▼ [QUALIFIED 状态]
               [嘉信实时期权链盘口最优报价锁定]
                                │
                                ▼
             [自动卖出 2 手双批次 0DTE 垂直价差]
                                │
                                ▼
       [无缝移交 10s 风控守护线程: 40%/75% 阶梯止盈 + 2.2x 硬止损 + 12:30 PST 强制时间全清]
```

---

## 拟修改与新增文件清单 (Proposed Changes)

### 1. 期权卖方决策算法层
#### [MODIFY] [option_seller_engine.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_engine.py)
* 新增核心方法 `evaluate_5m_synthesis_opportunity(...)`：
  * 输入参数：5m Order Flow 统计指标、SPX 实时 Gamma 数据、Smashelito Pivot 结构、15m/5m EMA 状态、趋势日状态；
  * 实现双向（Bullish / Bearish）对称的四维共振评分算法（满分 100 分）；
  * 强制执行三大刚性一票否决规则（Spoofing Trap、Trend Day Shield、11:30 PST 开仓截止）；
  * 根据得分自适应输出：`status` ('QUALIFIED' / 'REJECTED')、`direction` ('BULLISH' / 'BEARISH')、`recommended_profile` ('AGGRESSIVE' / 'BALANCED' / 'CONSERVATIVE') 与 `rationale`。

### 2. 交易管理与调度接入层
#### [MODIFY] [option_seller_manager.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
* 升级 `evaluate_and_auto_trade` 方法：
  * 支持接收 5 分钟四维综合上下文参数；
  * 保持第一层空仓状态硬锁：`if self.active_trades: return None`；
  * 成功仲裁后，调用 Schwab API 检索 SPY 0DTE 实时期权链，执行双批次立仓与 10 秒风控线程接驳。

### 3. 5分钟主周期驱动管道
#### [MODIFY] [order_flow_sentinel.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/order_flow_analysis/order_flow_sentinel.py)
* 在每个 5 分钟 bin 生成后，自动提取当前时间节点的最新 SPX Gamma 状态、当日 Smashelito Pivot 及 15m EMA 均线排列；
* 触发 `OptionSellerManager.get_instance().evaluate_and_auto_trade(...)`，实现无人值守常态化 5 分钟脉搏检测。

### 4. 交易系统规则手册与归档
#### [MODIFY] [system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html) & [.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md)
* 在第十七章（Option Seller Rules）第 8 节升级录入：**5分钟四维多因子共振决策模型**（包含打分规则、多空判定矩阵、三档策略映射与刚性一票否决表）。
* 同步更新镜像文件 `gemini-answers/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html` 与 `.md`。

#### [NEW] [system_modules/bbt_option_seller_5m_synthesis/plan.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_option_seller_5m_synthesis/plan.md)
#### [NEW] [system_modules/bbt_option_seller_5m_synthesis/walkthrough.md](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_option_seller_5m_synthesis/walkthrough.md)
#### [MODIFY] [system_modules/bbt_trading_modules.html](file:///Users/zhijiebian/.gemini/cli-workspace/gemini-answers/system_modules/bbt_trading_modules.html)
* 遵照规则 (10)，在系统模块总览中登记新 feature，更新技术栈标记与超链接直达。

---

## 验证与测试计划 (Verification Plan)

### 自动化单元测试 (Automated Unit Tests)
1. **多维度评分算法测试**：
   * 模拟看多四维全要素共振（Delta>0, Spot>ZGL, Price>Pivot, EMA13>21）➜ 验证输出 `QUALIFIED`, `BULLISH`, `AGGRESSIVE`, 得分 >= 75；
   * 模拟看空三维标准共振（Delta<0, Spot<ZGL, Price<Pivot, 均线缠绕）➜ 验证输出 `QUALIFIED`, `BEARISH`, `BALANCED`, 得分 55~74；
   * 模拟一票否决场景（`is_spoof_trap=True` 或 趋势日反向卖方）➜ 验证必须输出 `REJECTED`。
2. **持仓状态锁测试**：
   * 在已有持仓（`len(self.active_trades) > 0`）时调用评估，确认必须返回 `None` 且 0 次 API 请求。
3. **过去两周全量回测复算**：
   * 运行回测脚本，确认 10 天交易日内胜率与收益曲线符合预期。

### 人工验收标准
* 打开交易规则手册，确认表格、公式、多空对称逻辑完整渲染，无 LaTeX 乱码。
