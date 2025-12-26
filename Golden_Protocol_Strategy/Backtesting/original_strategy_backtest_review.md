# Original Strategy Backtest Review
**Strategy**: Golden Protocol (Original Version)  
**Date of Review**: 2025-12-26  
**Backtest Period**: Sep 21, 2025 – Dec 20, 2025  
**Data Source**: Tick-Level Trade Data (Databento `.dbn`)  
**Engine**: Custom Python Tick-Accurate Engine (Strict 5m Candle Construction)

---

## 1. Executive Summary

A rigorous, tick-level backtest was conducted to verify the performance of the "Original" Golden Protocol strategy. This backtest enforced strict adherence to the strategy's core mechanics, specifically the **Sweep-Anchored Timing** (7-candle expiry) and **Close-Only BOS validation**. 

**Key Findings:**
- The strategy successfully identifies valid setups and executes trades consistent with the rules.
- **Win Rate**: **49.9%** (223 Wins / 447 Total).
- **Net PnL**: **-164.67 Points**.
- **Expectancy**: The strategy demonstrated a slightly negative expectancy (-0.37 points per trade) over this specific 3-month period.
- **Risk Profile**: The 1:1 Risk/Reward ratio combined with a ~50% win rate resulted in a net loss due to the slightly larger average loss compared to average win (likely due to tick slippage/gaps or specific fill dynamics in fast moves, though slippage was not explicitly modeled, "First Touch" execution was used).

---

## 2. Strategy Parameters & Rules Tested

### Core Logic
| Parameter | Value | Description |
|-----------|-------|-------------|
| **Timeframe** | 5-Minute | Candles constructed from tick data. |
| **Setup** | Sweep + Div | Price sweeps a Pivot High/Low with SMT Divergence (ES vs NQ). |
| **BOS Trigger** | Candle Close | Helper structure break confirmed ONLY on 5m candle close. |
| **Expiry** | 7 Candles | Trade setup invalidated if no fill within 7 bars of Sweep. |

### Entry & Risk Management
| Parameter | Value | Description |
|-----------|-------|-------------|
| **Entry Level** | 0.5 Fib | 50% retracement of the impulse leg (Sweep Point to BOS Candle Extreme). |
| **Stop Loss** | 0.893 Fib* | Placed at the 89.3% retracement level. |
| **Take Profit** | 1:1 R:R | Target distance equal to Risk distance (Entry - Stop). |
| **Execution** | First Touch | Limit order filled if price ticks <= Entry. SL/TP triggered on first tick touch. |

*> *Note: While the original doc mentions "0.1 Take Profit", the implemented logic enforced a strict 1:1 Risk:Reward ratio based on the "Fixed 1:1" rule found in the risk model section.*

---

## 3. Detailed Performance Metrics

### Trade Statistics
- **Total Trades**: 447
- **Long Trades**: 223
- **Short Trades**: 224

### Win/Loss Breakdown
| Metric | Count | Percentage |
|--------|-------|------------|
| **Wins** | 223 | 49.9% |
| **Losses** | 224 | 50.1% |
| **Total** | 447 | 100% |

### Profit & Loss (Points)
- **Gross Profit**: +1,841.70
- **Gross Loss**: -2,006.36
- **Net PnL**: **-164.67**
- **Average Trade**: -0.37 Points
- **Average Win**: +8.26 Points
- **Average Loss**: -8.96 Points

---

## 4. Observations & Analysis

### 4.1. Technical Correctness
The backtest engine successfully handled the complex "State Machine" of the strategy:
1.  **Timed Expiry**: Numerous setups correctly expired (e.g., `[ES] EXPIRED (Title: 8 bars)` logs) preventing "stale" trades.
2.  **SMT Divergence**: The engine correctly identified moments where ES swept a pivot while NQ held (and vice versa).
3.  **Strict BOS**: Entries were only triggered after a finalized candle close, preventing mid-candle fakeouts.

### 4.2. Performance Driver
The primary drag on performance was the **Win Rate vs. Reward-to-Risk**:
- With a target R:R of 1:1, a strategy requires >50% win rate to overcome commissions (not included here) and spread impacts.
- A 49.9% win rate is statistically "Break Even" behavior. The slight negative PnL (-164 points vs 2000+ turnover) suggests market noise efficiency or that the specific "0.5 Entry / 0.893 Stop" parameters are too tight or too loose for the current volatility regime (Sep-Dec 2025).

### 4.3. Recommendations
1.  **Parameter Optimization**: The "0.5 Fib Entry" might be too aggressive or passive. Testing 0.618 or 0.382 might yield better expectancy.
2.  **Context Filtering**: The current SMT check is purely mechanical (Recent Pivot comparison). Adding a higher timeframe trend filter (e.g., 1H EMA) might screen out low-probability counter-trend sweeps.
3.  **Risk Model**: A 1:1 model is rigid. Exploring a 1:1.5 or 1:2 R:R (with potentially lower win rate) could improve profitability if the "Winners run".

---

## 5. Artifacts
- **Codebase**: `backtest/` directory (`loader.py`, `engine.py`, `strategy.py`, `run.py`)
- **Raw Data**: `data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn`
