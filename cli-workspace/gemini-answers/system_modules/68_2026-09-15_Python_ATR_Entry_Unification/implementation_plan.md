# Python 侧 ATR 取数统一：实算入口与绕道映射清理 —— 实施计划

- **日期**：2026-09-15
- **模块**：68 `Python_ATR_Entry_Unification`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施 + Python 量化取数工具链）
- **触发事件**：用户追加指令（原文）：「要一并切到实算 ATR」——即把**仍在读 `Ticker_ATR.csv` 的 Python 侧消费者**一并切到实算 ATR。
- **前序与本轮关系**：本归档是 `67_2026-09-15_Cross_Study_Real_ATR_Unification` 的**后续扩展**。67 已完成 Java 侧 3 个研究调用点（`StudyPriceSpike` 2 处 + `StudyOrderFlowReversal` 1 处）由 `getATR` 切至 `getRealATR`；67 文档「未纳入本轮范围」一节中列出的 Python 消费者在本轮被纳入。
  **本轮取代 67 的该项边界说明**：67 第 5 节与 walkthrough 第 6 节所记「Python 侧消费者 `PyTools/trading_view/`、`PyTools/option_chain/vantage.py`、`PyTools/spike_db/spikes_mw_to_csv.py` 仍读 CSV，本轮未改」这一边界，自本轮起不再成立；67 文档本身保持历史记录原样，不作修改。
- **用户口径**：
  1. 「两个研究仍在读那张已弃用的 CSV 统一改成不用那个CSV」（前序指令，已完成，归档于 67）；
  2. 「我只需要用在 SPY 上」（主用标的 SPY）；
  3. 「要一并切到实算 ATR」（本轮指令）。
- **技术栈**：Python 3 · `PyTools/py_lib/bb_tickers.py`（`BBTicker` 统一 ATR 入口）· Schwab 日线 API（`BBTOS.atr_wilder()`）· yfinance（`BBYF.atr_wilder()`，兜底）· Wilder RMA ATR(14) · Flask（`bbt_data_web`，`/mw_api/atr` 与 `/mw_api/atr_real`）· pandas（`Ticker_ATR.csv` 读表兜底）· 日志 `warning`

---

## 1. 背景与目标

67 已把 Java 侧研究指标的 ATR 取数切至实算链路（`/mw_api/atr_real`），但 Python 侧消费者仍统一经 `BBTicker.atr(ticker)` 取数，而该方法**优先读取 `Ticker_ATR.csv`**。因此存在口径分裂：

- Java 研究走实算 Wilder ATR(14)；
- Python 侧（TradingView 导出脚本、期权链、尖峰导出等）仍消费同一份被判定为过期 / 串行数据的 CSV。

本轮目标是把 Python 侧统一切到实算口径，并清理当年为绕过 CSV 缺行而设的「绕道映射」。范围纪律：**只动 Python 侧取数入口与 1 处绕道映射**，不改 Java 侧、不改 CSV 文件本身、不改无关脚本。

## 2. 改动清单（2 个文件）

| 文件 | 改动 |
|---|---|
| `PyTools/py_lib/bb_tickers.py` | `BBTicker.atr(ticker)` 重写为**统一入口**：优先 `atr_real()`（Schwab 日线 Wilder ATR(14) → yfinance Wilder 兜底，符号自行解析 `ES→/ES`、`SPX→$SPX`），`Ticker_ATR.csv` **降级为「实算链路全部失败时的最后兜底」**并写 warning 日志；新增私有 `_atr_from_csv(ticker)` 承载旧读表逻辑（仅在兜底内保留 `ES→SPX` / `NQ→NDX` 近似映射）；**删除**原先的 `BBTOS.atr()` / `BBYF.atr()`（SMA 口径）兜底链与末尾 `return 2.0` 硬编码 |
| `PyTools/trading_view/tv_order_flow_big_trade_single_tick_by_trading_hour.py` | `ticker_map_atr = {"ES": "SPX", "NQ": "NDX"}` → 清空为 `{}`（保留变量以便日后覆盖），并加注释说明：该映射是当年旧 CSV 无 ES/NQ 行的绕道，而 Pine 目标是 `ES1!`/`NQ1!` 期货图，故应取期货自身 ATR；实测差异 ES 期货 `70.08` vs SPX `60.17`（约 14%） |

## 3. 设计要点：统一入口的优先级与失败语义

- **入口优先级**：`BBTicker.atr(ticker)` → `atr_real(ticker)`（Schwab 日线 Wilder ATR(14) 主源，yfinance Wilder 兜底）→ 失败时 `_atr_from_csv(ticker)` 读 `Ticker_ATR.csv` 并写 warning 日志。
- **CSV 的新定位**：由「优先数据源」降级为「实算链路全部失败时的最后兜底」；这是为避免实算链路整体不可用时调用方直接崩断而保留的降级路径，不再是常规取数路径。
- **兜底内映射的保留理由**：`_atr_from_csv()` 内的 `ES→SPX` / `NQ→NDX` 近似映射仅在最后兜底内保留——因为 CSV 表内没有 ES/NQ 行；该映射属兜底路径的近似手段，不参与常规实算路径。
- **失败语义变更**：实算与 CSV 兜底**全部失败**时返回 `None`（原实现末尾硬编码 `return 2.0`）。该变更把「静默返回假值」改为「显式空值」，调用方需判空。
- **符号解析归属**：实算链路内部自行解析券商符号（`ES→/ES`、`SPX→$SPX`），调用方仍传裸符号，接口表面不变。

## 4. 未改动项（避免误解，逐条列明）

以下本轮**未改动**：

| 项 | 未改动的理由 |
|---|---|
| Java 侧 3 个研究调用点（`StudyPriceSpike` 2 处、`StudyOrderFlowReversal` 1 处） | 已在 67 完成；且 `atr_real` 路由未变，**无需重新部署** |
| `PyTools/trading_view/tv_order_flow_big_trade_by_time_range.py`、`tv_order_flow_big_trade_daily.py` 的 `ticker_map = {"ES": "SPY", "NQ": "QQQ"}` | 该映射是因为这两个脚本生成的 Pine 目标是 **SPY/QQQ 图**、收盘价也取 SPY/QQQ，属正当映射，必须保留 |
| `tv_dp_single_ticker.py`、`option_chain/vantage.py`、`spike_db/spikes_mw_to_csv.py` 的调用点 | 它们经统一入口自动生效，无需改代码 |
| CSV 文件 `Ticker_ATR.csv`、写表任务 `PyTools/jobs/calc_atr.py` | 本轮未改；该表降级为兜底，写表任务下次运行会把真实 ATR 写回表中（见第 6 节） |

## 5. 行为变化

### 5.1 ATR 值

| 标的 | 旧值（CSV 口径） | 新值（实算口径） | 说明 |
|---|---|---|---|
| SPY | `19.16` | `5.98` | 缩小 **3.2 倍** |
| ES | CSV 时代走 SPX `49.31` | 期货实算 `70.08` | 由「近似映射到 SPX」改为「期货自身」 |

### 5.2 生成 Pine 的 factor

| 脚本 | Pine 目标 | factor 公式 | 变化 |
|---|---|---|---|
| `tv_order_flow_big_trade_by_time_range.py` / `tv_order_flow_big_trade_daily.py` | SPY / QQQ 图 | `factor = (0.5 × ATR) / max_volume` | factor 缩小 3.2 倍，标记高度回到「0.5 × ATR」字面语义 |
| `tv_order_flow_big_trade_single_tick_by_trading_hour.py` | `ES1!` / `NQ1!` | `factor = (2 × ATR) / max_volume` | ATR `49.31 → 70.08`，factor 放大 `1.42 倍` |

### 5.3 失败语义

- `BBTicker.atr()` 在实算与 CSV 兜底**全部失败**时返回 `None`（原先末尾硬编码返回 `2.0`）。
- 判空现状：
  - `tv_dp_single_ticker.py` 第 194 行已有 `if atr is None or atr <= 0` 判空；
  - `option_chain/vantage.py` 用 `or BBYF.atr(ticker)`；
  - **`tv_order_flow_big_trade_by_time_range.py` 与 `tv_order_flow_big_trade_daily.py` 直接参与 `(0.5 * atr)` 运算，无判空** —— 仅在「实算失败且该标的不在 CSV 表内」时才会触发 TypeError（实测当前数据下不会发生），属已知残余风险。

## 6. 对定时任务的影响

定时任务 `PyTools/jobs/calc_atr.py` 仍调用 `BBTicker.atr()` 并写回该表：由于入口已实算，该任务下次运行会把**真实 ATR 写回表中**，原先「读表 → 写回表」的自引用闭环自然消除。

**本轮未执行该任务**（写用户配置文件需其确认）。

## 7. 验收标准

1. **编译检查**：`py_compile` 两个改动文件 → **OK**；
2. **统一入口实算值正确**：`BBTicker.atr()` 返回 SPY `5.98`、QQQ `8.77`、ES `70.08`、NQ `431.75`、SPX `60.17`、TSLA `13.11`；
3. **降级行为正确**：monkeypatch `atr_real` 返回 `None` 模拟实算全失败时，SPY → `19.16`（CSV 值）并写出 warning 日志；表内不存在的标的 → `None`；
4. **真实 HTTP 一致**：Flask 5005（debug 自动重载已生效）`/mw_api/atr` 与 `/mw_api/atr_real` 两条路由对同一标的值一致；
5. **消费者收敛**：`grep -rn "Ticker_ATR\|atr_config_file" --include=*.py` 显示全部 9 处调用点均经统一入口；直接读该表的代码仅剩 `_atr_from_csv()` 兜底；
6. **归档**：本目录（plan + walkthrough，`.md` / `.html` 双份）与 `bbt_trading_modules.html` M18 演进行同步。

## 8. 回滚方式

1. 恢复 `BBTicker.atr()` 原实现（读表优先），或
2. `git revert` 这两个文件；
3. Java 侧无需回滚（本轮未动，且 67 的 `atr_real` 路由口径未变）。
