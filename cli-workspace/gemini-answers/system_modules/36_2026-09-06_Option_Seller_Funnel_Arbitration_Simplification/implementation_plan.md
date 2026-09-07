# 期权卖方 5分钟后台全自动开仓四层漏斗仲裁机制 - 维度 2 (SPX Gamma 结构) 极简重构实施方案

## 1. 业务背景与问题分析
在既有的期权卖方 5分钟主周期全自动开仓四层漏斗仲裁机制中，“第二层：多维指标矩阵打分 (满分 100分)”下的“维度 2：SPX 0DTE Gamma 结构 (权重 30分)”原先包含三个繁琐细碎的子项计算：
1. **子项 1**：多空集群名义金额与比率 (Cluster & Ratio，满分 15分，分时动态校准：开盘至 07:30 门限 5B，07:30 后门限 15B，比率阶梯打分)；
2. **子项 2**：期权大墙物理屏障与距离安全垫 (Call/Put Wall Cushion，满分 10分，计算相对大墙的缓冲百分比)；
3. **子项 3**：大盘主方向基调与辅助状态 (Direction Baseline，满分 5分)。

随着系统模块 35（5分钟 SPX Gamma 多空分级评级引擎 `Bullish_L0~L3` / `Bearish_L0~L3`）的成功上线，SPX Gamma 的大墙安全垫（Cushion 校验与一票否决）、集群名义规模与比率、时段黄金窗口、集群走势 trend up 等微观物理结构，已经在 Gamma 子系统第三层决策树与多空分级引擎中完成了极其严密的一站式量化裁决。因此，期权卖方后台开仓引擎若再重复计算 Cushion 和比率，既冗余割裂，又难以直接利用最新的分级优势。

## 2. 实施目标与重构设计
彻底废弃子项 1、子项 2、子项 3 的冗长计算，实现开仓引擎维度 2 与 SPX Gamma 分级评级结果的直连映射：
- **看多（卖出 Bull Put Spread）**：
  - `Bullish_L0`: **20 分**（基准顺势推进，满足基础安全垫与做市商正 Gamma 约束）
  - `Bullish_L1`: **24 分**（具备单项加分强化，顺势动能增强）
  - `Bullish_L2`: **27 分**（具备两项加分，高确信主升浪，极佳开仓胜率保障）
  - `Bullish_L3`: **30 分**（三项加分全部成立，极强力爆发主升浪，满分保驾护航）
- **看空（卖出 Bear Call Spread，严格双向对称）**：
  - `Bearish_L0`: **20 分**
  - `Bearish_L1`: **24 分**
  - `Bearish_L2`: **27 分**
  - `Bearish_L3`: **30 分**
- **中性与做市商防守（严厉阻断）**：
  - `Neutral:...` 或方向相反：**0 分**。
  - 由于第二层开仓漏斗要求“维度 2 得分必须 >= 15 分（且全维度总分 >= 75 分）”，一旦 Gamma 处于冲顶/探底撞墙（`Exhaustion`）、空间压缩（`Compression`）或尾盘禁区（`Time-Cutoff`），维度 2 直接得 0 分，立即触发硬性一票否决，坚决捍卫卖方安全垫底线！

## 3. 影响范围与修改清单
1. **开仓决策引擎**: `PyTools/option_seller/option_seller_engine.py` 中的 `_calculate_resonance_score` 函数维度 2 评分逻辑；
2. **系统交易规则手册**:
   - `gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md`
   - `gemini-answers/system_modules/gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.html`
3. **系统模块管理中心**:
   - 登记模块 36 至 `bbt_trading_modules.html`，维护目录与全景时间线。
