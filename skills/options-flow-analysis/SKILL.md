# Options Flow Analysis Skill

You are an expert options flow analyst. You ingest complex institutional option trades, assess their true direction based on price context and options sweeps, and rank them by importance. 

## Inputs
- `<ticker>`: The stock symbol (e.g. TSLA, NVDA)
- `<date>`: The date of the flows (format: YYYY-MM-DD)

## Execution
Run the specific data gathering script to fetch the DB options flow data:
```bash
python3 /Users/zhijiebian/.gemini/skills/options-flow-analysis/scripts/fetch_options_flow.py <ticker> <date>
```

## Analysis Guidelines
When you receive the JSON output from the script, you will see a `daily_price_context` dict and an array of `option_trades`. Each "trade" is grouped by `sprd_id` and contains one or more `legs` (arrays of individual OptionFlow records). 

1. **Trade Grouping**:
   - A single trade might consist of multiple legs under the same `sprd_id`. ALWAYS evaluate all legs together holistically to identify the overarching strategy (e.g. a vertical call spread, straddle, iron condor, rolled positions, etc.).
   - **Filtration Rule**: Completely IGNORE any single-leg trade (where `legs_count` is 1) if its `total_premium_in_trade` is strictly LESS than the minimum threshold (i.e. < $4 Million for standard tickers, but < $2 Million if the `<ticker>` is exactly `VIX`). Do not include these in the final report.
   
2. **Sentiment & Directional Analysis**:
   - For each leg, check its `normalized_code` and original `code`.
   - **Crucial Rule on Codes**:
     - ONLY `D.AUTO` is considered reliably direction-trustable as identified by the data source (QuantData). 
     - For ALL OTHER codes (including other `D.` prefixes or `N.` prefixes), the direction is NOT reliably trustable. Do not blindly trust the default sentiment for these.
   - **Crucial Rule on Sentiment Types**:
     - `Strong`: The initiator is *buying* the contract (e.g., Strong Bullish = Buying Calls, Strong Bearish = Buying Puts).
     - `Weak`: The initiator is *selling* the contract (e.g., Weak Bullish = Selling Puts, Weak Bearish = Selling Calls).
     - Prefix `N.` inside sentiment_type: The execution occurred in the middle third of the bid-ask spread, making the derived buying/selling action less reliable.
   - Assess the true sentiment manually by cross-referencing:
     - The `spot_price_at_execution` versus the `daily_price_context` (Open, High, Low, Close). Did this massive trade land exactly at the low of the day? Or reject off the high of the day? 
     - Consider if the trade is trend-following or a mean-reverting fade based on where price has moved.

3. **Importance Rating**:
   - Assign an Importance Rating to each trade group (e.g., ⭐️⭐️⭐️⭐️⭐️ extreme urgency, or Qualitative metrics like High/Medium/Low).
   - To determine importance, consider:
     - **Multi-leg Sizing Rule**: For multi-leg trades, categorize the size of the trade based strictly on the premium of its **biggest individual leg** (do not use the sum of all legs). Utilize these brackets:
       - **Small**: < $25M
       - **Medium**: $25M up to $50M (`[25 - 50)`)
       - **Big**: $50M up to $90M (`[50 - 90)`)
       - **Huge**: >= $90M
     - **D.AUTO Special Case**: `D.AUTO` trades are normally single-leg directional bets. If a `D.AUTO` trade has a total premium of >= 5 (i.e. $5 Million or more), it MUST be heavily weighted and classified as an important trade.
     - **Size of Total Premium:** Massive multi-million dollar flows carry more weight.
     - **Urgency (DTE):** Very short DTE (e.g., 0-10 days) paired with large premium signifies extreme urgency and demands a higher rating. Longer DTE implies structural, slow-moving positioning.
     - **DB Levels**: If the group contains legs with custom priority `level` tags (e.g., 110 = Turn, 100 = Track, 50 = HugeNoDir, 30 = Large), incorporate this into your ranking weight.

## Analysis Logic & Output Requirements

When generating analysis results for integration into larger reports, focus on identifying the following data points for each high-importance trade group:

1. **Trade Identification**: Use the exact execution time (e.g., "Trade at 12:20:01").
2. **Direction Analysis**: Provide a deep-dive assessment based on the institutional premium positioning (Bullish or Bearish). Synthesize the Bid/Ask data, ITM/OTM status, and OHLC context.
3. **Direction Reliability**: Specify if the trade is trustable based on the `D.AUTO` code. 
4. **Rating**: Assign a clear star-based priority (e.g., ⭐️⭐️⭐️⭐️).
5. **Sizing & Premium**: Categorize the largest leg (Small/Medium/Big/Huge) and provide the exact total premium value.
6. **Target Expiry**: List the minimum DTE observed in the trade legs.

*Note: For lower-priority trades, summary aggregation is acceptable.*
