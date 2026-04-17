# Stock Analysis Skill

## Overview
This skill provides a conversational interface for querying **high‑confidence institutional signals** for any ticker over a user‑specified look‑back window (e.g., last 2‑3 weeks). It aggregates signals from three core sub‑skills:

- **Spike Analysis** (`/Users/zhijiebian/.gemini/skills/spike-analysis`)
- **Options Flow Analysis** (`/Users/zhijiebian/.gemini/skills/options-flow-analysis`)
- **Order‑Flow Big Trade Analysis** (`/Users/zhijiebian/.gemini/skills/order-flow-big-trade-analysis`)

The skill parses the natural‑language request (determining the ticker, look‑back period, and operation **Mode**), then calls the appropriate scripts, applies mode‑specific filtering, and returns a concise report.

---

## Operation Modes
### 1. Predict Mode (Default)
**Objective**: Forecast future price direction based on **active** institutional magnets.
- **Filtering**:
    - **Spikes**: Exclude any spike whose `target_price` has already been reached in price action.
    - **Options**: Exclude any flow where the contract expiration date has already passed.
- **Goal**: Present a "live" map of unresolved targets pulling or pushing price.

### 2. Backtest Mode
**Objective**: Validate institutional flow efficacy over a historical period.
- **Filtering**: NONE. Include all signals (hit, missed, or expired) within the specified window.
- **Goal**: Review the hit‑rate and statistical performance of the flow during the window.

---

## Capabilities
1. **Natural‑Language Query Parsing** – Detect ticker, time window, and **Mode** (`predict` vs `backtest`).
2. **Signal Retrieval** – Execute the following scripts and capture JSON output:
   - Spike signals: `spike-analysis/scripts/fetch_spikes.py <ticker> <date_range>`
   - Options flow signals: `options-flow-analysis/scripts/fetch_options_flow.py <ticker> <date_range>`
   - Order‑flow big‑trade signals: `order-flow-big-trade-analysis/scripts/fetch_big_trades.py <date_range>` (filter by ticker inside the script).
3. **Signal Filtering (Mode-Specific)**:
   - **Predict Mode**: Discard resolved spikes (target already hit) and expired option contracts. Use recent daily/hourly OHLC to verify spike status.
   - **Backtest Mode**: Retain all signals to measure historical price response.
### High-Importance Conviction Model

To maintain accuracy in directional forecasting, only signals meeting these "High-Importance" thresholds are included:

1. **Spikes**:
   - **PM (Pre-Market) Volume**: >= 10.
   - **RTH (Regular Trading Hours) Volume**: >= 50.

2. **Options Flow**:
   - **Primary Definition**: Refer to `/Users/zhijiebian/.gemini/skills/options-flow-analysis/SKILL.md` for all institutional modeling.
   - **Holistic Evaluation**: ALWAYS evaluate complex multi-leg spreads holistically (net premium bias) as defined in the base skill.
   - **High-Importance Thresholds**:
     - **D.AUTO single trade**: Total premium must be >= $5M.
     - **Multiple leg trade**: The premium of the largest individual leg must be >= $25M.

### Report Output Format (Mandatory)

Every generated report must be persisted in `/Users/zhijiebian/.gemini/cli-workspace/stock-analysis/` with the filename `Stock_Analysis_Query-<ticker>-<lookback>d_<YYYY-MM-DD_HH-MM-SS>.html`.

Structure:
1. **Original Instruction**: Quoted user request.
2. **Executive Summary**: Directional bias and precision metrics.
3. **Analytical Rationale**: Contextualizing institutional maneuvers (e.g., "Pinball" rebalancing).
4. **Signal Audit Trail**: A technical table at the bottom listing every validated marker.
5. **Aggregation & Scoring** – Combine signals, compute weighted confidence, and derive direction.
6. **Output Persistence** – Save the analysis as both Markdown and HTML files in the `/Users/zhijiebian/.gemini/cli-workspace/stock-analysis` directory.

---

## Execution Flow
1. **Parse Request** – Detect Ticker, Timeframe, and Operation Mode.
2. **Calculate Date Range**.
3. **Run Sub‑Skill Scripts**.
4. **Apply Mode Filtering**:
   - If `Mode == Predict`: Fetch current price action. For Spikes, if `high_since_execution >= target` (for bullish) or `low_since_execution <= target` (for bearish), discard. For Options, if `expiry < today`, discard.
5. **Apply Confidence Filter**.
6. **Combine Results** – Merge into a single list, sorted by timestamp.
6. **Generate Forecast** – Sum bullish vs bearish weighted scores, compute confidence % = (abs(bull_score - bear_score) / total_score) * 100.
7. **Return Markdown** – Format as described in *Capabilities*.
8. **Save Reports Locally** – After presenting the results in chat, save the Markdown and a rendered HTML version to the persistent storage at `/Users/zhijiebian/.gemini/cli-workspace/stock-analysis`.

---

## Output Persistence
In addition to the chat output, you MUST also save the analysis to the local filesystem for archival purposes:
- **Directory**: `/Users/zhijiebian/.gemini/cli-workspace/stock-analysis`
- **Markdown File**: `Stock_Analysis_Query-<ticker>-<lookback_days>d_<YYYY-MM-DD_HH-MM-SS>.md`
- **HTML File**: `Stock_Analysis_Query-<ticker>-<lookback_days>d_<YYYY-MM-DD_HH-MM-SS>.html`

The HTML file should be a direct render of the markdown output to ensure cross‑platform readability.

---

## Example Prompts & Expected Responses
### Prompt 1
`please find all the high confidence TSLA signals in the last 2 weeks`
**Response** (markdown):
```markdown
## High‑Confidence TSLA Signals (Last 14 Days)
| Time | Source | Type | Volume | Target | Hit Rate | Avg Days to Hit |
|------|--------|------|--------|--------|----------|-----------------|
| 2026‑04‑10 13:45 | Spike | RTH Magnet | 120 | 780.50 | 92.0% | 3.1 |
| 2026‑04‑08 09:12 | Options | Call Spread | 85 | 795.20 | 88.5% | 2.8 |
| 2026‑04‑06 15:30 | Order‑Flow | Big Trade | 300 | 770.00 | 95.0% | 1.9 |

**Overall Forecast**: **Bullish** with **84% confidence**.

*Rationale*: 3 high‑confidence signals, 2 from spikes and 1 from options, all bullish, weighted score 0.84.
```

### Prompt 2
`please use high confidence TSLA signals in the last 3 weeks to give a direction forecast with confidence level`
**Response** (markdown):
```markdown
## Direction Forecast (TSLA, Last 21 Days)
- **Bullish** – 78% confidence

**Key High‑Confidence Signals**:
- Spike (RTH) – 2 signals, avg hit‑rate 90%, avg days 3.2
- Options (Call) – 1 signal, hit‑rate 88%, avg days 2.5
- Order‑Flow – 1 signal, hit‑rate 95%, avg days 1.8

The majority of high‑confidence signals point upward, giving a strong bullish outlook.
```

---

## Integration Notes
- Place this `SKILL.md` under `/Users/zhijiebian/.gemini/skills/stock-analysis/`.
- Ensure the sub‑skill scripts output JSON (they already do for the daily reports).
- The orchestration can be implemented as a lightweight Python wrapper (e.g., `stock-analysis/scripts/run_query.py`) that reads the natural‑language request from stdin or an API call.
- The skill can be invoked by the Gemini agent via the standard skill‑lookup mechanism.

---

## Future Enhancements
- Add caching for recent signal queries to improve performance.
- Expose a REST endpoint for external services.
- Incorporate additional data sources (e.g., news sentiment) as optional modules.

---

*End of Skill Definition*
