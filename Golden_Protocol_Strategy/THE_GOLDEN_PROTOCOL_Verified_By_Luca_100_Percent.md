# THE GOLDEN PROTOCOL – Official Strategy Rulebook  
## Sweep-Anchored Timing Version  
### With Verified Tick-Accurate Backtesting Specification (Python + Backtrader)

---

## Market & Framework

**Markets watched**
- ES (S&P 500 futures)
- NQ (Nasdaq-100 futures)

**Execution instrument**
- Either ES or NQ (commonly NQ)

**Timeframe Logic**
- Structure & signals → **5-minute candles**  
- Entry & fills → **tick-level data**

**Data Quality Requirement**
- Historical testing MUST use **full tick-level trade data**
- Candle-only backtests are **not permitted**

---

## Core Idea — In Plain English

We trade a **liquidity-driven reversal pattern**, where:

1. Both ES and NQ have **structural PPIs (Pivot Points of Interest)**  
2. Price **attacks those PPI levels to run liquidity**
3. The breakout attempt **fails to convert into a true structural break**
4. **BOS confirms reversal intent**
5. We enter on a **0.5 retrace of the BOS impulse**
6. Entry MUST occur **within 7 candles after the sweep**

If the market doesn’t retrace to entry in time  
➡ **No trade**

---

# PPI & Reversal Context — Formal Specification

This section removes ambiguity so backtesting = live behaviour.

---

## 1. PPI (Pivot Point of Interest)

A **PPI** is a **5-minute swing high or swing low**.

We define swings using:

SWING_WIDTH = 2


### 1.1 PPI-High
Candle `i` is a PPI-High if:

high[i] > high[i - k] for k = 1..2
AND
high[i] > high[i + k] for k = 1..2


### 1.2 PPI-Low
Candle `i` is a PPI-Low if:

low[i] < low[i - k] for k = 1..2
AND
low[i] < low[i + k] for k = 1..2


PPIs are detected **separately for ES & NQ**.

---

## 2. Active PPI

A PPI remains **active** until:

- A **full candle close beyond it** occurs **in its direction**

So:

- PPI-High invalidates if we **close above it**
- PPI-Low invalidates if we **close below it**

Only **active PPIs** are valid liquidity references.

---

## 3. Interaction Classification

For each 5-minute candle, relative to the active PPI:

### Bearish Context → PPI-High

| Type | Definition |
|------|-----------|
| **SWEEP** | `high > PPI_high AND close < PPI_high` |
| **BREAK & HOLD** | `close > PPI_high` |
| **RESPECT** | `high <= PPI_high` |

BREAK & HOLD = **upward structure shift**

---

### Bullish Context → PPI-Low

| Type | Definition |
|------|-----------|
| **SWEEP** | `low < PPI_low AND close > PPI_low` |
| **BREAK & HOLD** | `close < PPI_low` |
| **RESPECT** | `low >= PPI_low` |

BREAK & HOLD = **downward structure shift**

---

## 4. Valid Reversal Context

A reversal-trade setup exists when:

> **At least one index sweeps its active PPI  
AND  
neither index performs a Break & Hold in sweep direction.**

This includes **two valid categories:**

---

### ✅ Type-A — Asymmetric Sweep Divergence
(one sweeps, one does not)

Examples:

| ES | NQ |
|----|----|
| SWEEP | RESPECT |
| RESPECT | SWEEP |

---

### ✅ Type-B — Dual Sweep Rejection
(both sweep — neither holds)

| ES | NQ |
|----|----|
| SWEEP | SWEEP |

This is often **higher conviction** because:

- liquidity is cleared on both indices
- both reject the breakout
- trapped positioning exists on both sides

---

## ❌ Invalid Context — Dual Break & Hold

If BOTH:

| ES | NQ |
|----|----|
| BREAK & HOLD | BREAK & HOLD |

➡ **No reversal setup — structure has transitioned**

This condition **kills any reversal bias.**

---

## 5. Divergence / Context Persistence

Once a valid reversal context forms:

It remains valid until:

1. BOS confirms
2. Dual Break & Hold occurs
3. Structural reset occurs
4. (Optional) time-decay threshold is reached

> **No valid reversal context = No trade.**

Sweeps alone are NOT enough.

---

# Phase-By-Phase Trade Process

---

## Phase 1 — Reversal Context Established

Reversal context becomes TRUE when:

- The market sweeps PPIs as described above
- And **no Break & Hold occurs**

No trades are taken yet.

---

## Phase 2 — Sweep Timing Anchor

The **Sweep candle close** starts the clock:

> **7-bar expiry window begins NOW**

State → `SWEEP_DETECTED`  
Record → `sweep_bar_index`

---

## Phase 3 — Break of Structure (BOS)

We require:

- Structure break in reversal direction
- **Confirmed only on a fully-closed 5-minute candle**
- Never intrabar

Once confirmed:

- `state = BOS_CONFIRMED`

---

## Phase 4 — Fib Mapping

From BOS impulse:

| Level | Role |
|------|------|
| **0.5** | Entry |
| **0.893** | Stop Loss |
| **0.1** | Take Profit |

Risk = fixed **1:1 R:R**

Entry = **limit order at 0.5**

---

## Phase 5 — Entry Window Constraint

Entry must fill:

> **Within 7 completed bars after Sweep**

If NOT:

- Cancel setup
- Mark → `EXPIRED`
- No trade recorded

---

## Phase 6 — Trade Management

Once filled:

- SL fixed at 0.893
- TP fixed at 0.1
- **Tick-level first-touch determines outcome**
- No trailing / scaling / overrides

---

# Strategy State Machine

| State | Description |
|------|-------------|
| IDLE | No setup present |
| CONTEXT_VALID | Reversal context detected |
| SWEEP_DETECTED | Sweep confirmed — timer running |
| BOS_CONFIRMED | Structure broken in reversal direction |
| PENDING_ENTRY | Order at 0.5 |
| FILLED | Position open |
| RESOLVED | SL or TP hit |
| EXPIRED | Entry not filled in time |

---

# Risk & Execution Rules

A trade MUST NOT be taken if:

- No valid reversal context exists
- BOS not confirmed on CLOSED candle
- Entry occurs after bar 7 post-Sweep
- Price never hits Fib 0.5
- Dual Break & Hold occurs
- Structure flips during setup

No manual overrides.

---

# Edge Cases

- If SL touched before entry → setup invalid
- If SL & TP touched same bar → **tick order decides**
- If a NEW sweep creates NEW context → old setup cancelled

---

# Timeframe Summary

| Component | Timeframe |
|----------|-----------|
| PPI detection | 5-minute |
| Sweep & Context detection | 5-minute |
| BOS confirmation | 5-minute closed bars only |
| 7-bar expiry clock | 5-minute |
| Entry, SL, TP fill logic | Tick-level |

---

# Tick-Accurate Backtesting Specification  
## Python + Backtrader — Ground-Truth Standard

This defines the execution model so:

> **Backtest results = Live behaviour under stated assumptions**

---

## Required Backtesting Principles

Backtesting MUST:

✔ Use **tick-level trade prints**  
✔ Process ticks in time order  
✔ Build 5-minute candles internally  
✔ Confirm BOS only on closed bars  
✔ Enforce sweep → BOS → entry ordering  
✔ Enforce 7-bar expiry  
✔ Use tick-first-touch fills  
✔ Produce deterministic results  

Backtesting MUST NOT:

❌ Read future candles  
❌ Infer fills from OHLC  
❌ Trigger BOS intrabar  
❌ Extend expiry  
❌ Reorder ticks  

---

## Why Backtrader

Because it:

- Runs event-driven (like live trading)
- Accepts multi-instrument tick feeds
- Resamples to 5-minute internally
- Prevents lookahead by design

So **live replay = batch backtest**

---

## Data Requirements

For ES & NQ tick streams:

- timestamp
- price
- (volume optional)

Ticks MUST be **chronologically ordered**.

---

## BOS Confirmation Rule

BOS logic **must** use only:

- the last CLOSED 5-minute bar
- never the current forming bar

This guarantees **no anticipation bias**.

---

## Tick-Accurate Fill Rules

### Long Entry
Fill when:

tick_price <= entry_price


### Long Stop
tick_price <= stop_price


### Long Target
tick_price >= target_price


(Shorts symmetric)

---

## First-Touch Rule

If SL & TP are both inside one bar:

> The first tick to hit either price wins.

No ambiguity.  
No estimation.

---

## Execution Assumptions

1. Fill-on-touch  
2. Zero latency  
3. Zero slippage (unless explicitly added)  
4. Fixed fees per contract  
5. Spread optional but consistent  

These assumptions MUST be stated so results remain interpretable.

---

## Sweep Timing Enforcement

On Sweep close:

sweep_index = bar_index


Each subsequent bar:

bars_since = current - sweep_index


If:

bars_since > 7 AND not filled


→ setup = `EXPIRED`

---

## Validation Requirements

To ensure **ground-truth reliability**, the engine MUST pass:

1. BOS only on closed bars
2. Sweep classification correctness
3. Correct Sweep anchor index
4. Tick-first-touch correctness
5. Deterministic repeatability
6. Live replay = batch backtest parity

If all pass:

> Backtesting output faithfully reflects real-time execution behaviour under the stated model.

---

# Final Rule

> **If the entry does not occur within 7 candles after the Sweep event —  
> the setup must NOT be traded.**

**End of Protocol.**
