# 跨研究 ATR 取数统一：弃用 Ticker_ATR.csv（StudyPriceSpike / StudyOrderFlowReversal 切至实算 ATR） —— 验收报告 (Walkthrough)

- **日期**：2026-09-15
- **模块**：67 `Cross_Study_Real_ATR_Unification`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施）
- **对应计划**：`implementation_plan.md`（同目录）
- **状态**：✅ 2 个文件、3 处调用点改动全部落盘；Java 全量编译 `exit 0`；`ant deploy` → **BUILD SUCCESSFUL**，34 个 class 文件拷入 `~/MotiveWave Extensions/dev`（`.last_updated` 时间戳 2026-09-15 21:55）；部署物经反编译核验
- **影响面**：MotiveWave 研究指标 `StudyPriceSpike`（盘前尖峰 + 盘后边界）与 `StudyOrderFlowReversal`（动态 EXT / EMA 距离）的 ATR 取数路径

---

## 1. 交付物清单（代码）

| 文件 | 交付内容 |
|---|---|
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyPriceSpike.java` | 2 处调用点由 `FlaskBridge.getATR(ticker)` 改为 `FlaskBridge.getRealATR(ticker)`：① 盘前尖峰分支（第 105 行，`enablePremarketSpike` 路径，结果经 `checkPremarketSpike()` 使用）；② 盘后/常规分支（第 178 行，`atrCache` 按 `dateStr` 缓存后用于盘后边界的 ATR 路径）。两处均加注释「Real (computed) Wilder ATR(14) — Ticker_ATR.csv is no longer used」 |
| `/Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowReversal.java` | 1 处（第 446 行）：`getDailyAtrWithCache()` 内由 `FlaskBridge.getATR(ticker)` 改为 `FlaskBridge.getRealATR(ticker)`；该值用于 `dynamicExtDistance = effectiveATR * extAtrMult` 与 `dynamicEmaDistance = effectiveATR * emaAtrMult`（第 179–180 行） |

## 2. 关键机制（最终口径）

- **取数链路（复用上一轮，本轮未再改动）**：`/mw_api/atr_real` 路由 → `BBTicker.atr_real()` → Schwab 日线 `BBTOS.atr_wilder()` 主源（Wilder RMA，取最后一根已收盘日线）+ yfinance `BBYF.atr_wilder()` 兜底；符号经 `BBTOS.resolve_symbol()` 解析。
- **口径一致性**：至此 4 个 MotiveWave 研究指标（`StudySatyATR`、`StudyPriceSpike`、`StudyOrderFlowReversal`）的 ATR 来源统一为实算 Wilder ATR(14)，不再读取 `Ticker_ATR.csv`。
- **乘数语义**：换源后 `StudyPriceSpike` 的盘前 `0.5 × ATR` / 盘后 `0.2 × ATR` 与 `StudyOrderFlowReversal` 的 `EXT_ATR_MULT 0.6` / `EMA_ATR_MULT 0.25` 恢复「× ATR」的字面语义；SPY 上 ATR 路径阈值整体收窄 3.2 倍（见第 4 节）。
- **旧路径保留**：`/mw_api/atr` 路由与 `BBTicker.atr()` 本身、CSV 文件、写表任务均未改动（见第 6 节）。

## 3. 验证证据

### 3.1 调用点复查

```
grep -rn "getATR(\|getRealATR(" src/bbt/
```

4 个研究调用点全部为 `getRealATR`：`StudySatyATR:197`、`StudyOrderFlowReversal:446`、`StudyPriceSpike:105`、`StudyPriceSpike:178`。

**仅 `src/bbt/BBTTest.java:23` 仍调 `getATR("NVDA")`** —— 该文件是本地手工冒烟测试（`main()` 打印收盘价与 ATR），不属于任何研究信号链路，本轮按范围纪律未改。

### 3.2 编译

```
javac -nowarn -d /tmp/satyatr_build -cp "lib/*" src/bbt/*.java
→ exit 0
```

### 3.3 部署

`BBT_Studies/build` 下 `ant deploy` → **BUILD SUCCESSFUL**，34 个 class 文件拷入 `~/MotiveWave Extensions/dev`，`.last_updated` 已 touch（时间戳 2026-09-15 21:55）。

### 3.4 部署物反编译核验

`javap -v -p -cp . <class>`：

| class | 结果 |
|---|---|
| `bbt.StudyPriceSpike` | 含 `getRealATR` 引用 5 处 |
| `bbt.StudyOrderFlowReversal` | 含 `getRealATR` 引用 4 处 |
| `bbt.StudySatyATR` | 含 `getRealATR` 引用 4 处 |
| `bbt.FlaskBridge` | 含 `mw_api/atr_real` 3 处 |
| `bbt.BBTTest` | 仍含 `getATR` 4 处（预期内） |

### 3.5 取数链路实测（前一轮，仍适用）

| 请求 | 结果 |
|---|---|
| `/mw_api/atr_real?ticker=SPY` | 200 `5.98` |
| `/mw_api/atr?ticker=SPY`（旧路由） | 200 `19.16`（旧路由与方法保留未动） |

## 4. SPY 阈值影响

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

## 5. 未验证项（如实说明）

1. **三个研究在 MotiveWave 终端内的实际渲染与信号触发频率未做 GUI 实测**；
2. **阈值收窄 3.2 倍后尖峰样本量 / 信噪比的变化未做回测或实盘统计**；
3. **未做多标的遍历**（用户主用 SPY）。

## 6. 未纳入本轮范围

以下仍读同一份 CSV，本轮**未**改动，仍在消费可能过期的 ATR：

- `/mw_api/atr` 路由与 `BBTicker.atr()` 本身；
- CSV 文件 `Ticker_ATR.csv`；
- 写表任务 `PyTools/jobs/calc_atr.py`；
- Python 侧消费者 `PyTools/trading_view/`（5 个导出脚本）、`PyTools/option_chain/vantage.py`、`PyTools/spike_db/spikes_mw_to_csv.py`。

## 7. 归档与回滚

- **归档**：本目录 `67_2026-09-15_Cross_Study_Real_ATR_Unification/`（plan + walkthrough，`.md` / `.html` 双份）；`bbt_trading_modules.html` M18 演进行新增 1 行 + 计数同步。
- **回滚**：
  1. 把 3 处 `getRealATR` 还原为 `getATR` 并重新 `ant deploy` 即可；
  2. 或仅在 MotiveWave 中停用这两个研究；
  3. 影响面：取数链路为纯新增，回滚不影响其他研究。
