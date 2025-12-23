# 🧠 AI AGENT STRATEGY MEMORY (Source of Truth)

> [!URGENT]
> **INSTRUCTION TO ALL AI AGENTS:**
> 1.  **READ THIS DOCUMENT FIRST** before taking any action.
> 2.  **UPDATE THIS DOCUMENT** at the end of every session with new findings, tests, or code changes.
> 3.  **DO NOT HALLUCINATE** parameters. Use the "Current Active Strategy" section below.

---

## 🚀 Current Active Strategy: v7.0 "God Mode"

**Status:** 👑 FINALIZED (Dec 22, 2025)
**Objective:** Maintain >70% Win Rate across ALL active pairs (ES & NQ) using direction-specific logic.

| Parameter | NQ SHORT (The "Alpha") | NQ LONG (The "Banker") | ES SHORT (The "Validator") | ES LONG (The "Optimizer") |
|-----------|------------------|------------------|----------------------|-------------------|
| **Source** | Deep Drill | Cloud Optimization | **Scientific Validation** | **Scientific Validation** |
| **Timeframe** | **2 Minutes** | **5 Minutes** | **2 Minutes** | **5 Minutes** |
| **Win Rate** | **62-72%** | **71%** | **76%** | **65%** |
| **Entry** | 0.618 Fib | 0.5 Fib | 0.5 Fib | 0.5 Fib |
| **Target** | 0.0 (Impulse) | 0.0 (Impulse) | 0.0 (Impulse) | **0.1 (Extension)** 🎯 |
| **Stop** | 1.0 (Standard) | 1.0 (Standard) | **1.0 (Standard)** | 1.0 (Standard) |
| **Expiry** | 10 Candles | 10 Candles | 15 Candles | 10 Candles |
| **Trailing** | **ON** | **ON** | **ON** | **ON** |


### 🛠️ Key Strategic Insight (v7.0)
*   **The "God Mode" Concept:** We no longer use a "One Size Fits All" approach.
*   **NQ Shorts** require **Speed** (2m, 5 candle expiry, no filters) because they are often violent liquidations.
*   **NQ Longs** require **Confirmation** (5m, Wick Rejection) to avoid catching falling knives.
*   **ES Shorts** require **Room to Breathe** (Deep Stop 0.893) matching the Original Protocol theory.

---

## 📜 Strategy Evolution History (Log)

| Version | Date | Key Change | Outcome | Verdict |
|---------|------|------------|---------|---------|
| **v4.7** | Dec 15 | Original 2m Strategy (Both assets) | 53% WR, $9k PnL | **Baseline.** Promising but noisy. |
| **v5.0** | Dec 22 | "Einstein" Optimization (NQ Only) | 71.7% WR, low vol | **Validation.** Proved high WR possible. |
| **v6.0** | Dec 22 | Deep Drill (NQ Short) | 71.74% WR | **Breakthrough** for NQ Shorts. |
| **v7.0** | Dec 22 | **Cloud Optimization (God Mode)** | **76% WR (ES) / 71-77% WR (NQ)** | **THE GRAIL.** Multi-logic approach validated. |

---

## 🛠️ Tooling & Infrastructure Inventory

### ☁️ Cloud Optimization Suite (NEW)
*   **Modal.com Integration:** Successfully burst to **100+ Concurrent vCPUs** (~1.2kW Power).
*   **`optimizer_cloud_final.py`:** Massively parallel grid searcher (48,000 configs in < 1 hour).
*   **`modal.Volume`:** Persistent cloud storage for 900MB Tick Data (`.dbn` files).
*   **`golden_protocol_v7_god_mode.pine`:** Auto-Tuning Strategy Script that loads "God Mode" settings based on Ticker/Direction.

### 🐍 Python Core
*   `data_loader.py` & `backtest_engine.py`: The robust backend powering the cloud search.

---

## 🗺️ Roadmap & Next Steps

### Phase 1: Alpaca Paper Deployment (Executed)
*   [x] **Infrastructure:** `alpaca_paper_trader.py` updated to **v7.0 God Mode** (Multi-TF).
*   [x] **Proxy Strategy:** Using **QQQ** (NQ Proxy) and **SPY** (ES Proxy).
*   [ ] **Validation:** Monitor for correct PPI Logic (Simultaneous 2m & 5m scanning).

### Phase 2: Live Trading
*   [ ] After 1 week of profitable paper trading, switch API keys to Live.
*   [ ] Initial size: 1 Micro Contract (MNQ).

### Phase 3: The Scientific Validation (Completed Dec 23)
*   [x] **Objective:** Empirically verify "Original Protocol" mechanics vs "v7" mechanics.
*   [x] **Findings:**
    1.  **Trailing Fibs:** Dynamic (v7) VASTLY outperforms Static (Original). Static failed to meet minimum 55% WR criteria.
    2.  **Target:** 0.0 (Impulse End) is superior for most legs. **EXCEPTION:** ES Longs perform better with 0.1 Extension (65% vs 63%).
    3.  **Stop Loss:** Standard 1.0 (Sweep Extreme) outperforms Deep Stop (0.893). The 76% WR was achieved with Stop 1.0.
*   [x] **Action:** Update Strategy to use Stop 1.0 globally, and Target 0.1 for ES Longs.

---

## 📝 Agent Session Log

*   **2025-12-23 (Agent Antigravity):**
    *   **Phase 3 Scientific Validation:** Executed large-scale A/B test (Trailing vs Static, Target 0.0 vs 0.1, Stop 1.0 vs 0.893).
    *   **Debunked:** "Deep Stop (0.893)" and "Static Fibs" proved inferior.
    *   **Optimized:** Found that **ES Longs** require **Target 0.1** (Extension) to reach 65% WR.
    *   **Verified:** ES Short 2m maintains **76% WR** with Standard Stop (1.0).


