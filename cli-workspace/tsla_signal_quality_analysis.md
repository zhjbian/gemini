# 🎯 TSLA Options Signal Quality Deep Dive
**Evaluation Period**: Last 60 Days (Jan 13, 2026 - Mar 14, 2026)
**Target Threshold**: 3% directional move within 1-5 days (Failure = -3% move against).

## 1. Impact of Execution Type (Code Trustability)
We grouped trades by the `code` prefix (`D.` = Trustable directional execution, `N.` or other = Untrustable).

| Category | Total Trades | ✅ Success | ❌ Fail | ➖ Neutral | Success % | Fail % | Neutral % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Trustable Codes (D. Prefix) | 35 | 25 | 6 | 4 | 71.4% | 17.1% | 11.4% |
| Untrustable Codes (N. / Other) | 44 | 30 | 12 | 2 | 68.2% | 27.3% | 4.5% |

## 2. Impact of Absolute Net Premium Size

| Category | Total Trades | ✅ Success | ❌ Fail | ➖ Neutral | Success % | Fail % | Neutral % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| < $10M | 11 | 7 | 4 | 0 | 63.6% | 36.4% | 0.0% |
| $10M - $50M | 22 | 16 | 5 | 1 | 72.7% | 22.7% | 4.5% |
| $50M - $100M | 22 | 20 | 0 | 2 | 90.9% | 0.0% | 9.1% |
| > $100M | 24 | 12 | 9 | 3 | 50.0% | 37.5% | 12.5% |

## 3. Combined 'Golden' Signals (Trustable Code + High Premium >$50M)

| Category | Total Trades | ✅ Success | ❌ Fail | ➖ Neutral | Success % | Fail % | Neutral % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Golden Signals | 11 | 7 | 1 | 3 | 63.6% | 9.1% | 27.3% |