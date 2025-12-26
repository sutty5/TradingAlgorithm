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
- Strategy signals operate on **5-minute bars**
- Execution & fills operate on **tick-level data**

**Data Quality**
- Historical testing MUST use **full tick-level trade-print data**
- No aggregated candle-only backtests are permitted

---

## Core Idea – In Plain English

We trade a **very specific failure–reversal sequence**:

1. **Divergence**  
   ES & NQ disagree structurally.

2. **Sweep**  
   Price runs liquidity beyond the divergence zone.

3. **Rejection**

4. **Break of Structure (BOS)**  
   Confirmed **only when the 5-minute candle closes**.

5. **Retrace Entry**  
   Limit order at **50% retrace (Fib 0.5)** of BOS impulse.

6. **Strict Timing**  
   Entry must occur **within 7 candles after the Sweep candle**.

If entry does NOT occur in time  
➡ **NO TRADE**

---

# Phase-by-Phase Strategy Definition

## Phase 1 — Divergence Context

Divergence occurs when ES & NQ disagree structurally at or near a pivot.

Examples:
- One makes a higher high / lower low, the other does not  
- One sweeps liquidity while the other does not

Divergence is **context – not a trade signal.**

---

## Phase 2 — Liquidity Sweep

A **Sweep** is when price:

- Trades beyond an obvious high/low  
- Triggers resting liquidity  
- **Fails to hold beyond that level**

This Sweep becomes our **timing anchor.**

> From the Sweep candle close  
> The **7-bar clock begins.**

---

## Phase 3 — Break of Structure (BOS)

Price reverses and **breaks structure in the opposite direction.**

### BOS Confirmation Requirement

A BOS is only valid if:

> **The 5-minute candle CLOSES beyond the structural level.**

That means:

❌ No BOS during candle formation  
❌ No intra-bar trigger logic  
❌ No wick-based confirmation  
✔ BOS exists ONLY after the bar closes

This prevents BOS-fakeouts turning into sweeps.

---

## Phase 4 — Fib Mapping the BOS Impulse

Once BOS confirms:

- Identify BOS impulse
- Apply Fib from:
  - Start of impulse → End of impulse

Levels:

| Level | Purpose |
|------|---------|
| **0.5** | Entry |
| **0.893** | Stop Loss |
| **0.1** | Take Profit |

Risk model:
- Fixed 1:1  
- No discretionary modifications

---

## Phase 5 — Entry Logic

Entry is valid **ONLY IF:**

✔ BOS already confirmed  
AND  
✔ Price retraces to 0.5 Fib  

If price never tags 0.5  
➡ **NO TRADE**

There are no exceptions.

---

## Phase 6 — Timing Constraint

### Official Timing Rule

The trade entry must be filled:

> **Within 7 completed 5-minute candles AFTER the Sweep candle.**

That means:

- Sweep = Candle 0
- Count forward 7 completed 5-minute bars
- If entry not filled → Setup expires

### Trade Expiry Condition

If Fib 0.5 is NOT reached by bar 7:
➡ **TRADE EXPIRES**

No late fills  
No forced entries  
No extensions  

This preserves structural relevance.

---

# Strategy State Machine

| State | Meaning |
|------|--------|
| IDLE | No setup |
| SWEEP_DETECTED | Sweep confirmed – timer starts |
| BOS_CONFIRMED | BOS confirmed on CLOSED bar |
| PENDING_ENTRY | Limit order active at 0.5 |
| FILLED | Position active |
| RESOLVED | SL or TP hit |
| EXPIRED | Entry window closed |

---

# Risk & Execution Rules

### A trade MUST NOT be taken if:

- BOS is not confirmed by candle close
- Entry occurs after the 7-bar window
- Price never retraces to 0.5
- Sweep did not follow divergence
- Context is unclear

This strategy **never chases.**

---

# Edge-Case Handling

### If SL is touched before entry
❌ Setup invalid — NO TRADE

### If TP & SL both touch in one bar
Use **first tick to touch rule**

### If a new Sweep occurs before entry
RESET the setup  
Previous setup becomes invalid

---

# Strategy Philosophy

Liquidity Sweep = **intent**  
BOS = **commitment**  
Retrace = **optimal risk entry**  
Timing = **validity**

Only trade when all four align.

---

# Summary Checklist

| Rule | Must Be True |
|------|--------------|
| Divergence Present | ✅ |
| Sweep Occurs | ✅ |
| Start 7-bar clock | ⏱ |
| BOS Confirmed on Candle Close | ✅ |
| Fib Anchored to BOS Impulse | ✅ |
| Entry ONLY at 0.5 Fib | 🎯 |
| Fill within 7 bars of Sweep | REQUIRED |
| SL = 0.893 | 🔒 |
| TP = 0.1 | 🎯 |
| No Fill in Time Window | CANCEL |

---

# **Tick-Accurate Backtesting Specification (Python + Backtrader)**

This section defines the **mandatory rules required so backtesting results ALWAYS match real-time execution behaviour.**

If your backtester follows this section **exactly**, the results represent the **ground-truth outcome** of this strategy under the stated assumptions.

---

## Core Principles

Backtesting MUST:

✔ Run on **tick-level trade data**  
✔ Process ticks strictly in time order  
✔ Build 5-minute candles from ticks inside the engine  
✔ Confirm BOS using **only completed bars**  
✔ Execute fills using **first-touch tick logic**  
✔ Enforce Sweep → BOS → Entry ordering  
✔ Enforce the 7-bar expiry clock  
✔ Remain deterministic and reproducible  

Backtesting MUST NOT:

❌ Read future candles  
❌ Use pre-built bar arrays for logic  
❌ Infer fills from OHLC  
❌ Trigger BOS during unclosed candles  
❌ Enter after expiry  
❌ Reorder ticks  

---

## Why Backtrader Is Used

Backtrader is chosen because it:

- Supports tick-level event-driven feeds
- Builds higher-timeframe bars internally
- Processes data **exactly like a live feed**
- Supports multiple instruments (ES + NQ)
- Handles limit/stop orders reliably
- Avoids look-ahead bias by design

This ensures backtests mirror live trading flow.

---

## Data Requirements

For each instrument (ES + NQ):

- Full tick-level trade data
- Ordered by timestamp

Order enforcement:

> **Ticks must be strictly time-ordered before entry into the engine.**

No reordering  
No batch evaluation  
No forward scans

---

## Candle Construction Rules

- Feed tick data into Backtrader
- Resample to **5-minute bars internally**
- A bar is only “complete” when Backtrader rolls to the next bar

### BOS Logic MUST Use:
- `close[-1]` (last CLOSED bar)

### BOS Logic MUST NOT Use:
- Current live bar close
- Candle wicks during formation

This guarantees BOS isn’t anticipated.

---

## Entry & Exit Fill Logic (Must Use Tick-Level)

### Entry Fill — Long
Fill when a tick trades:

`<= 0.5 Fib`

### Stop Loss — Long
Hit when a tick trades:

`<= SL`

### Take Profit — Long
Hit when a tick trades:

`>= TP`

Shorts are symmetric.

### FIRST TOUCH RULE
The **first tick** to reach either level decides the outcome.

There is no tie logic.

---

## Official Execution Assumptions

These assumptions MUST be applied:

1. **Fill on touch**
2. **Zero queue & latency**
3. **Zero slippage unless explicitly added**
4. **Commission + fees must be applied consistently**
5. **Bid/ask spread modelling optional**
6. **One-contract model unless otherwise defined**

These define the trading universe.

---

## Sweep Timing Enforcement

When Sweep confirms:

- Record Sweep bar index
- Start 7-bar countdown

At each completed bar check:

`bars_since_sweep = current_index − sweep_index`

If:

`bars_since_sweep > 7 AND not filled`

➡ **Setup = EXPIRED**

Orders cancelled  
No trade recorded  

---

## Required Validation Tests

To guarantee correctness:

### 1. BOS Trigger Validation
Verify BOS only occurs on CLOSED bars

### 2. Expiry Validation
Verify entry never occurs after bar 7

### 3. Tick First-Touch
Verify tick ordering determines outcome

### 4. Determinism Test
Same data = same results

### 5. Forward-Consistency Test
Live simulated feed = same signals

---

## What “100% Reliable” Means Here

Under the assumptions above:

✔ No look-ahead  
✔ True tick sequence processing  
✔ True first-touch fills  
✔ BOS confirmed only on closed bars  
✔ Sweep timing enforced  
✔ Deterministic behaviour  

Therefore:

> **Backtesting outputs represent the true execution outcome of this strategy operating live under the stated execution assumptions.**

This makes optimisation & tuning **trustworthy.**

---

# Final Rule

> **If entry does not occur within 7 candles after the Sweep event —  
> the setup must NOT be traded.**

**End of Protocol.**
