# SPX 0DTE Gamma 实时分析与信号系统实现报告

本报告汇总了为大盘 SPX 0DTE Gamma 日内走势开发并部署的实时分析与持久化信号系统的细节。

---

## 1. 变更点汇总

### 1.1 数据库结构变更
#### [bbt_data_web/models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py)
* 新增 `SpxGammaSignal` 模型，字段涵盖 SPX Spot 价格、零 Gamma 翻转价、多空失衡比率、做市商对冲方向与主力目标 Strike，以及 `verdict`（包含 AI 生成的专业市场评论与策略）。

### 1.2 核心量化引擎设计
#### [PyTools/quantdata/spx_gamma_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/quantdata/spx_gamma_analyst.py) [NEW]
* **Rule-Based 核心计算逻辑**：
  * **零 Gamma 翻转线**：寻找平值两侧 `net_gamma` 从正转负或从负转正的交界行权价中距离标的最接近的一个。
  * **主力墙与集群**：寻找最大 Call 墙 (GEX 最正) 与 Put 墙 (GEX 最负)，并累积周边 5 个 strikes 的 Gamma。
  * **方向判断**：结合当前标的价格所在的 Regime（正 Gamma / 负 Gamma）与失衡比率（Imbalance Ratio），映射预测方向。
  * **主力墙滚动迁移 (Migration Shift)**：计算当前与 30 分钟前的墙体位移，捕捉多空重心的前瞻指引信号。
* **Gemini AI 智能推演模式**：
  * 通过 `--ai` 标志启动，将上述定量数据打包为 Prompt，调用 `BBAI.call_gemini`（遵守 API 调用秘钥与包装规则），在美东 14:00 时间价值加速耗尽（Charm/Theta）等背景下，撰写严谨专业的中文市场微观结构评论。
* **数据库持久化**：
  * 采用 `ON DUPLICATE KEY UPDATE` 逻辑自动完成 upsert 保存。

### 1.3 定时调度集成
#### [PyTools/daily_jobs.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/daily_jobs.py)
* 增加了 `run_spx_gamma_analysis_job` 函数，利用 `--ai` 对 0DTE Gamma 在日内 RTH 的 13 个时间段（07:00 至 13:05）进行定时触发分析，持久化写入数据库。

### 1.4 Web 端数据接口对接
#### [bbt_data_web/data_app/bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py)
* 新增路由 `/data/spx_gamma_decision`。支持前端传入 `date`、`time` 参数提取特定时段的 Gamma 信号，并且支持添加 `trigger_ai=1` 参数动态拉取最新的 SPX 盘面实时运行一遍 AI 研判。

---

## 2. 系统验证结果

### 2.1 规则定量（Rule-Based）模式校验
控制台测试运行：
```bash
/usr/local/bin/python3 -W ignore PyTools/quantdata/spx_gamma_analyst.py
```
**输出结果**：
* 成功提取 2026-06-05 的最后一笔 0DTE 数据 (13:00:00)。
* 从 `yfinance` 捕获到最近成交价 `$7,384.67`。
* 算得零 Gamma 线为 `$7,387.50`，Regime 为 Negative Gamma。
* 多空主力墙滚动检测成功（多头墙下滚30点至 `$7,390`，空头墙下滚15点至 `$7,385`）。
* 输出规则判词：
  ```
  - **多空方向:** Bearish
  - **重要关注价格:** 零Gamma线: $7,388, 多头墙: $7,390, 空头墙: $7,385
  - **实战交易策略:** 目标参考点位 $7,385，防御关卡 $7,388
  ```

### 2.2 智能推演（AI-Powered）模式校验
控制台测试运行：
```bash
/usr/local/bin/python3 -W ignore PyTools/quantdata/spx_gamma_analyst.py --ai
```
**输出结果**：
* 触发 `BBAI` 使用 `gemini-3.5-flash` 模型推演。
* **AI 生成 Verdict 判词片段**：
  > **[VERDICT]**
  > - **多空方向:** 看空 (空头主控) - 标的价格（$7,384.67）已跌破零 Gamma 换向线（$7,387.50），市场处于负 Gamma 放大波动格局，且多空主力墙在过去 30 分钟内发生显著向下共振迁移。
  > - **重要关注价格:** $7,387.50（零 Gamma 分水岭/多空强弱分界线）, $7,385.00（空头主力墙/日内强支撑与磁吸定价目标）, $7,390.00（多头主力墙/反弹阻力位）
  > - **实战交易策略:** 顺势买入看跌期权（Buy Put）或建立 Delta 偏空组合，参考目标价位 $7,385.00，防御关卡 $7,390.00
  > - **信心指数:** 4
  >
  > **[MARKET_ANALYSIS]**
  > 当前标的资产价格（$7,384.67）已运行于零 Gamma 线（$7,387.50）下方，确认做市商整体处于负 Gamma 风险敞口。在此状态下，做市商的 Delta 动态对冲机制呈现顺趋势的“正反馈”特征，即标的价格下跌时，做市商必须被动卖出基础资产以对冲其多头 Delta 的流失，这在客观上将放大市场的下行势能。

### 2.3 Web API 接口校验
对 `http://127.0.0.1:5005/data/spx_gamma_decision` 请求：
```json
{
  "signal": {
    "bearish_cluster_gamma": -128235050262.0,
    "bullish_cluster_gamma": -146528734750.0,
    "created_at": "2026-06-06 19:07:01",
    "direction": "Bearish",
    "id": 1,
    "imbalance_score": 1.143,
    "is_ai_analysis": true,
    "signal_date": "2026-06-05",
    "signal_time": "13:00:00",
    "spot_price": 7384.67,
    "target_strike": 7385.0,
    "ticker": "SPX",
    "verdict": "[VERDICT]...",
    "zero_gamma_level": 7387.5
  },
  "source": "db",
  "success": true
}
```
验证确认，API 路由、数据库提取和过滤逻辑均工作正常。

### 2.4 前端 UI 与交互校验
* **回测（Backtest）按钮关联**：在 [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) 中重构了 `fetchRealtimeSignals` 逻辑。点击后，前端在获取 Gamma 图表的同时，将向 `/data/spx_gamma_decision` 异步拉取 SPX Gamma 分析指标，并直接渲染至大图下方的 **SPX 伽马量化指标面板**（包括 SPX 现价、零 Gamma 线、失衡比率、集群 GEX 以及当前多空方向判定）。
* **多空主力集群 Gamma 比率转换**：
  * 为保证底层数据库数据结构的纯净性，保留 DB 中 `imbalance_score` 的原始浮点数值（如 `0.054`）和原始 `verdict` 文本。
  * 在页面加载与 AI 研判渲染阶段，通过前端 JS 进行动态比率计算：
    * 当 $\text{imbalance\_score} < 1.0$ 时，比率为 `1 : 1 / score`（Put 占优，看跌红标）；
    * 当 $\text{imbalance\_score} \ge 1.0$ 时，比率为 `score : 1`（Call 占优，看涨绿标）。
  * 引入定性分档分析：
    * `1:1`：多空平衡
    * 比值超过 `5`：低度失衡
    * 比值超过 `10`：中度失衡
    * 比值超过 `15`：重度失衡
  * 动态着色：根据多空占优方向对比率及定性标签渲染为相应的红色（Bearish）或绿色（Bullish）。
* **AI 交易决策触发**：点击“AI交易决策”按钮将向后端传递 `trigger_ai=true`，动态执行 `spx_gamma_analyst.py` 中的 Gemini AI 分析流，并将分析得出的 `[VERDICT]` 与 `[MARKET_ANALYSIS]` 段落使用前端 Markdown 解析器渲染至紫色卡片中，实现了秒级动态研判输出。

![SPX Gamma UI ratio verification](/Users/zhijiebian/.gemini/antigravity-ide/brain/bc230b76-d6e6-4ce5-a9eb-67f7ac133e62/gamma_ratio_result_1780775282111.png)

---

## 3. 多空主力集群 Gamma 失衡比率（Imbalance Score）说明

### 3.1 计算公式与算法实现
该指标基于 SPX 0DTE 期权全链 Gamma 分布，计算多头与空头最核心集群的敞口相对强弱。其具体计算逻辑如下：

1. **寻找主力单点水位**：
   * **多头主力墙（S_max_bull）**：全链正 Gamma 敞口最大（即 Call 侧通常最集中）的行权价。
   * **空头主力墙（S_max_bear）**：全链负 Gamma 敞口绝对值最大（即 Put 侧通常最集中）的行权价。
2. **计算 5-Strike 集群和（Cluster Sum）**：
   为了防止单点噪音并评估机构主力在该行权价附近的防御深度，取主力行权价及其上下各 2 个行权价（共 5 个行权价）的 Gamma 敞口总和：
   * G_bullish_cluster = 围绕 S_max_bull 主力行权价附近 5 个 strikes 的 Gamma 累加和
   * G_bearish_cluster = 围绕 S_max_bear 主力行权价附近 5 个 strikes 的 Gamma 累加和
3. **计算失衡比率（Imbalance Score）**：
   `Imbalance Score = |G_bullish_cluster| / max(1.0, |G_bearish_cluster|)`
   *注：分母引入限制条件 >= 1.0 以防止极小敞口除零溢出。*

### 3.2 数值指标解读
以回测案例中出现的 **`0.054`**（即大约 5.4%）为例：

* **微观结构失衡**：这表明多头主力集群（以 Call 为主）的 Gamma 总额仅为负向空头主力集群（以 Put 为主）绝对总额的 5.4%。空头集群敞口规模是多头集群的约 18.5 倍。
* **做市商对冲动力学**：
  由于 SPX 现价处于零 Gamma 线下方（负 Gamma 区间），市场流动性主要由做市商的顺势对冲（Delta-hedging）支配。如此低的比率意味着多头侧几乎没有提供任何 Gamma 钉住效应（Pinning Effect）或吸附效应的缓冲垫。
  一旦价格逼近空头主力墙，做市商因 Delta 敏感度极速升高，必须加大抛售 SPX 期货的速度来维持 Delta 中性，极易引发价格向下加速（动能释放/击穿效应）。

---

## 4. 主力墙体日内滚动与位移（Migration Shift）计算说明

### 4.1 计算逻辑与时序对齐
系统追踪多空主力墙在日内交易时间段的相对位移，用以评估期权市场流动性重心的转移特征。其具体步骤如下：

1. **时序对齐（T - 30分钟）**：
   * **当前分析点 (T)**：进行回测或实时分析的目标时间点（例如 10:30）。
   * **基准对比点 (T_prev)**：固定设为当前时刻 30分钟前（即 T - 30分钟，例如 10:00）。
   * **查询窗口容差**：为保证在交易日内因数据跳变或缺失时仍可对齐，查询窗口设定为基准对比点前后的 +/- 5分钟范围内（即最接近的一笔历史 Gamma 记录）。
2. **定位历史与当前主力墙**：
   * **历史极值**：在 T_prev 对应的数据集中，遍历全链找出历史多头主力墙行权价（S_prev_bull，正 Gamma 敞口最大点）和历史空头主力墙行权价（S_prev_bear，负 Gamma 敞口绝对值最大点）。
   * **当前极值**：在当前时间点 T 对应数据中定位当前多头主力墙（S_curr_bull）和当前空头主力墙（S_curr_bear）及其对应敞口数值。
3. **计算位移与变化输出**：
   * `多头墙位移 = 当前多头墙行权价 - 历史多头墙行权价`
   * `空头墙位移 = 当前空头墙行权价 - 历史空头墙行权价`
   * **输出触发**：位移不为 0 时输出滚动状态，包含前后期权敞口强度的变化：
     > `多头主力墙（Bullish Wall）发生滚动：$7,500 (+$1.83B) → $7,550 (+$0.89B) (位移: +50.0点)`

### 4.2 物理指引作用
* **位移方向定性**：主力墙向上滚动（位移为正）代表交易者向上追逐或滚动 Call 期权，暗示上行防御阻力抬升或看涨意愿增加；向下滚动（位移为负）表示防御重心向下撤退。
* **敞口强度变化（如 +1.83B -> +0.89B）**：表明虽然主力水位上移，但集中在其上的对冲头寸强度减弱，指示新高点位处的筹码聚集支撑度正在稀释。

---

## 5. AI Analysis Result Table UI 升级说明

为了与实时订单流信号表 (`#signalsTable`) 的设计语言保持高度统一，现已将原有的独立卡片列表完全重构为**格式化统一数据表格 (Unified Data Table)**。

### 5.1 数据表格列项与展现维度
表格共有 4 个主要列：
1. **展开控制符 (Toggle)**：包含加号/减号图标，配合流畅过渡，用于快速展开或合拢对应判断维度的详细分析报告。
2. **判断项目 (Judgment Item)**：包含四大并列研判维度：
   * **综合方向判断**：期权分布与大单Delta流向的综合立场结论。
   * **SPX Gamma方向判断**：当前 SPX 0DTE 量化 Gamma 实时计算与滚动位移诊断结果。
   * **Order Flow大单方向判断**：大型主力机构的低位限价承接与高位阻力拦截大单行为。
   * **Order Flow实时盘面判断**：动态监测日内成交的微观 Delta 流速及主力抛压强弱。
3. **方向 (Direction)**：使用标准的趋势方向徽章（徽章圆边边框、淡色背景及方向箭头），以绿色（Bullish 向上箭头）或红色（Bearish 向下箭头）及橘色/中性色（Neutral 变体）统一渲染。
4. **简短的判断依据 (Brief Verdict)**：默认在折叠状态下，以单行截断（text-overflow: ellipsis）的形式展示精简依据。

### 5.2 交互与无缝平滑滑动
* **行悬停 (Row Hover)**：主判断行的悬停效果与主订单流信号表一致，使用淡灰蓝色的渐变提示。
* **平滑滑动展开/合拢 (Slide Toggle)**：点击主判断行或左侧控制按钮后，系统通过封装 `div.detail-wrapper` 进行 `.slideDown()` 或 `.slideUp()` 平滑过渡，完全规避了对 `<tr>` 元素直接应用滑动动画带来的浏览器渲染抖动或闪烁问题。
* **SPX Gamma 完整分析整合**：展开 `SPX Gamma方向判断` 后，将在详情内嵌展现结构化 Markdown 解析后的完整分析面板（包括做市商对冲影响与微观结构推演）。

![AI Verdict Table Collapsed View](/Users/zhijiebian/.gemini/antigravity-ide/brain/bc230b76-d6e6-4ce5-a9eb-67f7ac133e62/ai_analysis_collapsed_1780782722634.png)

![AI Verdict Table Expanded View](/Users/zhijiebian/.gemini/antigravity-ide/brain/bc230b76-d6e6-4ce5-a9eb-67f7ac133e62/ai_analysis_expanded_1780782737045.png)

---

## 6. SPX Gamma 格式优化与操作建议风险提示系统追加说明

在后续的升级中，我们对 SPX Gamma 信号进行了更深度的微观体验与风险控制优化：

### 6.1 关键价格二级列表化与英文项名 (Key Levels Nested List)
* **规范输出**：将“重要关注价格”修改为更符合 Markdown 树状图的二级列表形式。
* **项名英文统一**：
  * `* Spot: 7453.84`
  * `* 0 Gamma: 7498`
  * `* Call Wall: 7550 (+$0.89B)`
  * `* Put Wall: 7450 (-$14.93B)`

### 6.2 移除 SPX 价格符号与千分位 (Stripping Price Dollars & Commas)
* **纯数字呈现**：根据交易界面的极致简洁要求，所有输出、打印和渲染保持纯数字，一律移除了美元符号 `$` 和千分位逗号 `,`。
* **图表画图同步**：同步更新了后端 Matplotlib 自动渲染图的标题与 X 轴刻度展示。
* **金额敞口保留**：严格区分价格与敞口量，括号中的敞口敞口值（如 `+$0.89B`）依旧规范保留 `$` 符号。

### 6.3 研判方向汉化与高级着色 (Verdict Direction Styling)
* **智能映射**：前端渲染器在读取 Verdict 文本时，会自动对“多空方向”的状态进行智能捕获，将 `Bearish` 映射为 `看空`，`Neutral-Bearish` 映射为 `中性偏空` 等，并保留其后面的描述信息。
* **高亮着色**：对不同方向做出了醒目的专业着色（看多/中性偏多为绿色，看空/中性偏空为红色，中性为橙黄色）。

### 6.4 操作建议与风险防范系统 (Operational Advice & Badges)
* **距离与空间量化**：后端新增了价格与目标主力墙距离计算逻辑。若现价与目标墙（Put Wall / Call Wall）距离极其临近（小于 12 点/约 0.16%），或者已经击穿主力墙时，系统会输出 `操作空间受限` 的警告并说明原因，防止用户高风险追多/追空。
* **前端高级徽章化**：在 Core Verdict 卡片中加入“操作建议”项目，并在前端对于 `操作空间受限`（红底白字警戒徽章）、`空间尚存`（绿底白字通行徽章）等状态使用专属 CSS 微章渲染，显著提升策略警醒度和微观视觉质感。
