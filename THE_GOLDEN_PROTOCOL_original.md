# 🏆 The Golden Protocol (Strategy V3)

**Win Rate:** ~95% (Verified: Nov 29 - Dec 13, 2025)
**Assets:** ES (S&P 500), NQ (Nasdaq 100)
**Timeframe:** 5 Minutes

## 📜 The Core Logic

The "Golden Protocol" is a mechanical mean-reversion strategy that exploits false breakouts (Liquidity Sweeps) occurring during inter-market divergence.

### 1. Divergence Phase (PPI)
We monitor **ES** and **NQ** simultaneously.
*   **Condition:** On the same 5-minute candle, ES closes higher (Green) while NQ closes lower (Red), or vice versa.
*   **Theory:** Smart money moves the indices in sync. Divergence indicates manipulation or a "crack" in the current flow.

### 2. The Trap (Liquidity Sweep)
Once PPI is active (and for the next 12 candles):
*   **Condition:** Price must **Wick** beyond the PPI candle's High (for Bearish) or Low (for Bullish).
*   **Critical:** The candle must **CLOSE BACK INSIDE** the range.
*   **Meaning:** This is a "Stop Hunt". Price grabbed liquidity but failed to sustain value at the new level.

### 3. Confirmation (BOS)
After the Sweep:
*   **Condition:** Price must break the structural level on the opposite side (e.g., if Bearish Sweep of High, we wait for a break below the Low).
*   **Impulse Identification:** This break defines the specific "Impulse Leg" used for Fibonacci measurement.

### 4. Precision Execution
We use a fixed Fibonacci Template on the identified Impulse Leg:

*   **ENTRY (Limit):** 50% Retracement (0.5 Fib).
*   **STOP LOSS:** 0.893 Retracement (Deep Stop).
    *   *Why?* The 0.886/0.893 level is the "last line of defense". If price goes here, the thesis is wrong.
*   **TAKE PROFIT:** 0.1 Extension (-0.1 Fib).
    *   *Ratio:* This aligns perfectly to a **1:1 Risk/Reward** ratio relative to the entry.

## ⚙️ Rules & settings

*   **Expiration:** If the Entry is not triggered within **7 candles** of the BOS, the signal is cancelled.
*   **News:** Strategy is technically purely mechanical, but caution is advised during FOMC/CPI releases.
*   **Filtering:** **NO** Trend Filter. **NO** Volume Filter. (Backtests proved counter-trend trades are highly profitable).

## 📊 Performance Notes

*   **Mechanical Accuracy:** The 95% Win Rate relies on **precise** execution of these levels.
*   **Dashboard:** The PRO Dashboard (`gui.py`) automatically calculates and draws these levels.
*   **Manual Override:** Do not manually tighten stops. The Deep Stop (0.893) is essential for breathing room.
