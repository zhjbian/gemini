# Fix StudyOrderFlowDataExporter.java Export Logic Issue

This implementation plan details the fix for the real-time tick export logic discrepancies in `StudyOrderFlowDataExporter.java`.

## Summary of Findings

1. **Duplicate Tick Export Bug (Double Listener Registration)**:
   - The study class `StudyOrderFlowDataExporter` implements `TickOperation`. In MotiveWave, any study overriding `onTick(DataContext ctx, Tick tick)` is automatically registered by the platform to receive tick events.
   - However, the code also manually calls `instrument.addListener((TickOperation) this)` in `setupExporters`. This registers the study instance as a tick listener a second time.
   - As a result, the `onTick` callback processes every incoming tick twice, leading to duplicate rows in the exported CSV files.
   - Furthermore, because passive instances do not have a `writeExecutor` but still call `setupExporters` daily/at startup, they continuously add themselves as listeners to the instrument, leading to memory leaks and multiple duplicate listener registrations.

2. **Rollover Week Tick Side Misclassification Bug**:
   - The recently added `isFuturesRolloverWeek` logic attempts to override the tick's buy/sell classification (`side`) by comparing the tick price to the current DOM bid/ask quotes (`currentBid0` and `currentAsk0`).
   - During high-volume periods, DOM updates are throttled and lag behind the real-time trade ticks, causing the tick price to diverge from the stale DOM quotes.
   - This triggers the re-classification logic and incorrectly overrides the correct native side of the trade (obtained from the exchange data feed via `tick.isAskTick()`).
   - This results in a massive bias in the calculated volume delta (e.g., heavily skewed towards `BID` ticks during rapid price movements).
   - In contrast, the Python backfiller directly and successfully trusts the native side byte from the MotiveWave binary files, confirming that the native `tick.isAskTick()` is correct and should not be overridden.

---

## Proposed Changes

### BBT Studies Component

#### [MODIFY] [StudyOrderFlowDataExporter.java](file:///Users/zhijiebian/Intellj-workspace/BBT_Studies/src/bbt/StudyOrderFlowDataExporter.java)

- **Remove redundant tick listener registration**:
  - Remove `instrument.addListener((TickOperation) this)` from `setupExporters`.
  - Remove `instr.removeListener((TickOperation) this)` from `cleanup`.
- **Implement safe DOM listener registration**:
  - Add a private boolean field `isDomRegistered` to prevent duplicate DOM listener additions.
  - Wrap `instrument.addListener((DOMListener) this)` with a check on `isDomRegistered`.
  - Wrap `instr.removeListener((DOMListener) this)` with a check on `isDomRegistered` in `cleanup`.
- **Remove incorrect rollover week side override logic**:
  - Remove the class fields: `lastPrice`, `lastSide`, `currentBid0`, `currentAsk0`.
  - Remove the `isFuturesRolloverWeek` helper method.
  - Simplify `onTick(Tick tick)` to directly use `tick.isAskTick() ? "ASK" : "BID"` and write it to the queue.
  - Remove DOM-scraping bid/ask variables in `update(DOM dom)`.

---

## Verification Plan

### Manual Verification
1. Open MotiveWave.
2. Enable the `BBT Order Flow Data Exporter` study on a chart (e.g. `ESU26`).
3. Allow it to export some real-time ticks.
4. Verify that the generated CSV file does not contain duplicate ticks (adjacent identical timestamps and volumes).
5. Compare the real-time exported delta volume plot using `plot_es_volume_delta.py` with the backfilled plot on the same day/period to ensure they match exactly.
