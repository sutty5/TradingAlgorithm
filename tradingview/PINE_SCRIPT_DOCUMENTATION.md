# 🏆 Golden Protocol V8 Pine Script Documentation

> **Version:** 8.0 LIVE  
> **File:** `golden_protocol_v8_live.pine`  
> **Last Updated:** December 24, 2025  
> **Status:** Production Ready

---

## 📋 Overview

This Pine Script (v6) implements the **Golden Protocol V8 "Honest God Mode"** strategy for TradingView. It provides real-time signal detection, visual trade markers, Fibonacci level drawings, and a comprehensive info panel for live trading.

**Important:** This script is designed for **VISUAL CHARTS AND LIVE ALERTS ONLY**. The Python backtest engine (using Databento tick data) is the source of truth for performance metrics (88% Win Rate).

---

## 🏗️ Architecture

### Indicator Declaration
```pinescript
indicator("Golden Protocol v8 LIVE", overlay=true, max_labels_count=500, max_lines_count=500)
```

### Auto-Detection Logic
The script automatically configures parameters based on the chart symbol:
- **NQ Charts:** Detected via `str.contains(ticker, "NQ")` or `"NAS100"`
- **ES Charts:** Detected via `str.contains(ticker, "ES")` or `"US500"`

---

## ⚙️ Configuration Parameters

### Asset-Specific Settings (Hardcoded)

### Asset-Specific Settings (Hardcoded Defaults)

| Parameter | ES (Short) | NQ (Option A - Default) | NQ (Option B - Aggressive) |
|-----------|------------|-------------------------|----------------------------|
| **Fib Entry** | 0.382 | 0.5 (50%) | **0.382 (38.2%)** |
| **Macro Filter** | ON | ON | **OFF** |
| **Fib Stop** | 1.15 | 1.15 | 1.15 |
| **Fib Target** | 0.0 | 0.0 | 0.0 |
| **Wick Ratio** | 35% | 50% | 50% |
| **Win Rate** | 76% | ~70% | **77.4%** |
| **R:R** | 1:0.77 | 1:0.77 | **1:0.50** |



### User Inputs
- `Fib Stop Level` (default 1.15)
- `Use Macro Filter (1H)` (default true)
- `NQ Strategy Mode` (New):
    - **Standard (V8):** The classic trend-following logic (Entry 0.5, Macro ON).
    - **Einstein (Aggressive):** The optimized scalping logic (Entry 0.382, Macro OFF).
- `Show Fibonacci Levels` (default true)
- `Show All PPI` (default true)
- `Show Strategy Guide` (default true)

> **To Activate Einstein Mode:**
> Simply select **"Einstein (Aggressive)"** from the settings dropdown. This will automatically:
> 1. Set Entry to 0.382
> 2. Disable the Macro Filter (ignoring the checkbox)


---

## 🔄 State Machine

The strategy operates through 5 distinct states:

```
STATE_SCANNING → STATE_PPI → STATE_SWEEP → STATE_PENDING → STATE_FILLED → STATE_SCANNING
```

### State Transitions

1. **SCANNING → PPI:** Divergence detected (ES/NQ opposite directions)
2. **PPI → SWEEP:** Liquidity sweep with adequate wick + filters pass
3. **SWEEP → PENDING:** BOS (Break of Structure) confirmed
4. **PENDING → FILLED:** Price touches entry level
5. **FILLED → SCANNING:** Stop or target hit
6. **PENDING → SCANNING:** Order expired (15-20 bars)

---

## 📊 Phase-by-Phase Logic

### Phase 1: PPI Detection
**Purpose:** Identify ES/NQ divergence (Price Point of Interest)

```pinescript
is_divergence = (my_bull and comp_bear) or (my_bear and comp_bull)
```

- Records PPI high/low for the divergence candle
- Lookback window: 12 bars maximum

### Phase 2: Sweep Detection
**Purpose:** Confirm liquidity grab with rejection wick

**Conditions:**
- Price wicks beyond PPI high/low
- Closes back inside the range
- Wick ratio meets minimum (50% NQ, 35% ES)
- Macro filter passes (1H trend alignment)
- ATR filter passes (ES only: ≤ 4.5)

### Phase 3: BOS Confirmation
**Purpose:** Confirm break of structure for entry

**Logic:**
- **Bearish BOS:** Close < PPI Low
- **Bullish BOS:** Close > PPI High

**Creates:**
- Fib entry/stop/target lines
- BOS label with entry price
- Alert notification

### Phase 4: Pending (Trailing)
**Purpose:** Trail Fibonacci levels until fill or expiry

**Trailing Logic:**
```pinescript
// SHORT: If price makes new low
if ppi_dir == -1 and l < impulse_origin
    impulse_origin := l
    // Recalculate all fib levels

// LONG: If price makes new high  
if ppi_dir == 1 and h > impulse_origin
    impulse_origin := h
    // Recalculate all fib levels
```

**Fill Detection:**
- LONG: `low <= entry_price`
- SHORT: `high >= entry_price`

### Phase 5: Filled (Outcome)
**Purpose:** Track trade to stop or target

**Outcome Logic:**
```pinescript
// Check stop first (conservative)
if hit_stop
    // Log loss, draw lines, reset
else if hit_target
    // Log win, draw lines, reset
```

---

## 📈 Visual Elements

### Labels
| Event | Icon | Color | Size |
|-------|------|-------|------|
| DIV (PPI) | - | Purple | tiny |
| SWEEP | - | Orange | small |
| BOS | - | Green/Red | normal |
| FILLED | 📍 | Blue | small |
| WIN | ✅ | Green | small |
| LOSS | ❌ | Red | small |
| EXPIRED | ⏰ | Gray | small |

### Fibonacci Lines
Drawn from BOS bar to outcome bar:
- **Entry:** Green, width 2
- **Stop:** Red, width 4 (loss) / 2 dotted (win)
- **Target:** Blue, width 4 (win) / 2 dashed (loss)

### Info Panel (Top Right)
Displays:
- Strategy mode (NQ LONG / ES SHORT)
- Historical Win Rate
- Comparison ticker status
- Current state
- Macro direction
- Entry/Stop/Target (when active)
- R:R ratio (when active)
- Net PnL

### Algorithm Guide (Bottom Right)
Toggle-able panel showing:
- Phase-by-phase algorithm explanation
- Index-specific parameters
- Direction rules
- Disable instructions

---

## 🔔 Alert System

| Event | Alert Message Format |
|-------|---------------------|
| SWEEP | "SWEEP Bearish/Bullish @ [price]" |
| BOS | "BOS LONG/SHORT - Limit @ [entry], Stop @ [stop]" |
| FILLED | "FILLED @ [entry]" |
| WIN | "WIN +$[amount]" |
| LOSS | "LOSS -$[amount]" |

All alerts use `alert.freq_once_per_bar`.

---

## 🛡️ Honest Macro Filter

**Critical Implementation:**
```pinescript
htf_close = request.security(syminfo.tickerid, "60", close[1], lookahead=barmerge.lookahead_off)
htf_ema   = request.security(syminfo.tickerid, "60", ta.ema(close, 50)[1], lookahead=barmerge.lookahead_off)
```

- Uses `close[1]` to reference the **previous** completed 1H candle
- `lookahead=barmerge.lookahead_off` prevents future data access
- This matches the Python engine's `shift(1)` implementation

---

## 📐 Fibonacci Calculation

**For SHORT (Bearish) Setups:**
```pinescript
price_range = math.abs(sweep_extreme - impulse_origin)
entry_price := impulse_origin + (price_range * final_fib_entry)  // 38.2% up from origin
stop_price := impulse_origin + (price_range * final_fib_stop)    // 115% up from origin
target_price := impulse_origin                                    // 0% (the origin)
```

**For LONG (Bullish) Setups:**
```pinescript
price_range = math.abs(sweep_extreme - impulse_origin)
entry_price := impulse_origin - (price_range * final_fib_entry)  // 50% down from origin
stop_price := impulse_origin - (price_range * final_fib_stop)    // 115% down from origin
target_price := impulse_origin                                    // 0% (the origin)
```

---

## ⚠️ Known Differences from Python Engine

| Aspect | Pine Script | Python |
|--------|-------------|--------|
| **Data Source** | CME via TradingView | Databento tick data |
| **Wick Filter** | 50%/35% (tighter) | 25% (ground truth) |
| **ATR Filter** | 4.5 (tighter) | 6.0 (ground truth) |
| **Win Rate** | ~70% on TV data | 88% on Databento |

**Reason:** TradingView's data feed is noisier. Tighter filters compensate to reduce false signals.

---

## 📝 Compliance Checklist

| V8 Spec | Pine Script Status |
|---------|-------------------|
| ✅ ES Entry 0.382 | Implemented |
| ✅ NQ Entry 0.5 | Implemented |
| ✅ Stop 1.15 | Implemented |
| ✅ Target 0.0 | Implemented |
| ✅ Honest Macro | `close[1]` + `lookahead_off` |
| ✅ Trailing Fibs | Implemented |
| ✅ No Break Even | Not implemented (by design) |
| ✅ 12 Bar PPI Lookback | Implemented |
| ✅ Expiry 15/20 bars | Implemented |
| ⚠️ Wick Filter | Tightened for TV data |

---

## 🚀 Usage Instructions

1. **Add to TradingView:** Copy/paste the Pine Script code
2. **Select Chart:** NQ or ES futures
3. **Set Timeframe:** 2m for ES, 5m for NQ (recommended)
4. **Configure Alerts:** Create an alert with "Any Alert"
5. **Disable Guide:** Settings → uncheck "Show Strategy Guide" when ready

---

## 📜 Version History

| Version | Date | Changes |
|---------|------|---------|
| 8.0 | Dec 24, 2025 | Full rewrite with enhanced visuals, dynamic algorithm guide |
| 7.1 | Dec 23, 2025 | God Mode with auto-tuning parameters |
| 7.0 | Dec 22, 2025 | Initial God Mode implementation |

---

**Trust the Math. Trust the V8.** 🏆
