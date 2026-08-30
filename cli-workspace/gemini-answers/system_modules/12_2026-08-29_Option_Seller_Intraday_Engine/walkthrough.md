# Option Seller 日内期权卖方自动交易系统实施与验收总结 (Module 12)

基于 **BBT.AI (BBT.AI)** 工业化期权卖方四步闭环体系（`DISCOVER` -> `STRUCTURE` -> `MANAGE` -> `REVIEW`），已全面完成 SPY 0DTE 两腿定义风险垂直价差（Vertical Credit Spread）自动交易系统的构建与端到端实盘仿真验证。

---

## 一、 完成的核心功能与模块架构

### 1. 核心选型引擎：[option_seller_engine.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_engine.py)
* **DISCOVER (机会发现与微观仲裁)**：
  * 结合市场状态、做市商 Gamma 对冲模式与趋势日均线带防护罩（Trend Day Shield，严禁逆势卖腿）；
  * 联动 5 分钟 Order Flow 哨兵双引擎信号与 DOM 诱多/诱空陷阱过滤，过滤胜率未达绝对优势的时段。
* **STRUCTURE (合约动态询价与组装)**：
  * 秒级扫描实时 SPY 0DTE（或近月）期权链，锚定 Short Leg Delta 在 `0.08 ~ 0.15` 区间（胜率 POP 85%~92%）；
  * 强制安全垫距离校验（Put 腿低于现价至少 0.60%~0.75%，Call 腿高于现价至少 0.60%~0.75%）；
  * 保护腿（Long Leg）固定间隔 1.0 点，硬性锁定最大理论亏损为 `(Width - Net Credit) * 100`；
  * 净权利金底线过滤（Net Credit >= $0.06，保证盈亏比合理）。

### 2. 状态机与持仓守护引擎：[option_seller_manager.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/option_seller/option_seller_manager.py)
* **双模式无缝支持**：
  * `dry_run = True`：实时行情 + 本地仿真撮合引擎（零资金风险演练，用于策略回测与参数调优）；
  * `dry_run = False`：直接经由 Schwab API (`schwab-py`) 下单执行。
* **自主后台守护线程 (15s Loop)**：
  * **主动提早止盈 (Take Profit)**：权利金衰减达到 65% 时自动市价平仓锁定利润；
  * **硬性止损保护 (Stop Loss)**：价差买回成本上升至开仓价 2.2 倍时自动买回止损；
  * **强制时间强平 (Time Stop)**：美西时间 12:30（收盘前半小时）全自动清空所有 0DTE 持仓，绝不过夜，规避美式期权交割风险。
* **紧急物理开关**：
  * 提供 `panic_close_all()` 一键紧急市价全平，以及 `toggle_engine()` 暂停/恢复开仓。

### 3. 底层多腿订单组装：[bb_tos.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/PyTools/tos_api/bb_tos.py)
* 增加了 `place_vertical_credit_spread()` 与 `close_vertical_spread()`，原生封装 `schwab.orders.options` 的 `bull_put_vertical_open/close` 与 `bear_call_vertical_open/close`。
* 增加了 `get_option_chain_for_symbol()` 与缓存 `get_account_hash()`。

### 4. 数据库持久化：[models.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/models.py) & [db_query_option_seller.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/db_query_module/db_query_option_seller.py)
* 建立 `order_flow_option_seller_trades` 表，结构化持久化每一笔交易的行权价、开仓权利金、平仓价、实现盈亏、入场微观证据链。

### 5. 独立 Web 监控控制台：[bbt_option_seller.py](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/bbt_option_seller.py) & [bbt_option_seller.html](file:///Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/templates/bbt_option_seller.html)
* 挂载于主平台 `bbt_data_app`（端口 5005），已加入 Landing Page 导航，独立路由直达：`http://127.0.0.1:5005/bbt_option_seller`。
* 采用现代高对比度量化控制台设计，涵盖：
  * 状态指示灯（Running / Paused / Panic）；
  * 6 大核心指标卡（总盈亏、已实现/浮动盈亏、胜率与单数、净 Delta 暴露、净 Theta 时间价值收益率）；
  * 活跃持仓动态监控卡（实时安全垫进度条、权利金衰减进度环、Greeks、手动单笔平仓）；
  * BBT.AI 四步流水线雷达状态；
  * 今日执行流水账本与历史列表；
  * 4 秒无刷新静默轮询更新。

---

## 二、 测试与全流程验证结果

1. **实时行情与合约组装验证 (Live Chain Verification)**：
   * 在当前标的 SPY $769.35 下调用 live Schwab 期权链：
     * **Bull Put Spread**: Short 763P (Delta -0.125, Bid 0.32) / Long 762P (Ask 0.25)，生成净权利金 **$0.08**，安全垫 **6.35 点 (+0.83%)**，胜率 **87.5%**，止盈线 $0.03，止损线 $0.18；
     * **Bear Call Spread**: Short 774C (Delta 0.103) / Long 775C，生成净权利金 **$0.08**，安全垫 **4.65 点 (+0.60%)**，胜率 **89.7%**。
2. **生命周期模拟演练 (Simulation Lifecycle Test)**：
   * 自动开仓入库生成 Trade #1，实时 Mark 更新，模拟触发 65% 止盈平仓，成功写入数据库并结算实现盈亏 `+$5.00`。
3. **Web 端 API 与页面渲染验证 (Endpoint Test)**：
   * `/bbt_option_seller` 页面正常渲染 HTTP 200；
   * `/api/option_seller/status` 正常输出包含持仓、Greeks、当日统计与流水明细的 JSON 数据；
   * `/api/option_seller/toggle_engine` 正常控制暂停与恢复状态。


### 6. 双批次阶梯开仓与分级止盈机制 (Dual-Tranche Tiered Scale-Out)
- **开仓策略**：每次从空仓触发入场时，系统一次性卖出 **2 个 1.0 点宽价差 (2 Contracts)**，分为两个独立追踪批次：
  - **Tranche 1 (初级止盈 40%)**：权利金衰减 40% 时平仓（买回成本 <= 60% 初始权利金），快速释放风险与心理压力；
  - **Tranche 2 (深度止盈 75%)**：权利金衰减 75% 时平仓（买回成本 <= 25% 初始权利金），深度收割 Theta 时间价值；
- **全生命周期风控**：两手价差统一受 2.2x 硬止损与 12:30 PST 时间强平线守护。
- **界面可视化**：活跃持仓卡片与历史流水账本清晰区分蓝色的 Tranche 1 与紫色的 Tranche 2 药丸标识。


### 7. 到期日动态配置与多 DTE 选型支持 (0DTE vs 1DTE Selector)
- **底层选型适配**： 增加  参数，自动解析 Schwab 期权链的  键值并升序智能寻优：
  - （当天）：自动锁定日内到期链，收割末日 Theta 加速流逝红利；
  - （隔天）：自动锁定次日到期链，以更宽的安全垫（1.0%~1.5%）与更厚的权利金进场；
- **控制台交互**：页面顶部 Header 增加轻量级交互选框 ，支持一键切换并与后端实时双向同步。


### 8. 三档开仓策略标准实装 (Risk/Yield Profiles: 保守 / 平衡 / 激进)
- **底层架构**：在 OptionSellerEngine 和 OptionSellerManager 中定义三档量化配置：
  - **CONSERVATIVE (🛡️ 保守型)**: Width 1.0点, Delta 0.10, Buffer >=0.60%, Credit >=zsh.08 (实盘净权利金约 zsh.08~zsh.12);
  - **BALANCED (⚖️ 平衡型)**: Width 2.0点, Delta 0.16, Buffer >=0.45%, Credit >=zsh.18 (实盘净权利金约 zsh.20~zsh.26);
  - **AGGRESSIVE (⚡ 激进型)**: Width 2.0点, Delta 0.25, Buffer >=0.30%, Credit >=zsh.28 (实盘净权利金约 zsh.30~zsh.45);
- **实盘期权链真实验证**：
  - 在 SPY .35 实盘链上，保守型卖出 763/762 (收 zsh.08)，平衡型卖出 765/763 (收 zsh.23)，激进型卖出 766/764 (收 zsh.30)；
  - 激进型单手净权利金较保守型激增近 4 倍，盈亏比与现金流大幅飞跃；
- **控制台交互**：Header 增加  动态切换选框，支持实时热切换与持久同步。


### 9. 双重运行场景架构实装 (Dual Usage Scenarios)
1. **场景（1）后台信号全自动开仓 (Autonomous Signal Entry)**：
   -  自动判定方向（BULLISH/BEARISH）；
   - 自动自适应决策开仓策略：
     - 若多理由共振（CVD背离 + DOM冰山吸收）或顺应高确信度 Gamma 支撑，自动触发 **⚡ 激进型 (AGGRESSIVE)**，最大化收割高额权利金；
     - 常规 HIGH 信号确认时，自动采用 **⚖️ 平衡型 (BALANCED)**；
   - 自动锁定 **0DTE**（当天到期，12:30 PST 强制全清）；
2. **场景（2）实时看盘手动快捷开仓 (Manual Trade Console)**：
   - 页面顶部增加高亮聚焦按钮 **【⚡ 手动开仓】**，点击唤起专业快捷建仓模态面板；
   - **三大维度自由定制**：
     - **方向**：🟢 看多卖 Put (Bull Put) / 🔴 看空卖 Call (Bear Call)；
     - **模式**：🛡️ 保守型 (宽1.0/Δ0.10) / ⚖️ 平衡型 (宽2.0/Δ0.16) / ⚡ 激进型 (宽2.0/Δ0.25)；
     - **DTE**：0 DTE (当天到期) / 1 DTE (隔天到期)；
   - **实时询价与预估盈亏仪表盘**：动态展示 Short/Long Strike、Delta、安全垫距离、单手及 2 手净权利金、最大亏损、双批次止盈价位；
   - **一键下单**：【🚀 立即开仓 (2 手双批次)】，秒级入库与实盘监控。


### 10. 今日交易流水账本多维元数据列升级 (Journal Multi-dimensional Columns)
1. **ID 后增加【类型】列**：
   - 自动开仓：展示 `[机器人] 自动` 图标徽章；
   - 手动开仓：展示 `[手势] 手动` 图标徽章；
2. **价差结构后增加【DTE】与【策略】列**：
   - **DTE 列**：展示清晰精致胶囊徽章（如 `0DTE` / `1DTE`）；
   - **开仓策略列**：展示风险收益徽章（`🛡️ 保守` / `⚖️ 平衡` / `⚡ 激进`）；
3. **活跃持仓卡片同步增强**：
   - 活跃持仓监控卡片同步增加类型图标、DTE 标签及开仓策略徽章，视觉体验高度统一。

### 11. 垂直价差合约极简无年份唯一表示法实装 (TOS Compact No-Year Signed Notation)
1. **统一格式语法**：
   - 采用 ThinkorSwim (TOS) 衍生的极简无年份紧凑签名表示法：`[标的][MMDD][C/P]-[ShortStrike]+[LongStrike]`；
   - 典型示例：
     - Bear Call Spread: `SPY0901C-771+770`（卖出 .SPY260901C771，买入 .SPY260901C770）；
     - Bull Put Spread: `SPY0901P-765+763`（卖出 .SPY260901P765，买入 .SPY260901P763）；
2. **流水账本与活跃卡片列布局优化**：
   - 在【价差结构】列后新增**【合约】**列（展示如 `SPY0901C-771+770` 极简代码标签）；
   - **删除冗余的【行权价】列**，信息高度凝练；
   - 活跃持仓卡片、手动快捷开仓实时询价预览面板、开仓确认弹窗全面同步展示此合约唯一代码。

3. **点击一键复制 ThinkorSwim (TOS) 复合合约代码实装**：
   - 用户点击任何位置的 `<code class="contract-code">` 徽章（如 `SPY0901P-766+765`），系统会自动生成标准 TOS 复合计算公式：
     - Bull Put: `.SPY260901P766-.SPY260901P765`
     - Bear Call: `.SPY260901C771-.SPY260901C770`
   - 一键写入系统剪贴板（兼容桌面与移动剪贴板环境），并触发右下角黑色悬浮 Toast 提示（`✅ 已复制 TOS 价差代码`）与徽章绿色高亮反馈；
   - 交易员可直接在 ThinkorSwim 的 Symbol 输入框按 `Ctrl+V`（或 `Cmd+V`）粘贴，立即查看价差实时图表与委托交易。

### 12. 今日流水账本【盈亏】分类列实装 (Outcome Classification Column)
1. **新增【盈亏】分类徽章列**：
   - 紧邻在【模式】列前新增独立【盈亏】列，直观快速识别交易结果；
2. **四档分类状态标准**：
   - 🟢 **盈利**：已止盈或盈利平仓（单笔实现净盈亏 > 0，清爽翠绿徽章）；
   - 🔴 **亏损**：发生硬止损或风控亏损平仓（单笔实现净盈亏 < 0，警示玫瑰红徽章）；
   - ⚪ **持平**：保本无损出场（单笔实现净盈亏 == 0，中性灰白徽章）；
   - 🟡 **未结**：当前头寸仍在持仓运行或追踪中（温润琥珀色沙漏徽章）。

### 13. 流水账本【操作】列与单条流水记录删除功能实装 (Row Deletion Feature)
1. **新增【操作】列**：
   - 位于【模式】列后作为账本最后一列（总计 15 列）；
   - 每一行展示精致的垃圾桶图标按钮 (`<button class="btn-table-del"><i class="far fa-trash-alt"></i></button>`)；
2. **安全防误触与全链路删除**：
   - 点击时弹出二次确认确认框（`确认删除订单 #ID 的流水记录吗？`），防止误触；
   - 后端新增 `/api/option_seller/delete_trade` API，调用 `DbQuery.option_seller_trade_delete(trade_id)` 从数据库永久移除；若为未平仓状态同步从内存活跃字典清理；
   - 成功后自动执行 `fetchStatus()` 实时重绘流水表格。

### 14. 双月盈亏日历模块实装 (2-Month P&L Calendar)
1. **双月并排响应式视口 (Dual Month Layout)**：
   - 位于流水账本下方，默认并列呈现当前月与前一个月（如 2026年7月 与 2026年8月）两个完整的 7 曜日本月历；
   - 顶部提供【前一月】、【当前双月】、【后一月】动态翻页与回到今天视口控制；
   - 每个月份卡片头部自带该月全景统计指标徽章：**月度累计盈亏**、**交易天数 / 总笔数**、**综合胜率**。
2. **每日盈亏色彩规范与单元格排版**：
   - 🟢 **浅绿色背景** (`#ecfdf5` / `#dcfce7`，边框 `#a7f3d0`)：当日实现净盈利，展示深绿粗体数字（如 `+$9.00`）与当日交易笔数（如 `4 笔`）；
   - 🔴 **浅红色背景** (`#fef2f2` / `#fee2e2`，边框 `#fecaca`)：当日发生止损净亏损，展示深红粗体数字（如 `-$25.00`）与交易笔数；
   - ⚪ **中性灰白背景**：工作日无交易或周末休市日；
   - 🔵 **今日高亮框**：当天单元格自带蓝色高亮内阴影与 `今日` 徽章；
   - **悬停浮窗 Tooltip**：鼠标 Hover 浮现当日精确盈亏额、交易笔数及胜负详情。
3. **后端数据引擎与实时联动**：
   - 数据库底层通过 `DbQuery.option_seller_pnl_by_date_range` 按日分组聚合统计；
   - 暴露 `GET /api/option_seller/calendar_pnl` API 接口；
   - 开仓下单、平仓离场或在流水账本中删除记录时，日历均自动秒级热重绘。

### 15. 流水账本首列升级为【序列】(Intraday Sequence Number)
1. **列名与语义变更**：
   - 将今日流水账本第一列由 `ID` 重命名为 **`序列`**；
2. **单日交易独立流水号**：
   - 单元格摒弃跨日累加的全局数据库自增编号（如 `#9, #8, #7, #6`），改为展示当日专属序列号（如 `#4, #3, #2, #1`，其中当天开盘首单为 `#1`，最新一单为 `#4`）；
   - 鼠标 Hover 浮现智能 Tooltip 提示：`单日交易序列号 #4 (订单 #9)`，既保障日内复盘视觉清爽，又保留底层订单全局审计能力。
