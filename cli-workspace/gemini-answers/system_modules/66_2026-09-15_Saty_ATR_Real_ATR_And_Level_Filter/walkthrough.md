# MotiveWave「Saty ATR Levels」实算 ATR 关卡口径精简与符号解析修复 —— 验收报告 (Walkthrough)

- **日期**：2026-09-15
- **模块**：66 `Saty_ATR_Real_ATR_And_Level_Filter`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施）
- **对应计划**：`implementation_plan.md`（同目录）
- **状态**：✅ 6 个文件改动全部落盘，Java 全量编译与 Python 编译检查通过，新端点与符号解析经真实 HTTP 验证通过；**编译产物已部署**到 `~/MotiveWave Extensions/dev`（`ant deploy` / `BUILD SUCCESSFUL`）
- **影响面**：MotiveWave 研究指标 `StudySatyATR` + 指标-后端取数链路（`FlaskBridge` / `/mw_api/atr_real` / Schwab 符号解析）+ 共用昨收端点的 `StudyPreviousLevels`

---

## 1. 交付物清单（代码）

| 文件 | 交付内容 |
|---|---|
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudySatyATR.java` | 关卡精简为 4 条（`+61.8%` / `+100%` / `-61.8%` / `-100%`），删除 `UP_50_COLOR` / `DN_50_COLOR` 与 `±50%`；PC 昨收锚点保留；ATR 改调 `getRealATR`；新增 `onSettingsUpdated` 复位覆写 + `dataReady` / `RETRY_INTERVAL_MS=15000` 重试；ATR 缓存键由 date 改为 ticker |
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/FlaskBridge.java` | 新增 `getRealATR(ticker)` → `/mw_api/atr_real`；旧 `getATR()` 原样保留 |
| `bbt_data_web/data_app/motivewave_data.py` | 新增路由 `/mw_api/atr_real`（200 / 400 / 400 / 404 四态）；旧 `/mw_api/atr`（CSV 路径）未改动 |
| `PyTools/py_lib/bb_tickers.py` | 新增 `BBTicker.atr_real(ticker, period=14)` 与 `ATR_YF_SYMBOL_MAP`（Schwab 实算优先，yfinance 兜底，不读 CSV） |
| `PyTools/bb_yf/yf.py` | 新增 `BBYF.atr_wilder(...)`：Wilder RMA 递归、剔除未收盘 K、兼容 MultiIndex、回溯 400 天 |
| `PyTools/tos_api/bb_tos.py` | 新增 `SCHWAB_SYMBOL_MAP` / `resolve_symbol()`（`get_ohlc_rth()` 内应用，幂等）与 `BBTOS.atr_wilder(ticker, period=14)`（Schwab 日线 + Wilder 平滑） |

## 2. 关键机制（最终口径）

- **ATR 口径**：Wilder RMA（等价 TradingView `ta.atr(14)`），首值 = 前 `period` 个 TR 的简单均值种子；旧链路（`BBTOS.atr` / `BBYF.atr`）的 `rolling(window).mean()` 本身与 Pine 不等价。
- **取值口径**：**最后一根已收盘日线**的 ATR（盘中即 Pine 的 `atr[1]`）；期货按 17:00 ET、股票按 16:00 ET 判定并剔除仍在交易的当根。
- **数据源优先级**：Schwab 日线（主源，与昨收同源、口径内部一致）→ yfinance（兜底）。依据：yfinance `ES=F` 的 2026-09-14 那根与此前收盘 / 券商日线不一致（换月 / 合约错位伪影）。
- **符号解析**：`resolve_symbol()` 把裸符号映射为券商口径（`ES→/ES`、`NQ→/NQ`、`MES→/MES`、`MNQ→/MNQ`、`SPX→$SPX`、`NDX→$NDX`），已带前缀的输入原样返回（幂等）。
- **设置变更复位**：`Study.onSettingsUpdated()` 的 SDK 字节码顺序（`clearFigures()` → `labelMap.clear()` → `updateDefaultGuides()` → `precalculate()` → `calculateValues()` → `postcalculate()`）**不含 `clearState()`** ⇒ 依赖「数据未变就早退」的守卫会白屏；已在 `StudySatyATR.onSettingsUpdated()` 内自行复位 `lastSize=-1` / `lastTicker=""` / `dataReady=false` 后调 `super`。
- **容错重试**：`dataReady` + `RETRY_INTERVAL_MS=15000` 节流重试，取数失败不再被 size 守卫永久锁死；ATR 缓存键改为 ticker（ATR 与日期无关）。
- **纯新增面**：`/mw_api/atr_real` 为新增路由；旧 `/mw_api/atr` 保持 CSV 语义不动。

## 3. 验证证据

### 3.1 Java 全量编译

```
javac -nowarn -d /tmp/... -cp lib/* src/bbt/*.java
→ exit 0
```

环境：JDK 22 + `lib/mwave_sdk.jar`。

### 3.2 Python 编译检查

`py_compile` 四个改动文件：`bb_tos.py` / `bb_tickers.py` / `yf.py` / `motivewave_data.py` → **OK**。

### 3.3 实算 ATR（Schwab 日线主源）

| 标的 | 实算 ATR（Schwab 主源） |
|---|---|
| ES | 70.08 |
| NQ | 431.75 |
| MES | 70.17 |
| SPY | 5.98 |
| QQQ | 8.77 |
| TSLA | 13.11 |
| SPX | 60.17 |

yfinance 兜底口径：`ES 70.66` / `SPY 6.12`（与主源差约 1% 以内，交叉一致）。

### 3.4 真实 HTTP 端到端（服务 `127.0.0.1:5005` 在跑）

| 请求 | 结果 |
|---|---|
| `/mw_api/atr_real?ticker=ES` | 200 `70.08` |
| `/mw_api/atr_real?ticker=SPY` | 200 `5.98` |
| `/mw_api/atr_real?ticker=ES&period=abc` | 400 |
| `/mw_api/atr_real`（缺 ticker） | 400 |
| `/mw_api/atr_real?ticker=<未知标的>` | 404 |
| `/mw_api/atr?ticker=ES`（旧路径） | 200 `49.31`（旧路径未受影响） |
| `/mw_api/prev_ohlc?ticker=ES` | `7682.25`（修复前为 `68.33`） |
| `/mw_api/prev_ohlc?ticker=SPY` | `760.77` |
| `/mw_api/prev_ohlc?ticker=NQ` | `29416.25` |
| `/mw_api/prev_ohlc?ticker=SPX` | `7620.37` |
| `/mw_api/prev_ohlc?ticker=/ES` | `7682.25`（幂等，与 `ES` 一致） |

Flask `test_client` 另跑一遍，结果与上述一致（确认路由层行为）。

### 3.5 当前四条关卡数值（ATR 70.08，锚 7682.25）

| 关卡 | 数值 |
|---|---|
| `+61.8%` | `7725.56` |
| `+100%` | `7752.33` |
| `-61.8%` | `7638.94` |
| `-100%` | `7612.17` |

## 4. 未验证项（如实说明）

1. **MotiveWave 终端内的实际渲染**未做 GUI 实测；
2. **「改设置后不再白屏」未做 GUI 实测** —— 依据为 SDK 字节码（`javap` 反编译 `lib/mwave_sdk.jar`）+ 代码逻辑推导；
3. **编译产物已部署**到 `~/MotiveWave Extensions/dev`（2026-09-15 21:45 执行 `ant deploy`：`BUILD SUCCESSFUL`，34 个 class 文件，`.last_updated` 已 touch 触发终端热加载；部署前已备份旧目录到 `/tmp/mw_dev_backup_20260915_214517`）；**终端热加载后的实际显示仍未做 GUI 实测**；
4. **未做多标的 / 多周期在终端内的遍历验证**；
5. 缺陷一章节中两个 `−100%` 数值分别对应不同 ATR 来源：`−2.33` 出自 yfinance 兜底口径 ATR `70.66`，`−1.75` 出自 Schwab 主源 ATR `70.08`；非矛盾，且两者均在零轴以下，缺陷判定不变。

## 5. 残余偏差（待用户决策，本轮未改）

本轮锚点口径 = 「上一自然日 RTH（6:30–13:00 PT）收盘」；TradingView = 「上一根已收盘日线收盘」。以 2026-09-15 为例：本实现锚 `7682.25`（9/14 RTH 收盘），TV 口径锚 `7663.75`（9/15 日线收盘）⇒ 四条线整体偏 **+18.50 点**。可拆为：① 按 PT 自然日换日（15:00–24:00 PT 仍显示上一交易日关卡，约 9.5 点）；② RTH 13:00 PT 收盘 vs TV 日线 17:00 ET 收盘（约 9 点）。是否对齐 TV 待用户裁定。

## 6. 归档与回滚

- **归档**：本目录 `66_2026-09-15_Saty_ATR_Real_ATR_And_Level_Filter/`（plan + walkthrough，`.md` / `.html` 双份）；`bbt_trading_modules.html` M18 演进行新增 1 行 + 计数同步。
- **回滚**：
  1. 文件层面：`git revert` 上述 6 个文件；
  2. 口径层面：把 `StudySatyATR` 的 `getRealATR` 换回 `getATR`，即恢复 CSV 口径；
  3. 影响面：`/mw_api/atr_real` 为纯新增路由，`StudyPriceSpike` / `StudyOrderFlowReversal` 仍走旧 `/mw_api/atr`，不受影响。
