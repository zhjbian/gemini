# 5分钟 SPX Gamma 多空分级评级引擎验收报告 (Walkthrough)

## 1. 模块核心目标与改动概述
本模块将原本三元粗粒度的 5 分钟 SPX Gamma 顺势单边信号（`Bullish`、`Bearish`）成功升级为四级精细化多空分级评级体系：
- **基础判定 (Level 0 Baseline)**：
  - 完全继承现有的第三层决策树判定：形态纯净度通过（变号 <= 2 次）、主力 Gamma 优势显著（>= 2.0x）、现价未撞入 8 点天花板/铁底禁区、顺势推进 Cushion 空间充盈达标（趋势日 >= 15点，非趋势日 >= 23点）、日内分位数处于安全区。满足基础判定即获 `Bullish_L0`（或 `Bearish_L0`）。
- **三大加分项 (Bonus Factors, 各得 1 分)**：
  1. **多空主力集群 Gamma 规模比率 >= 3.0**（`imbalance_score >= 3.0` 或空头 `bear_ratio >= 3.0`）；
  2. **开盘黄金布局时段 (06:30 - 08:30 PT)**（美西时间开盘前两小时主力建仓与爆发期）；
  3. **主力集群 Gamma 趋势整体上 Trend Up (持续扩张净注入)**（开盘以来集群规模节点样本 >= 2、终点显著大于起点、线性拟合斜率 `slope > 0` 且最新值处于序列高位）。
- **评级输出**：
  - 0 项加分：`Bullish_L0` / `Bearish_L0` (基准)
  - 1 项加分：`Bullish_L1` / `Bearish_L1` (强化)
  - 2 项加分：`Bullish_L2` / `Bearish_L2` (高确信)
  - 3 项加分：`Bullish_L3` / `Bearish_L3` (极强力主升/主跌浪)
- **约束保持**：严格未触发任何数据库历史全量回填，保障线上生产数据稳定不受干扰。

## 2. 核心落地文件与实现细节
1. **集群趋势评测引擎 (`PyTools/quantdata/trend_regime.py`)**：
   - 实现了 `evaluate_cluster_gamma_trend_up(history_nodes, side='bull')`：采用最小二乘法回归与高位边界检验，客观量化集群演化是否呈现整体 Trend Up。
2. **SPX Gamma 评级决策树 (`PyTools/quantdata/spx_gamma_analyst.py`)**：
   - 在进入顺势判定分支后，自动校验三大加分项并累加得分，生成 `Bullish_L0~L3:Bullish`（或 `Bearish_L0~L3:Bearish`）；
   - 更新 `risk_advice` 与判词 `verdict`，展示分级标签与加分项验证明细。
3. **Web 后端 API (`bbt_data_web/data_app/bbt_signals.py`)**：
   - 增强 `/data/spx_gamma_signals` 的方向过滤，支持前缀模糊匹配（选 `Bullish` 查出全部 L0~L3）以及单选特定分级。
4. **Web 前端渲染 (`bbt_data_web/static/js/bbt_signals.js` 与 `templates/bbt_signals.html`)**：
   - 为 `Bullish_L0` 到 `Bullish_L3` 渲染翠绿到高亮翡翠绿的渐进式徽章，为 `Bearish_L0` 到 `Bearish_L3` 渲染珊瑚红到深红高光徽章，严格保持 Light Theme 浅色风格；
   - 下拉框中扩展了具体分级选项。

## 3. 测试验证实证
1. **2026-09-03 07:30 单点实测（对应用户示意图演化过程）**：
   - 现价 7705.85，Call Wall 7740，Cushion 34.1 点；
   - 黄金时间 07:30 (满足)；
   - Call 集群从 4.3B 攀升至 17.6B，回归斜率 > 0 (满足)；
   - 集群比率 2.4 (未达 3.0)；
   - 得分: 2 分，**精准评定为 `Bullish_L2:Bullish`（顺势看多，L2高确信）**！
2. **2026-09-03 连续时点验证**：
   - 07:00: `Bullish_L2:Bullish`
   - 07:30: `Bullish_L2:Bullish`
   - 07:45: `Bullish_L2:Bullish`
   - 07:55: `Bullish_L2:Bullish`
   - 状态稳定输出高确信多头评级，与大盘主升浪走势完美共振。
