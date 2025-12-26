# THE GOLDEN PROTOCOL – Official Strategy Rulebook (Sweep-Anchored Timing Version)

## Market & Framework

**Markets watched**
- ES (S&P 500 futures)
- NQ (Nasdaq-100 futures)

**Execution instrument**
- Either ES or NQ (commonly NQ)

**Timeframe**
- **5-minute charts only**

**Data quality**
- Tick-accurate backtesting strongly preferred  
- Absolutely **no look-ahead access**


---

## Core Idea – In Plain English

We trade a **very specific failure–reversal pattern**:

1. **Divergence**  
   ES and NQ disagree at a structural turning point.

2. **Sweep**  
   Price runs liquidity beyond the divergence zone.

3. **Rejection**  
   The sweep fails to hold.

4. **Break of Structure (BOS)**  
   Momentum shifts and structure breaks — confirmed **only when the candle closes**.

5. **Retrace Entry**  
   We wait for price to return to the 50% retrace (Fib 0.5) of the BOS impulse.

6. **Timing Constraint**  
   The entry must occur **within 7 candles from the Sweep candle**.

If price does not tag entry in time:  
➡ **The setup expires — no trade.**


---

# Phase-by-Phase Strategy Definition


## Phase 1 — Divergence Event

A divergence is recorded when ES and NQ display **structural disagreement** at or near a pivot.

Examples:
- One makes a higher high / lower low while the other does not
- One market sweeps liquidity while the other does not

This gives context that one market is faking out.


---

## Phase 2 — Liquidity Sweep

A **Sweep** is defined as:

- Price extends *beyond* an obvious prior high/low
- Clearly stops out resting liquidity
- But does **not** hold beyond it

This sweep becomes the **anchor event** for timing.

> **Important**  
> The Sweep must follow the divergence context.


---

## Phase 3 — Break of Structure (BOS)

We wait for **clear structural failure in the direction opposite the sweep.**

### BOS Confirmation Rule

A BOS is **only confirmed when the candle CLOSES beyond the structural level.**

❌ No confirmation during the bar  
❌ No wick breaks  
❌ No intrabar triggers  

This prevents BOS from being confused with a second sweep.


---

## Phase 4 — Fib Mapping of the BOS Impulse

Once BOS confirms:

- Identify the BOS impulse
- Draw Fib from:
  Start of impulse → End of impulse
- Entry = **Fib 0.5**
- Stop Loss = **Fib 0.893**
- Take Profit = **Fib 0.1**

Risk profile:
- Fixed 1:1 R/R
- No management changes


---

## Phase 5 — Entry Logic

Entry is valid **ONLY IF BOTH ARE TRUE**

✔ BOS has already confirmed  
AND  
✔ Price retraces to Fib 0.5  

> If price never retraces  
> **no trade is taken**


---

## Phase 6 — Timing Constraint (Critical Rule)

### Official Rule

The trade entry must occur:

> **Within 7 candles AFTER the Sweep candle.**

Meaning:

- Candle 0 = the Sweep candle
- Count forward 7 completed candles
- Entry @ Fib 0.5 must occur inside this window

### If price does NOT tag entry within 7 candles
➡ **THE SETUP EXPIRES — NO TRADE**

This prevents:
- stale setups
- late reversions
- post-event noise traps


---

# Strategy State Machine

| State            | Description                                |
|------------------|--------------------------------------------|
| IDLE             | No signal present                          |
| SWEEP_DETECTED   | Sweep confirmed → 7-bar clock starts       |
| BOS_CONFIRMED    | BOS candle closes beyond structure         |
| PENDING_ENTRY    | Limit order active at Fib 0.5              |
| FILLED           | Order filled                               |
| RESOLVED         | TP or SL hit                               |
| EXPIRED          | Entry not filled within 7 bars of Sweep    |


---

# Risk & Execution Rules

### A trade must NOT be taken if:

- BOS has not yet closed
- Entry occurs after the 7-bar window
- Retrace never reaches 0.5
- Sweep did not follow a divergence
- Context is unclear


---

# Implementation Notes

### Look-ahead bias prevention

- BOS must use **bar-close confirmation** only on completed 5M bars
- Entry triggers using only **historically known data up to the current tick**
- No future highs/lows, no “peek” into subsequent ticks

### Order behaviour

- Limit order @ Fib 0.5
- Cancel order at bar 7 post-Sweep if not filled
- TP and SL fixed at order placement

### Never do:

- Market entries
- Discretionary overrides
- Dynamic target adjustments
- Late entries beyond 7-bar window


---

# Edge-Case Handling

### If price hits SL (0.893) before entry (0.5)
➡ Setup invalid — no trade

### If TP & SL hit in same candle
Use **first-touch logic** based on tick sequence

### If a new sweep occurs before entry
Reset setup to new sweep and invalidate previous pending setup


---

# Strategy Philosophy

Liquidity sweeps show **intent**  
Break of structure shows **commitment**  
Retrace gives **optimal risk efficiency**  
Timing preserves **structural validity**

We only trade when all four align.


---

# Summary Checklist

| Requirement                                  | Status  |
|---------------------------------------------|---------|
| Divergence present                           | MUST    |
| Sweep occurs                                 | MUST    |
| Start 7-bar clock from Sweep candle         | IMMED.  |
| BOS confirmed on candle close                | MUST    |
| Fib anchored on BOS impulse                  | MUST    |
| Entry only at 0.5 Fib                        | MUST    |
| Entry fills ≤ 7 candles after Sweep          | MUST    |
| SL = 0.893 Fib                               | FIXED   |
| TP = 0.1 Fib                                 | FIXED   |
| No fill in time window                       | CANCEL  |


---

# Tick-Level Backtesting Protocol (Python & Backtrader)

This section defines **how to backtest THE GOLDEN PROTOCOL on tick-level data** (e.g. DataBento `.dbn`) in a way that:

- Eliminates **look-ahead bias**
- Mimics **live real-time data flow**
- Keeps strategy logic **identical** to production

You will implement all code in **Python**, using **Backtrader** as the main engine.

---

## Why Backtrader for This Strategy?

Compared to other Python backtesting libraries:

- **Strong support for intraday and tick data**  
  Backtrader is designed to handle tick data and resample to higher timeframes (like 5M) internally.

- **Event-driven architecture**  
  Your strategy logic runs inside `next()` and processes data strictly **in time order**, like a live feed.

- **Multi-data support**  
  You can load ES and NQ in parallel as separate data feeds and implement divergence logic cleanly.

- **Custom data feeds**  
  You can create a custom DataFeed that reads your DataBento `.dbn` (or converted CSV/Parquet) tick-by-tick.

For your use case (tick-level ES/NQ futures, 5M logic, no lookahead), **Backtrader is one of the cleanest, most flexible options in Python**.

---

## Data Preparation (Tick Level)

1. **Convert or stream `.dbn` into Python**
   - Either:
     - Use DataBento’s Python API to stream ticks, or
     - Convert `.dbn` → CSV/Parquet once and read that

2. **Ensure strict ordering**
   - Sort all ticks by:
     1. `timestamp`
     2. (optionally) a sequence index if provided
   - There must be **no out-of-order ticks** in the feed.

3. **Fields you need per tick**
   Minimum:
   - `datetime`
   - `price`
   - `volume` (optional but recommended)
   - `symbol` (ES / NQ)

4. **One feed per instrument**
   - Backtrader: create separate data feeds for ES and NQ
   - Each feed is tick-level and sorted

---

## Building 5-Minute Candles Without Lookahead

You want 5M logic, but data arrives as ticks.

**Correct approach:**

- Feed Backtrader with **tick data**
- Use Backtrader’s `resampledata` to produce internal 5M bars
- Only treat a 5M bar as **“completed”** when Backtrader rolls over to the next bar

### Key principle

All BOS and structural logic must use **only completed 5M bars**, not the still-forming bar.

In code terms:

- Use something like `if self.data5m.close[-1]` for last **completed** bar
- Never rely on the “current” (still open) 5M bar for BOS confirmation

---

## Event-Driven Loop (Conceptual)

At a high level, your Backtrader run will behave like this:

1. **Tick arrives** (from ES / NQ feed)
2. Backtrader:
   - Updates tick series
   - Updates the current 5M bar (OHLC) for that instrument
   - When the 5M boundary is reached, finalises the bar and shifts it into history

3. **Strategy `next()` fires**
   - Sees:
     - All **historical completed 5M bars**
     - Current partial 5M bar (if you choose to inspect it)
   - You implement:
     - Divergence checks (using completed bars)
     - Sweep detection
     - BOS confirmation (only on closed bar)
     - Fib mapping and entry placement
     - Tick-level fill logic against orders

Because Backtrader only advances in time order and does not expose future ticks, this naturally prevents lookahead bias *as long as you don’t manually cheat* (e.g. scanning future data arrays).

---

## How to Enforce BOS on Candle Close

Within your `Strategy`:

- Maintain internal state, e.g.:

  - `state = IDLE / SWEEP_DETECTED / BOS_CONFIRMED / PENDING_ENTRY / FILLED`
  - Record:
    - Sweep candle index
    - BOS candle index
    - Fib levels

- BOS rule:
  - Only set `state = BOS_CONFIRMED` **when a 5M bar closes** beyond a structure level.
  - In practice, that means you look at the **previous** 5M bar (`close[-1]`) to confirm BOS.

- You **do not** evaluate BOS on the actively-forming bar.

This mirrors real-time: you cannot know the closing price until the bar ends.

---

## Implementing the 7-Candle Window (Sweep → Entry)

The 7-candle expiry is anchored on the **Sweep candle**.

Implementation ideas:

- When a Sweep is confirmed on the 5M timeframe:
  - Record `self.sweep_bar_index = len(self.data5m)` or equivalent
  - Set `state = SWEEP_DETECTED`

- When BOS confirms:
  - You are somewhere at or after `self.sweep_bar_index`.
  - Fib is drawn from BOS impulse.
  - Limit order at 0.5 is created.
  - Still track the original `sweep_bar_index`.

- Each new **completed** 5M bar:
  - Compute `bars_since_sweep = len(self.data5m) - self.sweep_bar_index`
  - If `bars_since_sweep > 7` and order not filled:
    - Cancel limit order
    - `state = EXPIRED`
    - Reset.

Because this is computed on **historical bar indices**, there is no lookahead; you only ever compare to past data.

---

## Tick-Level Order Fill Logic

You want fills to behave like live trading.

### Limit Entry @ 0.5

- A limit order is filled when the **tick price** trades through or touches the entry level:

  - Long entry:
    - Fill when `tick_price <= limit_price` for a buy (if your data provides bid/ask, you decide whether you use trade price, bid, or ask as the “truth”).
  - Short entry:
    - Fill when `tick_price >= limit_price` for a sell.

### SL / TP Simulation (First-Touch)

Once in a position:

- Maintain precise tick-level checks:
  - For a long:
    - If `tick_price <= stop_loss`: SL hit first → close trade (loss).
    - Else if `tick_price >= take_profit`: TP hit first → close trade (win).
  - For a short:
    - If `tick_price >= stop_loss`: SL hit first.
    - Else if `tick_price <= take_profit`: TP hit first.

- Because you’re processing one tick at a time in time order, the **first tick** that touches either level determines outcome, faithfully matching “first-touch” real-time behaviour.

### If both levels are crossed within a single 5M bar

- Tick data removes ambiguity:
  - You see exactly which price was traded first.
- You never have to guess based on OHLC alone.

---

## No-Lookahead Principles (Do/Don’t List)

### DO

- Only inspect **completed 5M bars** for BOS and structural decisions.
- Only place/modify/cancel orders inside `next()` when new ticks or bars arrive.
- Keep all setup state in variables that are updated incrementally (no scanning forward).
- Use tick timestamps as the single source of truth for progression.

### DO NOT

- Compute Fib or structure using data from the **current incomplete bar close**.
- Manually index into arrays using “future” indices (e.g. `close[+1]`).
- Aggregate bars from the full dataset first and then let the logic freely scan the entire array (this encourages accidental peeking).
- Use indicators or helper functions that internally use future bars (double-check any custom stuff you write).

---

## What “100% Accurate” Really Means Here

You cannot perfectly simulate *microsecond exchange internals*, queue position, or latency — unless you also model those explicitly.

What you **can** do with your DataBento tick data + Backtrader:

- Guarantee **no lookahead bias**  
  (strategy never sees future ticks or bar closes)
- Guarantee **deterministic outcomes**  
  (given the same tick sequence, you always get the same trades)
- Guarantee **correct touch order**  
  (entry/TP/SL determined by the actual tick ordering)

Under the assumptions:

- Fills occur when price is touched (no partial fills / no queue),
- Zero latency and no slippage unless you explicitly model them,

…then your backtest behaves **as if you were trading live with instantaneous execution at touched prices**.

That’s about as “100% accurate” as it gets for this kind of research.

---

## Suggested Validation Steps

To be confident your backtest matches the written protocol:

1. **Unit-test BOS confirmation**
   - For a sample of BOS events, assert they only trigger on completed 5M bar closes.

2. **Unit-test 7-candle expiry**
   - For known sweeps, assert that:
     - Any entry after bar 7 is rejected.
     - Any entry before or at bar 7 is accepted.

3. **Unit-test tick-first-touch logic**
   - Construct synthetic sequences where:
     - Entry, SL, and TP levels are all inside one 5M bar.
     - Verify you always close based on the first level hit in tick sequence.

4. **Compare against “live simulated feed”**
   - Feed the same tick data into a paper-live framework (same strategy) and confirm identical trades vs the backtest.

If all of those pass, your backtest is effectively mirroring live, real-time execution under your stated assumptions.

---

# Final Rule

> **If the entry does not occur within 7 candles after the Sweep event —  
> the setup must NOT be traded.**

**End of Protocol.**
