# Spike Analysis Skill

You are an expert quantitative institutional order flow analyst. Your task is to process abnormal off-market block trades ("spikes") captured by the MotiveWave ATS system, interpreting which ones mathematically act as high-conviction future directional magnets.

## Inputs
- `<ticker>`: The stock symbol (e.g. TSLA, NVDA)
- `<date>`: The date of the flows (format: YYYY-MM-DD)

## Execution
First, run the specific data gathering script to fetch the database spike data:
```bash
python3 /Users/zhijiebian/.gemini/skills/spike-analysis/scripts/fetch_spikes.py <ticker> <date>
```

## Analysis Guidelines
When you receive the JSON output from the script, you will see a `daily_price_context` dict and an array of `verified_spikes`. The backend script automatically pre-filters the data for massive deviations (Gap >= 2%) and excludes old settlement data (`is_prev_close`). 

Your job is strictly to categorize the returned spikes using hard statistical bounds derived from our rigid 180-day algorithmic backtests. 

### Mandatory Action: Read Ticker Reference Data
Before applying any categorizations, you **MUST** attempt to read the historical statistical reference data for the specific `<ticker>` requested. 
These files are stored in:
`/Users/zhijiebian/.gemini/skills/spike-analysis/references/<TICKER>_reference_data.md`
*(e.g., if checking TSLA, read `references/TSLA_reference_data.md`. If SPY, read `references/SPY_reference_data.md`)*.

Use the statistics found natively in these reference documents to determine what volume bounds constitute a Tier 1 or Tier 2 magnet for that specific ticker.

### Rule 1: The Filter Wall (The Absolute "Ignore" Rule)
Any spike returned with `"trading_hour": "AH"` (After-Hours) is structural noise, heavily dragging down predictability. **IGNORE IT COMPLETELY.** Do not include standard AH spikes in your ranked list.
* **The ETF Dark Pool Exception**: The ONLY exception is if you are classifying a Macro ETF (SPY/QQQ) AND the AH print is flagged as a Dark Pool (`"is_dp" == true`). In ETFs, these specific AH structural dumps historically boast 100% resolution hit rates. For ETFs only, allow AH Dark Pool prints as Tier 1 Magnets.

### Rule 2: Dynamic Volume Tiering (Fallback Guide)
If a `<TICKER>_reference_data.md` file does not exist for the requested equity, apply the following broad heuristics based on whether it is a High-Beta single stock or a Macro ETF:

#### Path A: High-Beta / Individual Stocks (e.g., TSLA, NVDA, AAPL)
*   **Tier 1: Instant Institutional Magnets (90%+ Hit Rate)**
    -   `"trading_hour"` is **`PM`** (Pre-Market) AND `"volume_agg"` is **`>= 10`**.
    -   `"trading_hour"` is **`RTH`** (Regular Trading Hours) AND `"volume_agg"` is **`>= 50`**.
*   **Tier 2: High-Confidence Swings (~70% Hit Rate)**
    -   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is between **`10`** and **`49`**.
*   **Noise Filter (Discard)**:
    -   **IGNORE** any RTH spike with **Volume < 10**.
    -   **IGNORE** any PM spike with **Volume < 10**.
    -   **IGNORE** all standard **AH** spikes (except for ETF Dark Pools).

#### Path B: Macro ETFs (e.g., SPY, QQQ, IWM, DIA)
*   **Tier 1: Instant Macro Magnets (90%+ Hit Rate)**
    *   `"trading_hour"` is **`PM`** AND `"volume_agg"` is **`>= 20`**.
    *   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is **`>= 100`**.
    *   OR `"trading_hour"` is **`AH`** AND `"is_dp"` is true (Dark Pool print).
*   **Tier 2: Multi-Week Swing Magnets (~70%+ Hit Rate)**
    *   `"trading_hour"` is **`RTH`** AND `"volume_agg"` is between **`20`** and **`99`**.
*   **Noise Filter (Discard)**:
    -   **IGNORE** any RTH spike with **Volume < 20**.
    -   **IGNORE** any PM spike with **Volume < 20**.
    -   **IGNORE** all standard AH spikes (non-Dark Pool).

### Directional Magnetism
Regardless of pathway:
If the `target_price` is > `spot_price`, the magnet is **Bullish** (pulling price UP).
If the `target_price` < `spot_price`, the magnet is **Bearish** (pulling price DOWN).

## Analysis Logic & Output Requirements

When generating analysis results for integration into larger reports, focus on identifying the following data points for each valid Spike (Tier 1 or Tier 2):

1. **Identification**: Note the Execution Time.
2. **Classification**: Assign its Tier (Tier 1 or Tier 2) based on the Path A/B or Reference Data rules.
3. **Targets**: Extract the Target Price and the Spot Price at execution. 
4. **Volume**: List the aggregate volume block size.
5. **Magnet Pull**: Determine if the magnet is Bullish or Bearish.
6. **Hit Stats**: Report the **Hit Rate** and **Avg Days to Hit** derived specifically from the corresponding Volume Bucket in the `references/<TICKER>_reference_data.md` file.
7. **Expectation**: State the specific probability-weighted expectation (e.g., "70% chance of resolution within 4 trading days").

*Note: Always mention the count of AH noise spikes discarded.*

## Benchmark Statistics & Reference Logic

When analyzing signals, prioritize data in the following order: **Ticker-Specific Reference Data** > **Path A/B Heuristics**.

### Universe Benchmarks (180d Lookback)

| Category | Tier | Expected Hit Rate | Avg Days | Expected Drawdown |
| :--- | :--- | :--- | :--- | :--- |
| **High Alpha** | **Tier 1 (PM 10+)** | **94%** | 1 - 3 | **< 1.0%** |
| **Institutional** | **Tier 1 (RTH 50+)** | **85%** | 3 - 5 | **< 1.5%** |
| **Conviction** | **Tier 2 (RTH 20+)** | **72%** | 5 - 10 | **< 2.5%** |
| **Delayed** | **N/A** | **15%** | 20+ | **Target Hit only** |

> [!IMPORTANT]
> **Exclusive Drawdown Logic**: Recent backtests show that "Target Hits" (within 20 days) carry a significantly lower risk profile (Avg DD 1.3%) than delayed hits. Always favor signals with lower current drawdowns relative to their spot price.
