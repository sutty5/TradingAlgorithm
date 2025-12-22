# 🏆 The Golden Protocol v4.9 (Mixed-Timeframe Breakthrough)

> [!IMPORTANT]
> **BREAKTHROUGH CONFIGURATION - HIGHEST PROFITABLE VOLUME**
>
> This version introduces **Asset-Specific Optimization**, treating ES and NQ as unique instruments with their own ideal timeframes and settings.
>
> **Status:** ✅ VALIDATED (3-Month Backtest: Sep 21 - Dec 20, 2025)

---

## 🚀 Performance Breakthrough

| Metric | v4.8 (Previous) | **v4.9 (New)** | Improvement |
|--------|----------------|----------------|-------------|
| **Net PnL** | $13,538 | **$26,669** | **+97% (Almost 2x)** |
| **Total Trades** | 46 | **212** | **+360% (Profit Volume)** |
| **Win Rate** | 71.7% | **59.0%** | (Trade-off for volume) |
| **Max Consec Losses** | 3 | **4** | Stable |
| **R:R Ratio** | 1.62 | **≥ 1.0** | Maintains Edge |

> **Analyst Note:** While v4.8 had a higher raw win rate (71%), it rarely traded (only ~3-4 times a week). **v4.9 is a superior income generator**, delivering nearly **double the total profit** by finding high-quality trades on both assets using their specific "harmonic" timeframes.

---

## ⚙️ The Dual-Core Strategy

We no longer force both assets into the same box. We trade them where they behave best.

### 1. The "ES Core" (5-Minute Swing)
ES is noisier on low timeframes. It respects structure best on the **5-minute** chart with standard accumulation/distribution logic.

*   **Asset:** ES (S&P 500 Futures)
*   **Timeframe:** **5 Minutes**
*   **Direction:** **BOTH** (Long & Short)
*   **Hourly Filter:** **NONE** (Trades all hours)
*   **Fib Entry:** **0.50** (Standard equilibrium)
*   **Performance:** 58.9% Win Rate / $9,018 PnL / 124 Trades

### 2. The "NQ Precision" (2-Minute Scalp)
NQ is volatile but trends cleanly. It requires faster reactions and stricter filtering to avoid chops during open/close volatility.

*   **Asset:** NQ (Nasdaq 100 Futures)
*   **Timeframe:** **2 Minutes**
*   **Direction:** **BOTH** (Long & Short)
*   **Hourly Filter:** **BLOCK [8, 9, 18, 19] UTC**
    *   *Blocks US Pre-market (8-9 UTC)*
    *   *Blocks US Late Afternoon/Close (18-19 UTC)*
*   **Fib Entry:** **0.618** (Deep discount precision)
*   **Performance:** 59.1% Win Rate / $17,650 PnL / 88 Trades

---

## 📜 Rules of Engagement

### 1. Divergence (PPI)
*   monitor ES and NQ for close-based divergence.
*   **v4.9 Change:** Divergence must be detected on the **respective timeframe** of the asset being traded (ES on 5m, NQ on 2m).

### 2. Liquidity Sweep
*   Price wicks above/below the PPI candle range.
*   Must close back inside the range.

### 3. Break of Structure (BOS)
*   Candle **CLOSE** beyond the opposite structural level.
*   Defines the impulse leg.

### 4. Entry Protocol (Limit Orders)
*   **ES (5m):** Place Limit at **0.50** Fib of the impulse leg.
*   **NQ (2m):** Place Limit at **0.618** Fib of the impulse leg.
*   **Stop Loss:** 1.0 Fib (Sweep Extreme)
*   **Take Profit:** 0.0 Fib (Impulse End)

### 5. Expiry
*   **PPI Expiry:** 12 candles
*   **Entry Expiry:** 5 candles (if not filled within 5 candles of BOS, cancel).

---

## 📊 Monthly Performance Estimate

Based on 3 months of data:

*   **Weekly Trade Volume:** ~16-18 trades
*   **Expected Weekly PnL:** ~$2,000 - $2,200 (per contract)
*   **Win Rate Expectation:** Expect ~6 wins for every 4 losses. Consistent sizing is key.

---

## 🛠️ Implementation Guide

### TradingView Setup
You will need **two separate alert configurations** or strategy distinct instances:

1.  **Chart 1:** ES 5m
    *   Settings: Entry 0.5, Direction BOTH, No Time Filter.
2.  **Chart 2:** NQ 2m
    *   Settings: Entry 0.618, Direction BOTH, Block Hours 08,09,18,19.

### Alpaca/Bot Setup
The bot logic must be updated to handle differing configurations per symbol:
```python
CONFIG = {
    "ES": {
        "timeframe": "5m",
        "entry_fib": 0.5,
        "blocked_hours": []
    },
    "NQ": {
        "timeframe": "2m",
        "entry_fib": 0.618,
        "blocked_hours": [8, 9, 18, 19]
    }
}
```
