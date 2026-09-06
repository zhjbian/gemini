# SPX Gamma 结构形态（极佳单边三角形态）前置硬性过滤引擎 实施计划

## 1. 目标与痛点背景
在期权卖方交易系统【场景一：大单边趋势日极限终点反向开仓 (Trend Day Terminal Exhaustion Reversal)】中，原有开仓机制依赖波幅大小（日内总振幅 >= 30点）、日内位置（处于极端顶峰 >= 80% 或深水 <= 20%）以及距离做市商单日 Max Gamma Bar <= 4.0 点作为前置条件。

然而，实盘数据表明：
- **优质单边形态（图 1）**：红柱与绿柱在横轴左右清晰分开（Flip 点为唯一界限），优势侧（如绿柱）呈现显著的单峰三角形态，且最大优势柱高度达到劣势柱的 2 倍以上。在此种形态下，Max Gamma Wall 具有极其强大的终结阻力与做市商钉住（Pinning）效应，反向开仓胜率极高；
- **劣质混乱形态（图 2）**：红柱与绿柱在横轴上穿插交错（如绿柱阵营中突兀耸立巨额红柱），多空拉扯剧烈，无清晰分界。即使点位暂时触及 Max Call Wall，行情也极易在多空博弈中被穿透打爆。

因此，系统亟需建立一套通用的 **SPX 净 Gamma 结构形态量化检测引擎**，作为场景一开仓与伏击单装配的刚性硬件级前置准入条件。

---

## 2. 核心量化算法设计（四维层级判定模型）

算法对看涨单边（摸顶卖 Call）与看跌单边（抄底卖 Put）实施完全对称的通用判定：

1. **红绿完全隔绝无穿插 (Clean Separation / Zero Interleaving)**：
   - 过滤尾部微小噪点（高度 < 10% 劣势峰值或 < 5% 优势峰值）；
   - 在核心价格活动区间（围绕现价 +- 120 点）内，符号变号次数 `Sign_Flips` 严格等于 1 次；
   - 劣势异色柱严禁突兀穿插进优势阵营内部（`Interleaved_Count == 0`）。
2. **优势方单峰三角形 (Dominant Triangle Peak Profile)**：
   - 优势侧必须具备唯一的明显主波峰，无高度接近的第二独立波峰（若次峰距离主峰 >= 15 点，主峰高度 / 次峰高度 >= 1.20）；
   - 整体呈现为正立或倒立的平滑收敛三角形：构造以主峰为顶点、核心集群两端为底脚的理论三角形包络线，计算实际 Gamma 分布与理论三角包络的相关度 `Triangular_Score >= 0.60`。
3. **绝对高度压制倍数 (Height Ratio >= 2.0x)**：
   - 最大优势柱绝对高度必须是最大劣势柱绝对高度的 2.0 倍以上（`Dominant_Peak / Opposite_Peak >= 2.0`）。
4. **Flip 分水岭零轴定位 (Zero Flip Junction)**：
   - Zero Gamma Flip 精确位于红柱倒立三角与绿柱正立三角在零轴上的交界处，两军阵线分明。

---

## 3. 涉及系统文件与实施范围

1. **核心算法库**：
   - 新建 `PyTools/py_lib/gamma_structure_detector.py`，提供 `analyze_gamma_profile_structure(strikes, exposures, spot_price)` 核心检测函数。
2. **期权卖方决策引擎集成**：
   - 更新 `PyTools/option_seller/option_seller_engine.py` 中的 `evaluate_counter_trend_boundary_opportunity`：在进入 Case 1A（摸顶卖 Call）与 Case 1B（抄底卖 Put）前，强制校验 Gamma 结构形态。若结构不达标（如穿插混乱或三角形态失败），直接在调试原因中否决开仓并拒绝挂载伏击单。
3. **数据管道与上下文传递**：
   - 更新 `PyTools/order_flow_analysis/comprehensive_signals_job.py`：在 `trigger_option_seller_from_30m` 中查询并携带底层 `strikes` 与 `exposures` 列表；
   - 更新 `PyTools/order_flow_analysis/order_flow_sentinel.py`：在 5 分钟哨兵中提取最新 Gamma 的 `strikes` 与 `exposures`。
4. **SPX Gamma 独立分析研判**：
   - 更新 `PyTools/quantdata/spx_gamma_analyst.py`：在运行中自动计算单边形态质量，并在输出研判结论（Verdict）及返回字典中增加 `SPX Gamma 单边形态检验` 字段。
5. **规则手册与索引归档**：
   - 更新 `gemini_answer-trading_system_rules_manual-2026-08-29_10-13-45.md` 与 `.html` 的场景一限定条款；
   - 更新 `bbt_trading_modules.html` 模块目录索引。
