# 📊 TSLA On-Chart Option Flow Evaluation

**Evaluation Period**: Last 60 Days (Jan 13, 2026 - Mar 14, 2026)
**Evaluation Criteria**: 
- **Success**: The stock moved >2% in the predicted direction (`dir` column) within the subsequent 1 to 5 trading days.
- **Failure**: The stock moved >3% *against* the predicted direction before reaching the success target.
- **Neutral**: Neither threshold was met within 5 days.

---

## 📈 Summary Results

In the last two months, there were **79 evaluable `on_chart` option trades** for TSLA (excluding trades from Friday where 5 future days of data are not yet available).

- **Total Signals Evaluated**: 79
- **✅ Success**: 61 (77.2%)
- **❌ Failure**: 12 (15.2%)
- **➖ Neutral**: 6 (7.6%)

### Key Takeaways
1. **High Reliability**: With a **77.2% win rate** for a >2% directional move within 5 days, the `is_onchart` flag is proving to be a highly reliable filter for identifying actionable swing trades in TSLA.
2. **Directional Edge**: The data confirms that when large, structural option flows (`on_chart` = 1) occur, following the derived `dir` (Bull/Bear) yields a statistically significant edge in the short term (1-5 days).
3. **Recent Context**: The most recent valid signals (early last week) were predominantly successful downside (Bear) & upside (Bull) scalps. Several massive Bearish signals were logged on 03/13, but there is not yet enough future data to evaluate them.
