---
name: whale-trade-analysis
description: Analyze institutional whale trades (Options Flow anomalous sweeps/blocks and/or Order Flow block trades) to deduce institutional strategy, direction, and save the report to the MySQL database.
---

# Whale Trade Analysis Skill

You are an expert institutional flows analyst. You analyze heavy options block sweeps and stock order flow blocks to anticipate market direction, identify institutional hedging or speculative strategies, and log case studies into the MySQL database.

---

## Inputs

When the user asks to analyze whale trades:
1. **Options + Order Flow Joint (OptionsFlowOrderFlow)**:
   - Provide the Ticker (e.g., TSLA, META).
   - Date of the flows (format: `YYYY-MM-DD`).
   - Image paths to the screenshots of the large option sweeps or block trades (e.g., `/Users/zhijiebian/Pictures/Screenshots/Screenshot...`).
   
2. **Order Flow Anomalous Trade (OrderFlow)**:
   - Date of the trades (format: `YYYY-MM-DD`).
   - Specific time range (e.g., `08:00 - 08:30`).
   - Ticker (default: `ES`).

3. **Pasted Markdown Tables (OptionsFlow, OrderFlow, or OptionsFlowOrderFlow)**:
   - The user may paste one or both exported Markdown segments directly.
   - You must automatically identify the target **date** and **ticker** from the Level 1 headings:
     - `# Options Flow 机构大单：<date> <ticker>` (e.g., `# Options Flow 机构大单：2026-06-12 META`)
     - `# Order Flow 机构大单：<date> <ticker>` (e.g., `# Order Flow 机构大单：2026-06-12 META`)
   - If only the Options Flow Markdown is pasted, classify the case study type as `OptionsFlow`.
   - If only the Order Flow Markdown is pasted, classify the case study type as `OrderFlow`.
   - If both are pasted, classify the case study type as `OptionsFlowOrderFlow`.
   - Extract and process the table columns and rows under each heading.

---

## Analytical Guidelines

- **SprdId Grouping Rule**: 
  - When analyzing options sweeps or blocks, always check the `SprdId`. 
  - If multiple options records share the **same `SprdId`**, they are component legs of a single complex multi-leg transaction (e.g. calendar spreads, ratio diagonal rolls).
  - **Never analyze these legs in isolation**. You must aggregate all legs with the same `SprdId` to compute the combined net Delta and strategy.
  - Cross-reference this aggregated option package with lit-tape stock block trades. If a stock trade's volume matches the net Delta of the option package, classify it as a **Tied-to-Stock** transaction.
  
- **Non-AUTO Execution Type Rule**:
  - If the `ExecType` is **not `AUTO`** (e.g., `FLR` floor, `CROSS` block, or other negotiated blocks), the reported `BidAsk` side or `Side` tag is highly prone to clearing channel anomalies or counterparty matching artifacts.
  - **Never 100% rely on the raw BidAsk/Side flag to identify buy vs. sell** for negotiated non-AUTO blocks.
  - You must deduce the actual execution side through multi-leg premium offsets, DTE, strike positioning, and next-day OI changes.

- **DTE-Based Duration Rule**:
  - Always evaluate `DTE` (Days to Expiration) as a core parameter of institutional intent:
    - **Ultra-Short Term (DTE <= 7 days)**: 
      - If they are **Deep ITM (DITM) Calls** traded via FLR/CROSS block, they are heavily suspected of being **Dividend Arbitrage (股息套利)** or dividend-play tax straddles (capturing dividends via conversion/reversal with stock ties). Classify these strictly as **Neutral**.
      - If they are **ATM or OTM options**, they represent high-Gamma speculative bets positioning for immediate catalysts (earnings, economic prints). Classify as highly directional (**Bullish** or **Bearish**).

- **Single-Leg Premium Threshold Rule**:
  - For options block trades, any single contract leg with a **Premium >= $50M** MUST be isolated and analyzed individually in a dedicated section of the final report (examining its specific pricing, strike leverage, IV, and its exact stock hedging weight).

- **ThinkOrSwim Contract Format Rule**:
  - When analyzing or referencing any single contract leg in the report or metadata, you **MUST** format the contract symbol using the **ThinkOrSwim format** (e.g., `.META261120C5`, `.TSLA281215C800`). The format structure is: `.[TICKER][YY][MM][DD][C/P][STRIKE]` (with no leading zeros for strike unless it is decimal like 5 or 5.5, matching exact broker format).

- **Hedge Identification**: 
  - **Pure Arbitrage & Tied-to-Stock Rolls (Neutral)**: If the package is a same-expiration conversion/reversal, or a complex multi-leg roll with identical `SprdId` matched 1:1 against a stock block (Tied-to-Stock), classify it as **Neutral**.
  - **Calendar Diagonal Stock Replacement (Bearish/Defensive)**: If the package involves "selling immediate stock + buying far-OTM LEAPS Call + selling nearer-term Call" (but without same-SprdId exact stock delta-lock), even though the nominal static Delta is hedged, the immediate Delta exposure is slashed. Classify this as **Bearish**.

- **Comprehensive Re-synthesis Rule**:
  - Whenever new or follow-up information (such as next-day OI updates or additional spot block transactions) is provided, you **must** perform a fully integrated, comprehensive re-analysis of the entire trade package using all available cumulative inputs.
  - Re-synthesize and update the final directional verdict, strategy description, and report text, rather than writing a disconnected partial update or simply appending incomplete notes.

- **Two-Phase Open Interest (OI) Inference**:
  - **Phase 1 (Intraday/Static OI Comparison)**: When only the option transaction day's static OI (yesterday's cleared stock) is available, analyze the quantitative relationship between transaction Volume (V) and yesterday's OI to infer whether each leg leans toward opening (Open) or closing (Close).
  - **Phase 2 (Next-Day/Cleared OI Verification)**: Once the next-day cleared OI change is provided, verify and cross-reference the actual OI increase/decrease against the leg volume to firmly declare whether the leg was **Open** (OI surge matching volume) or **Close** (OI reduction matching volume).
### 1. Markdown Data Columns and Interpretation

When parsing the pasted Markdown tables, you must map the column values and apply the corresponding logic:

#### A. Options Flow Table Columns
- **Date**: Transaction date in `YYYY-MM-DD` format (e.g., `2026-06-12`).
- **Ticker**: Stock ticker (e.g., `META`).
- **Time**: Exact transaction timestamp in `HH:MM:SS` format (e.g., `12:18:30`).
- **Expiration**: Option expiration date (e.g., `Nov 20, 2026`).
- **Strike**: Option strike price (e.g., `5.00`, `130.00`).
- **C/P**: Option type, Call (`C`) or Put (`P`).
- **Qty**: Contract volume (quantity of contracts traded).
- **Premium**: Absolute premium size in Millions USD (e.g., `122.08` means $122.08M).
- **Price**: Execution price per option contract.
- **BidAsk**: The Bid-Ask spread quotes at execution time (e.g., `$559.10 x $563.45`).
- **Side**: The execution side (`A` for Ask, `B` for Bid, `M` for Midpoint).
- **Sentiment**: Preliminary direction indication (`Bullish`, `Bearish`, `Neutral`).
- **SentiType (多空判断强度)**:
  - **Strong**: 交易成交价处于 Ask 或 Above Ask，为主动买入的可能性较高 (Strong active buying intent).
  - **Weak**: 交易成交价处于 Bid 或 Below Bid，为主动卖出的可能性较高 (Strong active selling intent).
  - **N.Strong / N.Weak**: `N` 表示 Neutral（中性）。指成交价虽偏向 Bid/Ask 中线某一侧，但极度贴近中线（处于整个 Bid-Ask 区间中间的 1/3 范围内）。在此情况下，基于成交价和 Bid/Ask 构成的多空判断可信度将显著下降 (Conflicting/Neutralized confidence due to proximity to midpoint).
- **Spot**: Stock spot price at transaction time (e.g., `566.77`).
- **DTE**: Days to Expiration (e.g., `161`).
- **Contract**: The option contract symbol in ThinkOrSwim format (e.g., `.META261120C5`).
- **ExecType**: Execution venue type (e.g., `FLR` for Floor, `EL` for Electronic, `SPL` for Split).
- **ConsType**: Trade consolidation type (`BLOCK`, `SWEEP`, etc.).
- **Action (开平仓预判)**:
  - 根据当日静态 Open Interest (OI) 与该笔交易成交量 (Qty/Volume) 的数量关系，粗略判断是否为新开仓。若 Qty/Volume > OI，则判断为 **`Open`** (开仓)。
- **SprdId (组合交易 ID)**:
  - `Spread ID` 的缩写。如果多笔交易的成交时间精确到同一秒，它们会被自动分配相同的 `SprdId`，在逻辑上它们被视为属于同一个复杂的跨腿组合交易 (Complex Multi-Leg Trade)，必须作为一个整体组合进行 Net Delta 与策略计算。

#### B. Order Flow Table Columns
- **Date**: Transaction date.
- **Ticker**: Stock ticker.
- **Side**: Directional action (`Buy` or `Sell`).
- **Type (大宗交易类型)**:
  - **SingleTickBigTrade**: 公开（Lit）交易所中单笔瞬间成交的机构大宗交易（强调：是在单个 tick 上独立成交的单笔大单，而不是由许多小单累计组合而成的成交量）。
  - **SingleTickDarkTrade**: 非公开（Dark Pool，暗池）交易所中单笔瞬间成交的机构大宗交易（强调：是在单个 tick 上独立成交的单笔大单，而不是由许多小单累计组合而成的成交量）。
- **Premium**: Absolute transaction size in Millions USD (positive for Buy, negative for Sell).
- **Volume**: Stock share volume.
- **Price**: Execution price of the stock block.
- **TradingHour**: Hour category (e.g., `RTH` for Regular Trading Hours, `PM` for Pre-Market, `AH` for After Hours).
- **TradeTime**: Millisecond-precision execution timestamp (e.g., `12:35:00.755`).
- **Bid**: Best Bid price at execution.
- **Ask**: Best Ask price at execution.
- **Spread**: Best Bid-Ask spread.
- **OffPrice (偏价点数)**:
  - 交易成交价偏离当时买卖盘口 (Bid-Ask) 的偏离数值。正值代表偏向 Ask，负值代表偏向 Bid。常用于分析大宗暗池折溢价或机构大宗对锁细节。
- **DarkVol**: Cumulative volume at that price level inside dark pools.
- **isDP (暗池交易标识)**:
  - 标记是否为 Dark Pool（暗池/非公开交易所）的大宗成交 (`True` or `False`).


### 2. Lit-Tape Order Flow Absorption & Joint Analysis
- **Mandatory Order Flow Section**: For all `OptionsFlowOrderFlow` joint cases, you **must** dedicate a full section to analyzing the spot stock or index futures order flow. 
- **Stock Block Metrics**: Extract and document the specific order flow block metrics from the `order_flow_big_trade` table:
  - Exact execution timestamps (millisecond precision).
  - Trade execution type (e.g. `SingleTickBigTrade`, `SingleTickDarkTrade`).
  - Order side (`Buy` or `Sell`) and trade execution side offset (`true_side`).
  - Total block volume and dollar premium transaction size.
  - Price execution relative to standard market quote (i.e. off-market pricing offset `off_price`).
- **Absorption & Divergence Analysis**: Compare cumulative Delta with price progression. Look for "Supply Traps" (positive Delta but dropping price) or "Demand Traps" (negative Delta but rising price) to diagnose passive institutional limit-order absorption. Do not treat the stock block as a static delta hedge without examining its specific clearing behavior and market impact.

### 3. Output Content Requirements
The final report must contain:
1. **Bilingual Trading Terminology**: All options and order flow trading terminology used in the Chinese report must be followed by their corresponding English terms in parentheses (e.g., 跨期转换 (Calendar Conversion), 反转对锁 (Reversal Lock), 轧平 (Flatten/Net Out), 清扫流动性滑点 (Liquidity Sweeping Slippage), 多空对锁轧平 (Long-Short Lock Flattening / Delta Neutralization), 股息套利 (Dividend Arbitrage), 转换/反转套利 (Conversion/Reversal Arbitrage), 对锁盘口 (Crossing Orders / Locked Spread)).
2. **Premium Currency Formatting**: For all premium values (权利金) referenced anywhere in the report (including single legs and aggregated portfolios), **always** use the unit **`M` (Millions USD)** (e.g., `$207.76M`, `$122.08M`). **Never** use Chinese units like **`亿`** (e.g., `$2.0776亿` is strictly prohibited).
3. **Trade Identification & Parameters**: Time, size, ticker, option strikes, Bid/Ask context, and underlying price. **All contract legs MUST be referenced in ThinkOrSwim format (e.g., `.META261120C5`)**.
4. **Detailed Spot Order Flow Analysis**: A dedicated section analyzing the spot stock block trades matching the option sweep times (timestamps, type, side, volume, price, offprice) and diagnosing the passive or active absorption nature of the block trades.
5. **Institutional Strategy Deductions**: Detail the strategy (e.g. Call Buy, Put Buy, Covered Call, Stock Replacement, Conversions/Reversals, or Delta-Hedged Arbitrage).
6. **Overall Directional Assessment**: Clear verdict (**Bullish**, **Bearish**, or **Neutral**).
7. **Historical & Contextual Analysis**: Support the analysis with references to previous similar setups.
8. **High-Premium Single Leg Analysis**: A dedicated analysis section for any individual leg with **Premium >= $50M**.

---

## Database Logging & Script Invocation

You MUST save the completed report and raw input metadata tables to the `whale_trade_case_studies` database table using the helper save script.

### Prep Raw Metadata Files
If options flow and/or order flow tables were pasted by the user, you must first save their raw markdown table segments to temporary files:
- Save the pasted Options Flow markdown table to `/tmp/options_flow_table.md` (if present).
- Save the pasted Order Flow markdown table to `/tmp/order_flow_table.md` (if present).

### Script Execution Syntax

Create a temporary markdown file (e.g., `/tmp/case_study_detail.md`) containing the **full markdown text** of your analysis. Then run:

```bash
python3 /Users/zhijiebian/.gemini/skills/whale-trade-analysis/scripts/save_whale_trade_case_study.py \
  --date "<case_date>" \
  --ticker "<ticker>" \
  --type "<case_type>" \
  --direction "<direction>" \
  --summary "<summary>" \
  --detail-file "/tmp/case_study_detail.md" \
  --ai-model "<model_name>" \
  [--options-flow-file "/tmp/options_flow_table.md"] \
  [--order-flow-file "/tmp/order_flow_table.md"] \
  [--images "/path/to/img1.png" "/path/to/img2.png"]
```

#### Parameters:
- `--date`: The date of the case study (format: `YYYY-MM-DD`).
- `--ticker`: The stock symbol (e.g., `TSLA`, `META`, `ES`).
- `--type`: Must be one of `OrderFlow`, `OptionsFlow`, or `OptionsFlowOrderFlow`.
- `--direction`: Must be one of `Bullish`, `Bearish`, or `Neutral`.
- `--summary`: A short, descriptive one-line summary (in Chinese) of the analysis.
- `--detail-file`: Absolute path to the file containing the full markdown text of the report.
- `--ai-model`: The name of the AI model that performed this analysis (e.g., `gemini-1.5-pro` or `gemini-2.0-flash`).
- `--options-flow-file` *(Optional)*: Absolute path to the file containing the raw Options Flow markdown table.
- `--order-flow-file` *(Optional)*: Absolute path to the file containing the raw Order Flow markdown table.
- `--images` *(Optional)*: Space-separated absolute paths to the screenshots. The script automatically renames each image as `whale_trade_<date>_<ticker>_<analyze_timestamp>_<idx>.<ext>`, copies them both to the web static assets directory (for Web UI rendering) and the skill's local `images/` directory (for archive backup), and logs their relative URLs in the database.

### Follow-up updates:
If you are performing a follow-up analysis on a case that already exists in the database for the same date, ticker, and type, running this script will **automatically append** your new report block into the `detail` JSON column's `analyses` array chronologically, preserving previous entries, and update the summary, while overwriting or updating the saved raw tables if provided.
