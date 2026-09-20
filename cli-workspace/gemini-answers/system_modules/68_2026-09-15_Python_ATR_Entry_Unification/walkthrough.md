# Python 侧 ATR 取数统一：实算入口与绕道映射清理 —— 验收报告 (Walkthrough)

- **日期**：2026-09-15
- **模块**：68 `Python_ATR_Entry_Unification`（归属能力域：**M18 交易基础设施与开发环境工具链** · MotiveWave 终端 Java SDK 研究基础设施 + Python 量化取数工具链）
- **对应计划**：`implementation_plan.md`（同目录）
- **前序与本轮关系**：本归档是 `67_2026-09-15_Cross_Study_Real_ATR_Unification` 的**后续扩展**；**本轮取代 67 的该项边界说明** —— 67 第 5 节与 walkthrough 第 6 节所记「Python 侧消费者仍读 CSV、本轮未改」自本轮起不再成立，67 文档保持历史记录原样未作修改。
- **状态**：✅ 2 个文件改动全部落盘；`py_compile` 两文件 → **OK**；统一入口实算值、降级路径与真实 HTTP 三条路由均实测通过；消费者清单经 `grep` 核实收敛
- **影响面**：Python 侧 ATR 统一入口 `BBTicker.atr()` + `tv_order_flow_big_trade_single_tick_by_trading_hour.py` 的 ATR 绕道映射；经统一入口间接影响的消费者包括 4 个 TV 导出脚本、`option_chain/vantage.py`、`spike_db/spikes_mw_to_csv.py`、`tv_dp_single_ticker.py`

---

## 1. 交付物清单（代码）

| 文件 | 交付内容 |
|---|---|
| `PyTools/py_lib/bb_tickers.py` | `BBTicker.atr(ticker)` 重写为**统一入口**：优先 `atr_real()`（Schwab 日线 Wilder ATR(14) → yfinance Wilder 兜底，符号自行解析 `ES→/ES`、`SPX→$SPX`），`Ticker_ATR.csv` **降级为「实算链路全部失败时的最后兜底」**并写 warning 日志；新增私有 `_atr_from_csv(ticker)` 承载旧读表逻辑（仅在兜底内保留 `ES→SPX` / `NQ→NDX` 近似映射）；**删除**原先的 `BBTOS.atr()` / `BBYF.atr()`（SMA 口径）兜底链与末尾 `return 2.0` 硬编码 |
| `PyTools/trading_view/tv_order_flow_big_trade_single_tick_by_trading_hour.py` | `ticker_map_atr = {"ES": "SPX", "NQ": "NDX"}` → 清空为 `{}`（保留变量以便日后覆盖），并加注释说明：该映射是当年旧 CSV 无 ES/NQ 行的绕道，而 Pine 目标是 `ES1!`/`NQ1!` 期货图，故应取期货自身 ATR；实测差异 ES 期货 `70.08` vs SPX `60.17`（约 14%） |

## 2. 关键机制（最终口径）

- **统一入口**：`BBTicker.atr(ticker)` 是 Python 侧唯一 ATR 取数入口；所有消费者经此入口自动切到实算口径，无需逐个改代码。
- **优先级**：`atr_real()`（Schwab 日线 Wilder ATR(14) 主源 → yfinance Wilder 兜底）→ 全部失败时 `_atr_from_csv()` 读 `Ticker_ATR.csv` 并写 warning 日志。
- **CSV 新定位**：由「优先数据源」降级为「最后兜底」；兜底内仅保留 `ES→SPX` / `NQ→NDX` 近似映射（因表内无 ES/NQ 行），不参与常规实算路径。
- **绕道映射清理**：`tv_order_flow_big_trade_single_tick_by_trading_hour.py` 的 `ticker_map_atr` 清空 —— 该脚本 Pine 目标是期货图（`ES1!`/`NQ1!`），应取期货自身 ATR，而非近似映射到 SPX/NDX。
- **失败语义**：实算与 CSV 兜底全部失败时返回 `None`（原为硬编码 `return 2.0`），把「静默返回假值」改为「显式空值」。
- **正当映射保留**：`tv_order_flow_big_trade_by_time_range.py` 与 `tv_order_flow_big_trade_daily.py` 的 `ticker_map = {"ES": "SPY", "NQ": "QQQ"}` 保留 —— 这两个脚本生成的 Pine 目标为 SPY/QQQ 图、收盘价也取 SPY/QQQ。
- **Java 侧零改动**：Java 3 个研究调用点已在 67 完成，`atr_real` 路由未变，**无需重新部署**。

## 3. 验证证据

### 3.1 编译检查

```
py_compile PyTools/py_lib/bb_tickers.py
py_compile PyTools/trading_view/tv_order_flow_big_trade_single_tick_by_trading_hour.py
→ OK
```

### 3.2 统一入口实算值

`BBTicker.atr()` 实测返回值：

| 标的 | 实算 ATR |
|---|---|
| SPY | `5.98` |
| QQQ | `8.77` |
| ES | `70.08` |
| NQ | `431.75` |
| SPX | `60.17` |
| TSLA | `13.11` |

### 3.3 兜底路径验证（模拟实算全失败）

以 monkeypatch 令 `atr_real` 返回 `None` 模拟实算链路全部失败：

| 场景 | 结果 |
|---|---|
| SPY | → `19.16`（CSV 值，符合降级预期）并写出 warning 日志 |
| 表内不存在的标的 | → `None`（调用方需判空） |

### 3.4 真实 HTTP（Flask 5005，debug 自动重载已生效）

| 请求 | 结果 |
|---|---|
| `/mw_api/atr?ticker=SPY` | `5.98` |
| `/mw_api/atr?ticker=ES` | `70.08` |
| `/mw_api/atr?ticker=SPX` | `60.17` |
| `/mw_api/atr_real?ticker=SPY` | `5.98` |

两条路由（`/mw_api/atr` 与 `/mw_api/atr_real`）对同一标的返回值一致。

### 3.5 消费者清单核实

```
grep -rn "Ticker_ATR\|atr_config_file" --include=*.py
```

| 结论 | 说明 |
|---|---|
| 全部 9 处调用点均经统一入口 | `BBTicker.atr()` |
| 直接读该表的代码仅剩 `_atr_from_csv()` 兜底 | 常规路径不再直读 CSV |
| `PyTools/jobs/backfill_option_chain_from_vtg.py` 第 11 行 `atr_config_file` | **未使用的死变量**（仅声明） |
| `PyTools/jobs/calc_atr.py` | 仍写该表（写表任务未改） |

## 4. 行为变化对照

### 4.1 ATR 值

| 标的 | 旧值 | 新值 | 变化 |
|---|---|---|---|
| SPY | `19.16`（CSV） | `5.98`（实算） | 缩小 **3.2 倍** |
| ES | CSV 时代走 SPX `49.31` | 期货实算 `70.08` | 由「近似映射到 SPX」改为「期货自身」 |

### 4.2 生成 Pine 的 factor

| 脚本 | Pine 目标 | factor 公式 | 变化 |
|---|---|---|---|
| `tv_order_flow_big_trade_by_time_range.py` / `tv_order_flow_big_trade_daily.py` | SPY / QQQ 图 | `factor = (0.5 × ATR) / max_volume` | factor 缩小 **3.2 倍**，标记高度回到「0.5 × ATR」字面语义 |
| `tv_order_flow_big_trade_single_tick_by_trading_hour.py` | `ES1!` / `NQ1!` | `factor = (2 × ATR) / max_volume` | ATR `49.31 → 70.08`，factor 放大 **`1.42 倍`** |

### 4.3 失败语义与判空现状

- `BBTicker.atr()` 在实算与 CSV 兜底**全部失败**时返回 `None`（原先末尾硬编码返回 `2.0`）。
- 判空现状：
  - `tv_dp_single_ticker.py` 第 194 行已有 `if atr is None or atr <= 0` 判空；
  - `option_chain/vantage.py` 用 `or BBYF.atr(ticker)`；
  - **`tv_order_flow_big_trade_by_time_range.py` 与 `tv_order_flow_big_trade_daily.py` 直接参与 `(0.5 * atr)` 运算，无判空** —— 仅在「实算失败且该标的不在 CSV 表内」时才会触发 TypeError（实测当前数据下不会发生），属**已知残余风险**。

## 5. 未验证项（如实说明）

1. **4 个 TV 导出脚本与 `option_chain/vantage.py`、`spike_db/spikes_mw_to_csv.py` 未实际运行** —— 脚本涉及 MySQL 与产物文件写入，未执行以免产生副作用；
2. **生成 Pine 的 factor 数值变化未做终端内可视化确认**；
3. **未做回测 / 实盘统计**。

## 6. 定时任务与回滚

- **定时任务** `PyTools/jobs/calc_atr.py`：仍调用 `BBTicker.atr()` 并写回该表；由于入口已实算，该任务下次运行会把**真实 ATR 写回表中**，原先「读表 → 写回表」的自引用闭环自然消除。**本轮未执行该任务**（写用户配置文件需其确认）。
- **归档**：本目录 `68_2026-09-15_Python_ATR_Entry_Unification/`（plan + walkthrough，`.md` / `.html` 双份）；`bbt_trading_modules.html` M18 演进行新增 1 行 + 计数同步。
- **回滚**：
  1. 恢复 `BBTicker.atr()` 原实现（读表优先）；
  2. 或 `git revert` 这两个文件；
  3. Java 侧无需回滚（本轮未动，且 67 的 `atr_real` 路由口径未变）。
