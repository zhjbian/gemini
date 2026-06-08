# SPX 目标水位距离量化与 UI 增强说明

根据最新需求，系统增强了对于股价距离目标主力墙的量化评估，并将此信息在 Core Verdict 以及 AI 决策表格中同步透出，为交易者提供直观的追涨杀跌空间防范指引。

## 1. 距离量化评估逻辑
在前端 [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) 中引入 `getDistanceDescription(spot, target)` 计算器：
* **情况1 (接近目标)**：当标的现价与主力墙（目标价位）的差值绝对值 $\le 12$ 点时，状态提示为：`已接近目标`。
* **情况2 (空间尚存)**：当差值绝对值 $> 12$ 点时，状态提示为：`距离目标 {diff} ({pct}%)`（其中 `diff` 与 `pct` 根据 `target - spot` 的方向带上明确的正负号 `+` / `-` 标识），例如：`距离目标 +15 (+0.17%)` 或 `距离目标 -15 (-0.17%)`。

## 2. UI 同步联动呈现
1. **多空方向汉化 (Localization)**：
   表格中的方向一列已全面汉化。原来展现英文 Badge（例如 `Bearish`、`Bullish` 等）统一汉化为 `'看空'`、`'看多'`、`'中性偏多'`、`'中性偏空'` 及 `'中性'`。
2. **临界目标位颜色去色处理 (Color Omission)**：
   若当前的分类描述为 `'已接近目标'`（即差值在 12 点以内），为了防范盲目追多追空，系统将对方向颜色采取去色处理：
   * **Core Verdict 中**：`多空方向: 看空 - 已接近目标` 的文字颜色从红色/绿色变为中性灰（`#64748b`）。
   * **AI 决策表格中**：`SPX Gamma方向判断` 的 Badge 颜色与文字全部变为中性灰色。
3. **两行分排显示 (Two-Line Layout)**：
   在 AI 决策表格中，方向一列（Row 2：SPX Gamma方向判断）分两行呈现以防止在狭窄列宽下被意外挤扁折行：
   * 第一行展示方向 Badge；
   * 第二行展示距离目标文本（包裹在独立的带有 `margin-top: 4px;` 的 `div` 中）。
4. **UI 代码具体引用**：
   * **Core Verdict**：`多空方向: 看空 - 已接近目标`
   * **折叠表行**：`${getDirectionBadgeHtml(spxDir, distDesc === '已接近目标')}${distDesc ? `<div style="font-size: 0.8rem; color: #64748b; font-weight: 500; margin-top: 4px;">${distDesc}</div>` : ''}`

---

## 3. 时序位移与主力集群变化数据扩展说明

将原本的单行文本“日内墙体滚动情况”重构扩展为更加精细与结构化的最后 30 分钟量化时序变动对比信息，这不仅在 Rule-based 模式下起效，也会作为推演素材传给 Gemini AI 引擎并在 `[VERDICT]` 的固定列表字段中抄录输出。

### 3.1 扩展的对比字段与格式
1. **最后30分钟Call/Put Wall移动**：
   展示多空主力墙位置与单点 GEX 敞口量在 30 分钟前后的变动以及具体差值。
   * **格式**：`* Call Wall: {prev_max_bull} ({prev_bull_val}) → {max_bull_strike} ({curr_bull_val}) ⇒ ({strike_diff:+.0f}, {gex_diff_str})`
   * **示例**：`* Call Wall: 7510 (+0.92B) → 7550 (+0.89B) ⇒ (+40, -0.03B)`
2. **最后30分钟主力集群Gamma变化**：
   展示多空 5-strike 主力集群的总 Gamma 敞口值变动。
   * **格式**：`* Call主力集群: {prev_bull_cluster} → {curr_bull_cluster} ⇒ {cluster_diff}`
   * **示例**：`* Call主力集群: 11.5B → 12.0B ⇒ +0.5B`

### 3.2 引擎实现细节
* **时序容差与防空处理**：保留 30 分钟对齐和 5 分钟时间窗口查询机制。若没有上一时段的数据，系统将自动将 30 分钟前的数值设为当前最新数值，使输出差值为 `+0` 或 `+0.00B`，保证在全天任何时段（包括开盘首半小时内）均有稳定统一的结构化渲染输出。
* **Gemini Prompt 约束升级**：在给 AI 发送的 Prompt 中，通过显式强指令约束 AI 必须原封不动地完整抄录输出 `[VERDICT]` 模板中的这两个列表行，从而防止 AI 模型对高频量化指标产生自我发挥或漏掉格式。

---

## 4. 数据库层 QdGamma 映射模型定义说明

为了与量化 ingester 阶段自动抓取入库的 SPX 0DTE 全链原始 Gamma 数据相吻合，在 `bbt_data_web/models.py` 中为 `qd_gamma` 数据表建立了对应的 SQLAlchemy 模型类 `QdGamma`。

### 4.1 模型结构与映射关系
* **类名**：`QdGamma`
* **表名**：`qd_gamma`
* **字段映射**：
  * `timestamp` (`DateTime`, 主键，必填)
  * `ticker` (`String(20)`, 主键，必填)
  * `strike` (`Numeric(10, 2)`, 主键，必填) —— 以上三者共同构成**联合主键（Composite Primary Key）**。
  * `expiration_date` (`Date`, 必填)
  * `dte` (`Integer`, 必填)
  * `call_gamma` (`BigInteger`, 默认 0)
  * `put_gamma` (`BigInteger`, 默认 0)
  * `net_gamma` (`BigInteger`, 默认 0)
* **联合索引**：在 `timestamp` 与 `ticker` 列上构建名为 `idx_timestamp_ticker` 的联合索引，支持快速多时段查询对齐。

---

## 5. SPX Gamma 信号表字段扩展与数据库变更说明

为了支持高频的 30 分钟时序对比和主力墙迁移追踪，对系统表 `spx_gamma_signals` 进行了物理字段扩展，从而无需从大段文本中解析即可进行原始主力水位的时序查询与对比。

### 5.1 字段定义扩展
在 `SpxGammaSignal` 模型类（及 MySQL 中）新增了以下 4 个物理列：
* `call_wall_strike` (`Numeric(10, 2)`)：Call 侧单点最大正 Gamma 敞口的行权价。
* `put_wall_strike` (`Numeric(10, 2)`)：Put 侧单点绝对值最大负 Gamma 敞口的行权价。
* `call_wall_gamma` (`Numeric(20, 2)`)：对应多头主力墙处的 GEX 敞口原始数值。
* `put_wall_gamma` (`Numeric(20, 2)`)：对应空头主力墙处的 GEX 敞口原始数值。

### 5.2 数据库变更执行
* **迁移脚本**：通过编写并运行临时 DDL 迁移脚本，利用 `pymysql` 连接 `bb_trade` 数据库对 `spx_gamma_signals` 执行了 `ALTER TABLE` 物理添加操作，设置字段默认值为 `NULL` 并兼容重复执行情况。
* **保存逻辑升级**：同步重构了 [spx_gamma_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/quantdata/spx_gamma_analyst.py) 的 `INSERT / ON DUPLICATE KEY UPDATE` 入库语句，将每 30 分钟抓取计算得到的 `max_bull_strike`, `max_bear_strike`, `max_bull_val`, `max_bear_val` 正确地作为参数持久化绑定入库。

---

## 6. AI 模式选择框与后端 AI 模式联动说明

为了支持用户在进行历史回测或获取最新信号时自主选择是否启用 AI (Gemini) 进行分析与总结，系统新增了前端 “AI” 模式勾选与后端分析器 CLI 参数 `--ai` 模式的级联调度：

### 6.1 前端 UI 增强
* **选择框渲染**：在 [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html) 中的时间输入框后，新增了 “AI” 选项复选框（`#spxGammaAiCheckbox`），并配置了契合系统现代界面的 inline-flex 布局，便于用户直观操作。
* **参数传递**：在 [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) 的 `fetchRealtimeSignals()` 函数中，读取复选框的选中状态并将其作为 `use_ai` 参数（`true` 或 `false`）异步请求 `/data/spx_gamma_decision` 接口。
* **静态资源缓存击穿 (Cache-Busting)**：为了防止浏览器缓存旧版的 `bbt_signals.js` 导致逻辑未更新，在 [bbt_signals.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_signals.html) 中为静态资源 URL 附加了版本查询参数：`?v=1.0.5`，以强制浏览器加载最新逻辑。
* **AI 模型版本元数据呈现 (AI Model Metadata Display)**：为了让用户明确获取生成报告的底层 AI 模型规格，在 [spx_gamma_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/quantdata/spx_gamma_analyst.py) 中成功获取 Gemini 响应后，将使用的物理模型名称封装为 `[MODEL_INFO] {model_used}` 并追加至 `verdict` 文字尾端存入数据库。前端 [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) 进行正则表达式拦截与高精度转换，将该信息渲染为做市商对冲研判区域右下角独立、右对齐、带微芯片 icon 且具有点缀边框的优雅元数据展示条。
* **二级列表缩进解析 Bug 修复（Nested List Fix）**：针对 AI (Gemini) 输出时偶尔丢失行首缩进空格，导致诸如 `Call Wall:`、`Put Wall:`、`Call主力集群:`、`Put主力集群:` 等二级数据子项被误判为一级列表项的排版问题，在 Markdown 渲染解析器中新增了前缀关键字强识别。若匹配上述量化指标前缀，则强制设为二级嵌套缩进（`currentLineLevel = 2`），完美恢复级联排版。
* **研判文本结构化解析 Bug 修复（Swallow Bugfix）**：修复了在解析 `[VERDICT]` 区域时，由于 `多空方向` 研判的理由段落中包含 `多空主力集群Gamma比率` 关键字，导致整行被判定为比例行而被错误吞掉（Swallowed）的问题。调整匹配顺序优先判定 `多空方向`，确保两行研判结论完整渲染。
* **板块重命名（Section Rename）**：将原本意义不明确的 “市场微观分析 (Microstructure Analysis)” 部分正式重命名为 “**做市商对冲研判 (Market Maker Hedging Analysis)**”，使其技术主题更贴合期权动态对冲的业务实质。
* **双阶段异步渐进式加载 (Asynchronous Progressive Loading)**：
  * **第一阶段 (即时渲染)**：点击 Backtest 或 AI 决策按钮后，系统立即发送非 AI（`use_ai=false`）请求，瞬间加载并渲染固定的量化数据（Spot, Zero Gamma Line, Call/Put Walls, 30分钟墙体滚动与集群变化等），确保页面即时响应，无卡顿或空白感。
  * **第二阶段 (后台 AI 升级与覆盖)**：在第一阶段渲染完毕后，若启用了 AI 模式，系统在后台默默发送 AI 分析请求（`use_ai=true` 或 `trigger_ai=true`）。
  * **状态指示器 (Spinner)**：在此后台 AI 分析处理期间，查询按钮上会持续显示 `<i class="fas fa-spinner fa-spin"></i> AI Analyzing...` 旋转动画及置灰状态，直观体现后台正在处理。
  * **结果平滑覆盖**：当 AI 响应返回后，自动替换第一阶段的 “多空方向” Badge 及 “做市商对冲研判 (Market Maker Hedging Analysis)” 的文本内容，其余固定量化参数保持无缝贴合。

### 6.2 后端逻辑联动与缓存路由控制
In [bbt_signals.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_signals.py) 的 `/data/spx_gamma_decision` 路由函数中：
1. **参数提取**：通过 `request.args.get('use_ai')` 获取前端勾选状态。
2. **多模态缓存比对**：
   * 若勾选 AI 模式 (`use_ai=True`)，系统检索数据库时将强制匹配 `is_ai_analysis = 1` 的历史记录。若满足且属于 exact match 则直接返回，避免重复调用 AI API 产生不必要的延迟与配额消耗；若数据库中仅存在 Rule-based 记录 (`is_ai_analysis = 0`)，则会强制使缓存失效，调用 `run_live_spx_gamma_analysis(..., call_ai=True)` 进行动态 AI 升级计算并入库。
   * 若未勾选 AI 模式 (`use_ai=False`)，系统将优先获取或动态生成 Rule-based (`call_ai=False`) 的纯量化数据，满足用户的回测与非 AI 模式浏览诉求。
3. **动态调用传参**：如果缓存失效或无对应模式的信号，根据 `use_ai` 参数值动态调用 [spx_gamma_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/quantdata/spx_gamma_analyst.py)，实现参数 `--ai` 的级联流转。

---

## 7. 日内每半小时历史变化趋势与走势预判说明 (Intraday Trend Progression & Trajectory Forecast)

根据用户的最新要求，系统现在在 **AI 模式** 和 **Rule 模式** 下都加入了从开盘每半小时到当前查询时间的历史主要数据变化趋势分析，并对走势的可能变化进行科学预判（如：趋势加深、趋势反转、已达目标价开始横盘整理等）。

### 7.1 数据采集与对齐机制
* **开盘起点与区间对齐**：系统设定美西时间 `06:30 AM`（美东时间 `09:30 AM`）为交易日开盘起点。按 30 分钟为步长计算出至当前 `target_ts` 的所有时间节点（如：`06:30`, `07:00`, `07:30`, ...）。
* **内存一次性检索性能优化**：系统在每次分析执行时仅向 `yfinance` 下载**一次**当天的 1 分钟精度价格序列，并在内存中进行时间检索，避免了反复请求网络导致的延迟卡顿。
* **高容差匹配与批量数据提取**：根据生成的 30 分钟节点，在 `qd_gamma` 的唯一时间戳列表中匹配最接近的实际数据点（容差 15 分钟内）。确定时间戳列表后，进行 `SELECT ... WHERE timestamp IN (...)` 批量查询，一次性拉出所有节点数据，在内存中完成各时点的 Zero Gamma 翻转线、多空主力墙以及 5-strike 集群 Gamma 值的计算。

### 7.2 走势研判逻辑与分类
在每半小时变化轨迹的基础上，分析器（包括 Rule 模式下的 Python 规则判定与 AI 模式下的 Gemini 动态对冲推理提示词）会将盘面走势归纳分类为以下几种状态：
1. **趋势加深 (Trend Deepening)**：
   * *负 Gamma 区间*：空头主力墙向下位移，或 Put 主力集群的负 Gamma 绝对值持续显著扩增，在做市商顺势卖出 Delta 对冲盘的作用下，倾向于加速下行。
   * *正 Gamma 区间*：多头主力墙向上位移，或 Call 主力集群的正 Gamma 敞口持续放大，助推价格上行趋势。
2. **趋势反转 (Trend Reversal)**：
   * *下行反弹*：现价逼近或跌破空头主力墙，但最近 30 分钟 Put 主力集群的负 Gamma 绝对值开始收缩（空头平仓，做市商平仓 Delta 空头，触发回购），形成超跌反弹动能。
   * *上行见顶*：现价升入正 Gamma 极值区且接近多头主力墙，但最近 30 分钟 Call 主力集群的正 Gamma 绝对值开始萎缩，多头了结离场，做市商被动抛售对冲头寸，面临见顶反转。
3. **已达目标价横盘 (Target Reached & Range-bound)**：
   * 现价极其接近主力墙（12 点以内），且该主力墙在过去 30 分钟内未发生迁移，做市商在极值区的强行权钉住（Pinning）效应限制了波动，使价格在此处横盘整理。
4. **区间震荡 (Range-bound Consolidation)**：
   * 市场处于正 Gamma 弱波动或双向对冲均值回归中，主力墙未出现方向性偏移。

### 7.3 前端渲染与 UI 呈现
* **Markdown 到 HTML 的解析拓展**：
  * 在 [bbt_signals.js](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/static/js/bbt_signals.js) 中，为 `formatSpxGammaVerdict` 增加了 `[TREND_ANALYSIS]` 段落拦截与处理逻辑，将其渲染为独立的带图表的视觉大标题：**趋势与走势预判 (Trend & Trajectory Forecast)**。
  * 将时序变化（`trend_progression_text`）和对冲预判进行统一渲染输出。
* **研判类型 Badge 化视觉高亮**：
  * 对 `走势研判类型` 的判定结论进行了视觉增强，将 `趋势加深`、`趋势反转`、`已达目标价横盘`、`区间震荡` 映射为高亮气泡标签（Badge），使分析结论的核心字段在前端极其醒目。
* **静态缓存刷新**：
  * 将 `bbt_signals.html` 引用的 JS 文件版本升级为 `?v=1.0.6`，保证最新的趋势解析和走势气泡渲染立即生效。

---

## 8. 负 Gamma 环境下“行权钉住”误判修正说明 (Correcting Pinning Misjudgment under Negative Gamma)

在 2026-06-05 11:00 的分析中，AI 报告曾给出了“已达目标价横盘”的判定，且 trajectory 预判逻辑称“现已抵达空头主力墙 7450，做市商将买入正 Delta 资产以进行双向 Delta 对冲，形成强行权钉住效应，突破可能性降低”。然而，大盘随后实际向下突破并暴跌了 70 个点。

### 8.1 物理与微观机制的根本成因
这一误判的原因是 **Prompt 及规则中未对正/负 Gamma 机制下做市商动态对冲行为的物理规律进行严格约束**，导致 LLM 在物理机制上发生了原理性混淆：
1. **正 Gamma 机制（Spot > Zero Gamma）**：做市商实施**逆势对冲**（低买高卖）。当标的价格下跌时，做市商需要买入标的资产以维持 Delta 中性。这种对冲盘提供了支撑，在接近巨额 Gamma 墙时会产生明显的**“行权钉住 (Pinning)”效应**，平抑波动率并促使价格向主力墙靠拢并横盘整理。
2. **负 Gamma 机制（Spot < Zero Gamma）**：做市商实施**顺势对冲**（低卖高买）。当价格下跌时，做市商**必须加速卖出标的资产**以维持 Delta 中性。这是一种正反馈的波动率放大机制。在逼近负 Gamma 主力空头墙（如 Put Wall 7450）时，做市商不仅不能提供支撑和钉住作用，反而因为 Gamma 绝对值在行权价附近达到峰值，极易引发做市商 Delta 敞口的“悬崖效应”。一旦标的价格跌破或高度逼近该价位，做市商抛售对冲的行为将指数级加速，从而诱发**破位暴跌风险（趋势加深）**。

### 8.2 改进与修复实施
为了彻底解决此项误判，我们对系统代码及 Prompt 进行了如下修复升级：
* **删除并重新构建 `spx_gamma_analyst.py`**：修复了原代码中由于部分乱码及截断引起的语法错误，重新整理了 `init_signals_table` 的 DDL 创建规范，确保在全新环境下也能正确创建包含 Wall 追踪列的表结构。
* **物理法则约束注入 Prompt & System Instruction**：
  * 在 [spx_gamma_analyst.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/quantdata/spx_gamma_analyst.py) 的 `BBAI.call_gemini` 系统提示词（`system_instruction`）中，加入了极其严厉的物理定律约束：“你必须严格遵守期权做市商在正/负 Gamma 机制下的对冲物理定律：正 Gamma 逆势对冲产生行权钉住；负 Gamma 顺势对冲加速趋势并导致破位加深，绝无钉住效应。”
  * 在 Prompt 模板中新增了第 4 项明确指令【期权做市商对冲物理法则约束】，详细说明了在 Spot < Zero Gamma 的负 Gamma 环境下，逼近 Put Wall 时做市商顺势对冲会加速趋势并导致下行破位，绝无钉住效应，禁止 AI 在此环境下生成“已达目标价横盘”或宣称有“行权钉住”效果。
* **规则层与 AI 的科学对齐**：确保 Python 规则层计算的 `trend_type`（当在负 Gamma 环境下逼近空头墙且 GEX 扩张时自动判定为 `趋势加深`）作为强烈的上下文约束传导给 Gemini，使模型生成高度专业且契合市场实际走势的微观技术研判判词。

### 8.3 回测验证
使用修复后的脚本重新分析 2026-06-05 11:00：
* **分析类型**：由“已达目标价横盘”转为 **“趋势加深”**。
* **物理逻辑**：AI 精准指出了“在负 Gamma 机制下，标的价格下跌导致做市商的 Delta 快速转负，为维持 Delta 中性，做市商必须在现货市场进行顺势卖出对冲。由于 7450 处聚集了巨额负 Gamma 敞口，若现价跌破 7450，做市商将面临 Delta 极速收缩的‘悬崖效应’，迫使其抛售行为指数级加速，引发破位加深。”
* **实际走势拟合**：与随后的 70 点大跌实现了完美的实盘拟合与微观解释。
