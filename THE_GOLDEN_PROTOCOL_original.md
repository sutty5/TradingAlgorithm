# 🏆 The Golden Protocol v4.7 (Optimized 2m Strategy)

> [!CAUTION]
> **LOCKED PARAMETERS - DO NOT MODIFY WITHOUT EXPLICIT APPROVAL**
>
> This strategy is proven and profitable. See `docs/Strategy Testing/README.md` for the change approval process.

**Optimized Timeframe:** 2 Minutes  
**Win Rate:** 72.0% (55-day backtest)  
**Net PnL:** $143,339 (1 contract, 55 days)  
**Assets:** ES (S&P 500 Futures), NQ (Nasdaq 100 Futures)  

> **v4.7 Updates (Dec 16, 2025):**
> - Optimized for 2-minute timeframe (best performer)
> - Entry: 0.5, Stop: 1.0, Target: 0.0 (R:R 1:1)
> - Win rate increased from 65% to 72%
> - Trailing Fib Range + Same-bar sequence fix

---

## 📜 The Core Logic

The "Golden Protocol" is a mechanical mean-reversion strategy that exploits false breakouts (Liquidity Sweeps) occurring during inter-market divergence.

---

## Strategy Phases

### 1. Divergence Phase (PPI)
We monitor **ES** and **NQ** simultaneously.

*   **Condition:** On the same 2-minute candle, ES closes higher (Green) while NQ closes lower (Red), or vice versa.
*   **Dashboard Visual:** Marked by a **Purple Diamond (💜)** on the chart ("The Origin").
*   **Phase Indicator:** Shows `PPI` stage

### 2. The Trap (Liquidity Sweep)
Once PPI is active (and for the next 12 candles):

*   **Condition:** Price must **Wick** beyond the PPI candle's High (for Bearish) or Low (for Bullish).
*   **Critical:** The candle must **CLOSE BACK INSIDE** the range (confirmed at candle close).
*   **Dashboard Visual:** Marked by a **Yellow Warning Triangle (⚠️)**.
*   **Phase Indicator:** Shows `SWEEP` stage
*   **Trade Setup Guide:** Shows projected break level

### 3. Confirmation (BOS - Break of Structure)
After the Sweep:

*   **Condition:** Price must **CLOSE** beyond the structural level on the opposite side (e.g., if Bearish Sweep of High, we wait for a **close** below the Low).
*   **Critical:** BOS is only confirmed when the candle **closes** beyond the level, not on intra-bar breaks.
*   **Impulse Identification:** This break defines the specific "Impulse Leg" used for Fibonacci measurement.
*   **Phase Indicator:** Shows `BOS ↓ SELL` or `BOS ↑ BUY`

### 4. Trailing Fib Range (NEW in v4.6)
After BOS, the Fib range dynamically updates:

*   **Trailing fib_0:** Tracks lowest low (bearish) or highest high (bullish)
*   **Fixed fib_1:** Sweep extreme stays locked
*   **Dynamic Updates:** Entry/Stop/Target levels recalculate as fib_0 changes
*   **Locking:** Range locks when entry is filled or signal expires

### 5. Entry Fill (PENDING → FILLED)
After BOS confirmation:

*   **Trade Status:** `PENDING` - waiting for price to retrace to entry level
*   **Entry Condition:** Price must touch the 0.5 Fib level (limit order fill)
*   **Visual Marker:** Blue `FILL` label appears when entry is touched
*   **Trade Status:** `FILLED` - now tracking outcome
*   **Alert:** Entry fill alert sent with final locked levels

### 6. Precision Execution
We use a fixed Fibonacci Template on the identified Impulse Leg.

#### Fib Level Settings (OPTIMIZED 1:1 R:R)

| Level | Fib Value | Description | Chart Color |
|-------|-----------|-------------|-------------|
| **TARGET** | 0.0 | Impulse End (BOS candle extreme) | Green |
| **ENTRY** | 0.5 | 50% Retracement (Limit Order) | Orange |
| Reference | 0.786 | Reference level | White |
| **STOP LOSS** | 1.0 | Sweep Extreme (invalidation) | Red |

*   **Risk:Reward Ratio:** 1:1.00
*   **Phase Indicator:** Shows `PENDING` → `FILLED` → `WIN/LOSS`

---

## ⚙️ Rules & Settings

*   **Entry Expiration:** If the Entry is not filled within **7 candles** of the BOS, the signal is cancelled (EXPIRED).
*   **News:** Strategy is purely mechanical, but caution is advised during FOMC/CPI releases.
*   **Filtering:** **NO** Trend Filter. **NO** Volume Filter. (Backtests proved counter-trend trades are profitable).

---

## 📊 Backtest Performance (55 Days: Oct 21 - Dec 16, 2025)

### Multi-Timeframe Comparison

| Timeframe | Signals | Wins | Losses | Win Rate | Net PnL |
|-----------|---------|------|--------|----------|--------|
| **2m** 🔥 | 386 | 192 | 101 | **65.5%** | **$89,903** |
| 1m | 840 | 381 | 330 | 53.6% | $57,423 |
| 5m | 840 | 346 | 312 | 52.6% | $39,718 |
| 15m | 292 | 130 | 105 | 55.3% | $42,264 |

> **Recommendation:** The 2-minute timeframe shows the best performance with a 65.5% win rate.

### 15-Minute Timeframe (55 Days)

| Metric | Value |
|--------|-------|
| Total Signals | 285 |
| Entry Fills | 229 |
| **Win Rate** | **60.3%** |
| Max Consecutive Losses | 7 |
| **Net PnL (1 contract)** | **$40,246** |

---

## 📊 Dashboard Features

### Phase Indicator Bar
Visual progress showing current protocol stage:
```
SCANNING → PPI → SWEEP → BOS → PENDING → FILLED → WIN/LOSS
```
- Completed phases show ✓
- Current phase is highlighted
- Asset and direction (🐂 LONG / 🐻 SHORT) displayed

### Trade Setup Guide Panel
Step-by-step guidance panel showing:
- Current phase with context
- Checklist of completed/pending steps
- **DYNAMIC PARAM PANEL**: Shows Entry, Stop, Target prices when a signal triggers
- "What to do NOW" actionable guidance

### Chart Markers
| Marker | Color | When It Appears |
|--------|-------|-----------------|
| 💜 PPI Diamond | Purple | At divergence candle |
| ⚠️ SWEEP Triangle | Yellow | At liquidity sweep |
| BOS ↓ SELL / BOS ↑ BUY | Red/Green | At BOS confirmation |
| 🔵 FILL | Blue | When entry is touched |
| ✅ WIN | Green | At target hit |
| ❌ LOSS | Red | At stop hit |

### Fibonacci Lines
Lines span from trade start to trade end:
- **Orange** - Entry (0.5)
- **Red** - Stop Loss (1.0) - Sweep Extreme
- **Green** - Take Profit (0.0) - Impulse End
- **Gray** - Reference levels (0.786)

---

## 📈 Why It Works

### 1. The Liquidity Sweep (The Trap)
Most strategies fail because they chase breakouts. This strategy profits from failed breakouts.

- **What happens:** We wait for price to "wick" above a recent High (or below a Low).
- **Why it works:** Breakout traders enter Buy orders here, and existing shorters hit their Stop Losses. This creates a flood of liquidity.
- **The Trap:** If price immediately reverses and closes back inside the range, all those traders are trapped. We take their money.

### 2. Divergence (The Crack)
We don't just take every sweep. We only take sweeps when ES and NQ disagree.

- **The Logic:** Smart Money moves markets in sync. When ES makes a Higher High but NQ makes a Lower High, it reveals a "crack" in the correlation. It proves the move is weak and likely manipulation.

### 3. Entry Fill Confirmation
We don't assume instant fills - we wait for confirmation:

- **Realistic Execution:** Trade only counts after price actually touches our entry level
- **No Phantom Wins:** Trades where target was hit without entry fill are correctly filtered out
- **Accurate Metrics:** Win rate reflects actual executable trades

### 4. Strict Fibonacci (No Guessing)
Human emotion destroys win rates. We removed it entirely by using rigid math:

- **Entry (0.5 Fib):** Wait for price to pull back exactly 50% from the trap.
- **Stop (0.893 Fib):** Invalidation point with breathing room.
- **Target (0.1 Fib):** Fixed 1:1 payout. Don't get greedy.

---

## ⚙️ Technical Implementation Note

> **Updated Dec 16, 2025**

### Entry Fill Tracking

All components now properly track **entry fill** before calculating outcomes:
- **Pine Script (v4.7)** - TradingView indicator
- **Live Trading Backend** - `core/utils.py` → `calculate_single_outcome()`
- **Backtesting** - `routers/backtest.py` → uses same outcome calculation

**Flow:**
1. **BOS Confirmation:** Only triggers when candle **closes** beyond level (`barstate.isconfirmed`)
2. **Pending Phase:** Trade is `PENDING` until price touches the 0.5 entry level
3. **Filled Phase:** Once entry is touched, outcome tracking begins
4. **Outcome:** WIN if target hit, LOSS if stop hit, EXPIRED if entry never filled (7 candles)

### Previous vs Current Logic

| Aspect | Previous (Pre-Dec 15) | Current (v4.7) |
|--------|----------------------|----------------|
| BOS Trigger | Intra-bar break | Candle close confirmation |
| Entry Fill | Assumed instant | Wait for 0.5 touch |
| Timeframe | 5-minute | 2-minute (optimized) |
| Stop Level | 0.893 Fib | 1.0 Fib (sweep extreme) |
| Target Level | 0.1 Fib | 0.0 Fib (impulse end) |
| Win Rate | ~59% | ~72% (optimized) |
| Execution | Too fast to react | Time to place orders |

### TradingView Alerts

The script includes built-in alert conditions:
- `Bullish Entry Signal` - BUY opportunity
- `Bearish Entry Signal` - SELL opportunity
- `Trade WIN` - Target hit
- `Trade LOSS` - Stop hit

---

*Document last updated: Dec 16, 2025*

