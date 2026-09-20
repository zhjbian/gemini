# 跨研究 ATR 取数统一：弃用 Ticker_ATR.csv（StudyPriceSpike / StudyOrderFlowReversal 切至实算 ATR） —— 实施计划

- **日期**：2026-09-15
- **模块**：67 `Cross_Study_Real_ATR_Unification`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施）
- **触发事件**：用户追加指令（原文）：「两个研究仍在读那张已弃用的 CSV 统一改成不用那个CSV」——即把 MotiveWave 研究指标 `StudyPriceSpike`、`StudyOrderFlowReversal` 由读取 `Ticker_ATR.csv` 统一切换至实算 ATR。前序同类改动（`StudySatyATR` 弃用 CSV）已完成并归档于 `66_2026-09-15_Saty_ATR_Real_ATR_And_Level_Filter`。
- **用户口径（本轮）**：
  1. 「两个研究仍在读那张已弃用的 CSV 统一改成不用那个CSV」（原文）；
  2. 「我只需要用在 SPY 上」（主用标的 SPY）。
- **技术栈**：Java（JDK 22）· MotiveWave Java SDK（`lib/mwave_sdk.jar`）· Java 研究指标 `StudyPriceSpike` / `StudyOrderFlowReversal` / `FlaskBridge` · Flask（`bbt_data_web`）· `/mw_api/atr_real` · Schwab 日线 API · yfinance（兜底）· Wilder RMA（Wilder 平滑 ATR）

---

## 1. 根因：写表任务是「读 CSV → 原样写回 CSV」的自引用闭环

- `PyTools/jobs/calc_atr.py`（定时任务）第 11 行调用 `BBTicker.atr(ticker)`。
- 而 `BBTicker.atr()` **优先读取 `Ticker_ATR.csv`**：`PyTools/py_lib/bb_tickers.py` 第 219–249 行，命中表格即直接返回表内 `Atr` 列。
- 因此该任务实际构成「读 CSV → 原样写回 CSV」的**自引用闭环**：任何一次写错的数值会被永久固化、永不自愈。
- 这正是 SPY 长期保留 `19.16`（真实值 `5.98` 的 3.2 倍）的原因；也解释了表内 SPX `49.31`（真实 `60.17`）与 SPY 自身相互矛盾（价差约 10 倍而 ATR 仅差 2.6 倍）。

结论：只要消费者仍读该 CSV，错误数值就会被持续供给；本轮把剩余两个研究指标统一切换到实算 ATR 取数链路。

## 2. 改动清单（2 个文件、3 处调用点）

| 文件 | 改动 |
|---|---|
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyPriceSpike.java` | 2 处：`FlaskBridge.getATR(ticker)` → `FlaskBridge.getRealATR(ticker)`。① 盘前尖峰分支（第 105 行，`enablePremarketSpike` 路径，结果经 `checkPremarketSpike()` 使用）；② 盘后/常规分支（第 178 行，`atrCache` 按 `dateStr` 缓存后用于盘后边界的 ATR 路径）。两处均加注释「Real (computed) Wilder ATR(14) — Ticker_ATR.csv is no longer used」 |
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowReversal.java` | 1 处（第 446 行）：`getDailyAtrWithCache()` 内 `FlaskBridge.getATR(ticker)` → `FlaskBridge.getRealATR(ticker)`；该值用于 `dynamicExtDistance = effectiveATR * extAtrMult` 与 `dynamicEmaDistance = effectiveATR * emaAtrMult`（第 179–180 行） |

复用上一轮已建好的取数链路（本轮未再改动）：`/mw_api/atr_real` 路由 → `BBTicker.atr_real()` → Schwab 日线 `BBTOS.atr_wilder()` 主源（Wilder RMA，取最后一根已收盘日线）+ yfinance `BBYF.atr_wilder()` 兜底；符号经 `BBTOS.resolve_symbol()` 解析。

## 3. SPY 阈值影响

SPY：实算 ATR `5.98`，CSV `19.16`，比值 **3.20 倍**；价格参考 `757.39`。

| 阈值 | 旧（CSV 19.16） | 新（实算 5.98） | 旧/新 |
|---|---|---|---|
| StudyPriceSpike 盘前 `0.5 × ATR` | ±`9.58` | ±`2.99` | 3.20 |
| StudyPriceSpike 盘后 `0.2 × ATR`（SPY 专属因子） | ±`3.83` | ±`1.20` | 3.20 |
| StudyPriceSpike RTH `0.6% × price`（不涉 ATR） | ±`4.54` | ±`4.54` | 1.00 |
| OrderFlowReversal EXT `0.6 × ATR`（UI 设置 `EXT_ATR_MULT`，默认 0.6） | ±`11.50` | ±`3.59` | 3.20 |
| OrderFlowReversal EMA `0.25 × ATR`（UI 设置 `EMA_ATR_MULT`，默认 0.25） | ±`4.79` | ±`1.50` | 3.20 |

含义：ATR 路径的尖峰/距离阈值在 SPY 上**整体收窄 3.2 倍**（RTH 的百分比路径不受影响）。这是有意接受的后果：CSV 数值本身不可信，旧阈值是错误数值的产物；换源后乘数恢复「× ATR」的字面语义。

**若日后需要恢复旧灵敏度**（供复议，本轮未改）：`StudyPriceSpike.atrFactor` 的 SPY `0.2 → 0.64`（代码 Map，第 35–37 行）；`checkPremarketSpike()` 内硬编码 `0.5 → 1.60`（第 706–707 行）；`StudyOrderFlowReversal` 的设置项 `EXT_ATR_MULT 0.6 → 1.92`、`EMA_ATR_MULT 0.25 → 0.80`（UI 可直接改，无需改代码）。

## 4. 验收标准

1. **调用点收敛**：`grep -rn "getATR(\|getRealATR(" src/bbt/` 显示 4 个研究调用点全部为 `getRealATR`，且仅本地手工冒烟测试 `BBTTest.java:23` 仍调 `getATR`（不属研究信号链路，本轮未改）；
2. **Java 全量编译通过**：`javac -nowarn -d /tmp/satyatr_build -cp "lib/*" src/bbt/*.java` → **exit 0**；
3. **部署成功**：`BBT_Studies/build` 下 `ant deploy` → **BUILD SUCCESSFUL**，34 个 class 文件拷入 `~/MotiveWave Extensions/dev`，`.last_updated` 已 touch；
4. **部署物核验**：反编译部署产物确认 `getRealATR` 引用进入 `StudyPriceSpike` 与 `StudyOrderFlowReversal`；
5. **旧路径零回归**：`/mw_api/atr` 路由与 `BBTicker.atr()` 原样保留（`/mw_api/atr?ticker=SPY → 200 19.16`），CSV 文件与写表任务未改；
6. **归档**：本目录（plan + walkthrough，`.md` / `.html` 双份）与 `bbt_trading_modules.html` M18 演进行同步。

## 5. 未纳入本轮范围

以下仍读同一份 CSV，本轮**未**改动，仍在消费可能过期的 ATR：

- `/mw_api/atr` 路由与 `BBTicker.atr()` 本身；
- CSV 文件 `Ticker_ATR.csv`；
- 写表任务 `PyTools/jobs/calc_atr.py`；
- Python 侧消费者 `PyTools/trading_view/`（5 个导出脚本）、`PyTools/option_chain/vantage.py`、`PyTools/spike_db/spikes_mw_to_csv.py`。

## 6. 回滚方式

1. 把 3 处 `getRealATR` 还原为 `getATR` 并重新 `ant deploy` 即可；
2. 或仅在 MotiveWave 中停用这两个研究；
3. 影响面：取数链路为**纯新增**，回滚不影响其他研究。
