# QuantData Options Execution Types: Expert Mechanical Analysis

This document provides an expert-level breakdown of options execution types based on market microstructure and order routing mechanics. It evaluates the reliability of using **"Price vs. Bid-Ask Spread"** as a proxy for institutional directional intent.

---

## 🟢 Tier 1: High Conviction (Aggressive)
These orders originate from a desire for **Immediacy** over **Price Improvement**. They take liquidity from the market, making them the most reliable indicators of sentiment.

### 1. ISO (Intermarket Sweep Order) — ⭐⭐⭐⭐⭐
- **Mechanics**: The most aggressive order type. The sender assumes responsibility for price protection and "sweeps" all available liquidity across multiple exchanges simultaneously up to a limit price.
- **Expert Reliability**: **Extreme**. An ISO print at the Ask signifies an institution "pounding the table" to get filled regardless of the NBBO. 
- **Sentiment**: Near/Above Ask = High Conviction Buy; Near/Below Bid = High Conviction Sell.

### 2. AUTO (Electronic Matching) — ⭐⭐⭐⭐
- **Mechanics**: Standard automated execution where an order is matched against the public limit order book on a single exchange. 
- **Expert Reliability**: **High**. Represents standard directional participation. Since it hits the prevailing spread, the "Price vs. Bid-Ask" logic is structurally sound.
- **Sentiment**: Follows standard proximity rules.

---

## 🟡 Tier 2: Price Discovery (Auction)
These orders prioritize **Price Improvement** over **Immediacy**. They involve a brief "pause" for others to provide a better price than the prevailing spread.

### 3. AUCT / AUCT_ISO (Auction) — ⭐⭐⭐
- **Mechanics**: Electronic auctions (e.g., CBOE AIM, ISE PIM). The order is "stopped" with a guaranteed fill price, then exposed for 100ms-1s to see if any participant offers a better price.
- **Expert Reliability**: **Moderate**. Because these auctions actively seek the **Midpoint**, the final print frequently lands inside the spread. While the "initiating side" is known, the price interaction is less aggressive than an ISO.
- **Sentiment**: Bias towards the initiating side, but often "Neutral" due to midpoint fills.

---

## 🔴 Tier 3: Negotiated / Complex (Low Confidence)
These trades are either pre-matched off-market or involve multi-leg structures where individual leg prices are secondary to the overall strategy cost.

### 4. CROSS (Crossing Mechanism) — ⭐⭐
- **Mechanics**: A broker pairs two clients (or a client and the firm) and prints the trade to an exchange. 
- **Expert Reliability**: **Low**. The price is pre-negotiated to be "fair" to both parties, often landing exactly at the midpoint or an arbitrary benchmark. It does not represent directional "pressure" on the open market.
- **Sentiment**: Unreliable. Treat as institutional risk transfer rather than a "bet."

---

## ❌ Tier 4: Hedged / Neutral (Misleading)
These trades are part of a multi-asset strategy where the directional intent of the option is neutralized by another asset.

### 5. TIED (Tied to Stock) — ❌
- **Mechanics**: The option trade is contingent on a corresponding stock trade (e.g., Stock-Tied Cross).
- **Expert Reliability**: **None**. These are effectively delta-neutral hedges.
- **Sentiment**: **Dangerous**. Without seeing the stock delta, the option sentiment is meaningless.

---

## 📊 Detailed Reliability Index: Obsereved Full Strings

The following unique strings were identified in the internal database from the last year of live trading. They are sorted by **Expert Reliability Rating**.

### ⭐⭐⭐⭐⭐ TIER 1: EXTREME CONVICTION
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **ISO** | Intermarket Sweep. Institutional urgency. | 95% |
| **AUCT_ISO** | Urgent sweep triggering an immediate auction. | 90% |

### ⭐⭐⭐⭐ TIER 2: STRONG PARTICIPATION
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **AUTO** | Standard electronic market matching. | 85% |
| **M2S_AUTO** | Electronic match against internal liquidity. | 80% |

### ⭐⭐⭐ TIER 3: PRICE DISCOVERY
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **AUCT** | Standard electronic auction. Often lands at midpoint. | 60% |

### ⭐⭐ TIER 4: NEGOTIATED BLOCK
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **CROSS** | Single institutional cross. Agreed-upon price. | 30% |

### ⭐ TIER 5: COMPLEX / FLOOR (NOISE)
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **MULTI_AUCT_COB** | Multi-leg auction. Leg prices are derived artifacts. | <20% |
| **MULTI_AUTO_COB** | Multi-leg electronic book matching. Package-priced. | <20% |
| **MULTI_CROSS** | Multi-leg institutional crossing. | <10% |
| **FLR / M2M_FLR** | Manual floor negotiation. Stale screen Bid/Ask. | <10% |
| **M2S_FLR** | Manual floor matching against internal firm liquidity. | <10% |
| **MULTI_FLR_PP** | Floor Proprietary Product. Complex/opaque strategy. | <5% |

### ❌ TIER 6: DELTA-HEDGED (DANGEROUS)
| Type | Mechanics | Sentiment Trust |
| :--- | :--- | :--- |
| **TIED_MULTI_AUCT_COB** | Stock-tied multi-leg auction. Direction is hedged. | 0% |
| **TIED_MULTI_AUTO_COB** | Stock-tied multi-leg electronic matching. | 0% |
| **TIED_MULTI_CROSS** | Stock-tied institutional crossing. | 0% |
| **TIED_MULTI_FLR_COB** | Stock-tied manual floor complex trade. | 0% |

### 🔘 SYSTEM / STATUS (IGNORE)
| Type | Description |
| :--- | :--- |
| **EXT_HOURS** | Low-liquidity trades printed outside regular session. |
| **CANCEL / CANCEL_LAST** | Corrective records for trade removal. |
| **SOLD_LAST** | Late-reported trade from an earlier time. |

---

## Practical Examples & Case Studies

Detailed audits of real-world institutional prints to illustrate the conviction model in action:

*   **[TSLA Feb 2026: The $1.2B Tied-Block Liquidation](case_study_TSLA_Feb2026_Tied_Block.md)**: A masterclass in identifying institutional capitulation mid-downtrend via sub-bid stock executions.
