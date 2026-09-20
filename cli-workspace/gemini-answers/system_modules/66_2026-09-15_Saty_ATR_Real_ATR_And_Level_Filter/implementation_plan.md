# MotiveWave「Saty ATR Levels」实算 ATR 关卡口径精简与符号解析修复 —— 实施计划

- **日期**：2026-09-15
- **模块**：66 `Saty_ATR_Real_ATR_And_Level_Filter`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施）
- **触发事件**：用户对 MotiveWave Java 研究指标 `BBT Saty ATR Levels`（`StudySatyATR`，对标 TradingView 指标 `BB_Saty_ATR` / Saty Mahajan Saty ATR Levels）本轮提出两项口径调整要求；核查过程中同批暴露两个必须一并修复的缺陷（详见第 2 节）。
- **用户口径（本轮，原文要点）**：
  1. 「不要依赖 Ticker_ATR.csv，请实算 ATR」；
  2. 「改成只显示 ±61.8%、±100%」（即精简为 **+61.8% / +100% / −61.8% / −100%** 四个关口，去掉 ±50%）。
- **技术栈**：Java（JDK 22）· MotiveWave Java SDK（`lib/mwave_sdk.jar`）· Java 研究指标 `StudySatyATR` / `FlaskBridge` · Flask（`bbt_data_web`）· TOS/Schwab 日线 API · yfinance（兜底）· Wilder RMA（Wilder 平滑 ATR）

---

## 1. 背景与目标

标的指标为 MotiveWave 终端内的 Java 研究指标 `BBT Saty ATR Levels`（类 `StudySatyATR`），其语义为：以「昨收」（PC 线）为锚点，按 ATR 的固定百分比倍率向外投射若干条价格关卡（对标 TradingView 指标 `BB_Saty_ATR`，即 Saty Mahajan 的 Saty ATR Levels）。

本轮目标有三项，其中前两项来自用户明确口径，第三项为核查中发现的同批必修缺陷：

1. **弃用 CSV 数据源，改为实算 ATR**：不再读取 `Ticker_ATR.csv`，改由后端实算 ATR 并供给指标；
2. **关卡精简**：只保留 ±61.8% 与 ±100% 四个关口，删除 ±50%，PC（昨收）锚点线保留；
3. **同批修复两个缺陷**：① ES 昨收取到了 Eversource Energy（NYSE 电力股）而非 ES 期货；② `Ticker_ATR.csv` 数值与真实 ATR 严重不符（第 2 节逐条复核）。

## 2. 缺陷复核（先钉事实，再定设计）

### 2.1 缺陷一：ES 的昨收取到了 Eversource Energy（NYSE 电力股）

- **现象**：`/mw_api/prev_ohlc?ticker=ES&date=2026-09-15` 返回 `{"open":68.87,"high":69.1,"low":67.93,"close":68.33}`。裸符号 `ES` 在 Schwab 上是股票代码（Eversource Energy，价格约 $68），**不是 ES 期货**。
- **实测对照**（2026-09-14 交易日 RTH）：

| 传入符号 | 取数结果 |
|---|---|
| `ES` | `68.33`（错误标的：Eversource Energy） |
| `/ES` | `{"open":7673.5,"high":7719.75,"low":7662.25,"close":7682.25}`（ES 期货，正确） |
| `NQ` | 无数据 |
| `/NQ` | `29416.25` |
| `SPX` | 无数据 |
| `$SPX` | `7620.37` |
| `NDX` | 无数据 |
| `$NDX` | `29128.62` |
| `MES` / `MNQ` | 无数据 |
| `/MES` / `/MNQ` | `7682.25` / `29415.75` |

- **影响**：ES 图上四条关卡以 $68 级别的股票价为锚，关卡数值完全失真。示例：以锚 `68.33` 与实算 ATR 组合计算，`−100%` 关卡落到零轴以下（**−2 量级**，无意义）。
  - 口径说明：核查当刻先用 yfinance 兜底口径 ATR `70.66` 试算（`68.33 − 70.66 = −2.33`）；改用 Schwab 主源 ATR `70.08` 后为 `68.33 − 70.08 = −1.75`。两个数值仅反映 ATR 来源不同，并非矛盾；两者**均落于零轴以下**，缺陷判定不变。
- **波及面**：共用 `/mw_api/prev_ohlc` 端点的 `StudyPreviousLevels` 受同一缺陷影响，修复后一并受益。

### 2.2 缺陷二：Ticker_ATR.csv 数值与真实 ATR 严重不符（用户因此要求弃用）

2026-09-15 实测对照（CSV 值 vs 本次实算值）：

| 标的 | CSV | 实算 |
|---|---|---|
| SPX | 49.31 | 60.17 |
| SPY | 19.16 | 5.98（约 3.2 倍偏差） |
| QQQ | 18.43 | 8.77 |
| NDX | 274.21 | NQ 431.75 |

表内 SPX / SPY 自身即互相矛盾（两者价差约 10 倍，而 ATR 仅差 2.6 倍），确认为过期 / 串行数据。此为要求弃用 CSV 的直接依据。

## 3. 设计（三个决策点）

### 3.1 ATR 口径：Wilder RMA（而非简单滚动均值）

- TradingView 的 `ta.atr(14)` 是 **Wilder RMA**，不是 TR 的简单滚动均值；旧链路（`BBTOS.atr` / `BBYF.atr`）用的是 `rolling(window).mean()`，本身就不等价。
- 本轮实算口径 = **Wilder RMA**：首值用前 `period` 个 TR 的简单均值作种子，其后按 Wilder 递归平滑。
- 取值口径 = **「最后一根已收盘日线」的 ATR 值**（盘中即等价于 Pine 的 `atr[1]`）；期货按 17:00 ET 收盘、股票按 16:00 ET 收盘判定当根是否仍在交易并剔除。

### 3.2 数据源选择：Schwab 日线为主源，yfinance 仅兜底

- Schwab 日线时间戳 = 交易日 00:00 ET（PDT 期间为 05:00 UTC）；yfinance `ES=F` 日期标签相同。
- 但 yfinance `ES=F` 在 **2026-09-14** 那根 K 线与此前收盘 / 券商日线不一致（换月 / 合约错位伪影）。
- 故 **Schwab 为主源（与昨收同源、口径内部一致）**，yfinance 仅在主源失败时兜底。

### 3.3 设置变更缺陷：SDK 证据与复位方案

- **SDK 证据**（用 `javap` 反编译 `lib/mwave_sdk.jar` 得出）：`Study.onSettingsUpdated()` 的字节码顺序为 `clearFigures()` → `labelMap.clear()` → `updateDefaultGuides()` → `precalculate()` → `calculateValues()` → `postcalculate()`，**全程不调用 `clearState()`**；且整个 SDK jar 中只有 `Study.class` 引用 `clearState`。
- **后果**：指标内任何依赖「数据未变就早退」的守卫（size 守卫 / ticker 守卫 / `dataReady` 守卫）在改设置后会直接白屏。
- **方案**：在 `StudySatyATR` 内覆写 `onSettingsUpdated(DataContext)`，先把 `lastSize=-1`、`lastTicker=""`、`dataReady=false` 复位，再调用 `super.onSettingsUpdated(ctx)`，使守卫在改设置后必然重新取数。
- **配套**：新增 `dataReady` + `RETRY_INTERVAL_MS=15000` 节流重试，取数失败时不再被 size 守卫永久锁死；ATR 缓存键由 date 改为 ticker（ATR 与日期无关）。

## 4. 变更清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudySatyATR.java` | 关卡精简为 4 条（`+61.8%` / `+100%` / `-61.8%` / `-100%`，删除 `UP_50_COLOR` / `DN_50_COLOR` 及 `±50%` 绘制与设置项，PC 昨收线保留为锚点）；ATR 改调 `FlaskBridge.getRealATR(ticker)`（`/mw_api/atr_real`）；新增 `onSettingsUpdated(DataContext)` 覆写（先复位 `lastSize=-1` / `lastTicker=""` / `dataReady=false` 再 `super`）；新增 `dataReady` + `RETRY_INTERVAL_MS=15000` 节流重试；ATR 缓存键由 date 改为 ticker |
| 2 | `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/FlaskBridge.java` | 新增 `getRealATR(ticker)` → `/mw_api/atr_real`；旧 `getATR()` 原样保留（`StudyPriceSpike` / `StudyOrderFlowReversal` 仍在用） |
| 3 | `/Users/zhijiebian/Documents/Workplace/PycharmProjects/BBTrading/bbt_data_web/data_app/motivewave_data.py` | 新增路由 `/mw_api/atr_real`（成功返回文本浮点 200；缺 ticker 400；period 非法 400；无数据 404）；旧 `/mw_api/atr`（CSV 路径）未改动 |
| 4 | `PyTools/py_lib/bb_tickers.py` | 新增 `BBTicker.atr_real(ticker, period=14)` 与 `ATR_YF_SYMBOL_MAP`；**先走 TOS/Schwab 日线实算，失败再退回 yfinance**；完全不读 `Ticker_ATR.csv` |
| 5 | `PyTools/bb_yf/yf.py` | 新增 `BBYF.atr_wilder(ticker, period=14, symbol=None, lookback_days=400)`：Wilder RMA 递归（首值用前 period 个 TR 的简单均值做种子）、剔除当日未收盘 K、兼容 yfinance MultiIndex 列、回溯 400 天 |
| 6 | `PyTools/tos_api/bb_tos.py` | 新增 `BBTOS.SCHWAB_SYMBOL_MAP` 与 `resolve_symbol()`（`ES→/ES`、`MES→/MES`、`NQ→/NQ`、`MNQ→/MNQ`、`SPX→$SPX`、`NDX→$NDX`、`VIX/RUT/DJI`），并在 `get_ohlc_rth()` 内对 `symbol` 应用（已带 `/`、`$` 前缀的原样返回，幂等）；新增 `BBTOS.atr_wilder(ticker, period=14)`：Schwab 日线 + Wilder 平滑，剔除仍在交易的当根（期货按 17:00 ET 收盘、股票按 16:00 ET 收盘判定） |

## 5. 验收标准

1. Java 侧全量编译通过：`javac -nowarn -d /tmp/... -cp lib/* src/bbt/*.java` → **exit 0**（JDK 22 + `lib/mwave_sdk.jar`）；
2. Python 侧编译检查通过：`py_compile` 四个改动文件（`bb_tos.py` / `bb_tickers.py` / `yf.py` / `motivewave_data.py`）→ **OK**；
3. 新端点行为正确：`/mw_api/atr_real` 成功 200（文本浮点）、缺 ticker 400、period 非法 400、无数据 404；
4. 旧链路零回归：`/mw_api/atr`（CSV 路径）返回不变；`StudyPriceSpike` / `StudyOrderFlowReversal` 不受影响；
5. 符号解析幂等：`ES` 与 `/ES` 取到同一 ES 期货数据（`7682.25`）；
6. `StudySatyATR` 改设置后不再白屏（依据为 SDK 字节码 + 代码逻辑推导，**未做 GUI 实测**；未验证项汇总见 `walkthrough.md` 第 4 节）；
7. 归档：本目录（plan + walkthrough，`.md` / `.html` 双份）与 `bbt_trading_modules.html` M18 演进行同步。

## 6. 按设计未实现（用户本轮明确精简，不算缺陷）

以下能力按用户本轮口径精简，**不作为缺陷记录**：

- 触发位 CT / PT（±23.6%）；
- 中间档与扩展档（38.2 / 78.6 / 123.6 … 300）；
- 交易日型时间框架切换（Day / Multiday / Swing / Position / Long-term）；
- 信息表；
- 期权 Calls / Puts 标签。

## 7. 残余偏差（如实记录，标注为待用户决策，不要写成已修复）

锚点口径与 TradingView 仍有系统性偏移：本轮采用「上一自然日 RTH（6:30–13:00 PT）收盘」为锚，TV 采用「上一根已收盘日线收盘」。

以 2026-09-15 为例：

| 口径 | 锚值 |
|---|---|
| 本实现（9/14 RTH 收盘） | `7682.25` |
| TradingView（9/15 日线收盘） | `7663.75` |
| 四条线整体偏移 | **+18.50 点** |

偏移可拆为两项：

1. 按 PT 自然日换日 ⇒ 15:00–24:00 PT 仍显示上一交易日关卡（当日最近已收盘 RTH 为 9/15 的 `7672.75`，约 **9.5 点**）；
2. RTH 13:00 PT 收盘 vs TV 日线 17:00 ET 收盘（约 **9 点**）。

是否对齐 TV 口径**待用户裁定，本轮未改**。

## 8. 回滚方式

1. **文件层面**：`git revert` 上述 6 个文件；
2. **口径层面**：仅把 `StudySatyATR` 的 `getRealATR` 换回 `getATR`，即恢复 CSV 口径；
3. **影响面**：`/mw_api/atr_real` 为**纯新增**路由，其他研究不受影响（`StudyPriceSpike` / `StudyOrderFlowReversal` 仍走旧 `/mw_api/atr`）。
