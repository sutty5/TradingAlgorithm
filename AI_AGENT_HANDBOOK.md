# AI AGENT HANDBOOK & PROJECT MANIFEST
**Project**: Golden Protocol Strategy Optimization  
**Last Updated**: 2025-12-26  
**Status**: Active / Optimization Phase

---

## 1. Project Mission
To engineer the ultimate trading strategy day-trading **ES** and **NQ** futures. 
- **Target Win Rate**: 70%+
- **Target R:R**: ~1:1 (flexible if expectancy is high)
- **Priority**: High win rate and consistency over raw R:R.
- **Methodology**: Tick-accurate backtesting using **Python + Backtrader**.
    - **MANDATORY**: All backtests must use full tick-level data.
    - **MANDATORY**: Zero lookahead bias (closed candles only for signals).

---

## 2. Directory Map & Organization
All agents MUST adhere to this structure. Do not create random files in root.

```text
TradingStrategyDev/
├── AI_AGENT_HANDBOOK.md       <-- THIS FILE (Source of Truth)
├── backtest/                  <-- THE ENGINE (Python Code)
│   ├── engine.py              <-- Tick processing & Candle construction
│   ├── loader.py              <-- Databento .dbn parsing logic
│   ├── strategy.py            <-- Golden Protocol Logic (State Machine)
│   └── run.py                 <-- Execution Entry Point
├── data/                      <-- RAW DATA STORAGE
│   ├── databento_trades/      <-- Original .dbn files (Archive)
│   ├── es_trades.parquet      <-- OPTIMIZED ES TICK DATA (Sep-Dec 2025)
│   └── nq_trades.parquet      <-- OPTIMIZED NQ TICK DATA (Sep-Dec 2025)
├── Golden_Protocol_Strategy/  <-- STRATEGY DOCUMENTATION
│   ├── THE_GOLDEN_PROTOCOL... <-- Original Rulebook
│   └── Backtesting/           <-- RESULTS & REVIEWS (Markdown Reports)
└── Experiments/               <-- FUTURE: Optimization Configs & Logs
```

### Naming Conventions
- **Backtest Reviews**: `Golden_Protocol_Strategy/Backtesting/{version}_review_{date}.md`
- **Experimental Branches**: Use descriptive names `feature/optimize-entry-fib` or `experiment/trend-filter`.

---

## 3. Protocol for AI Agents
1.  **Read First**: Always read this `AI_AGENT_HANDBOOK.md` at the start of a session.
2.  **Log Your Work**: At the end of your session, append a new entry to the **Session Log** below.
3.  **Update Knowledge**: If you fix a bug or learn a quirk (e.g., data format), update the **Pitfalls & Learnings** section.
4.  **Chronological Order**: Never delete past logs. Append new ones.
5.  **Clean Code**: Keep the `backtest/` folder tailored to the *current best* version. Use `Experiments/` for variants.

---

## 4. Pitfalls & Learnings (Knowledge Base)
- **Data Loading**: We have converted `.dbn` to `.parquet` for performance. Use `data/es_trades.parquet` and `data/nq_trades.parquet`.
- **BOS Logic**: Break of Structure must be confirmed on **Candle Close** (5m). Do not trigger intra-candle.
- **Timing Rule**: The "7-candle expiry" is a hard rule. The custom engine enforces this.
- **Entry Logic**: "First Touch" execution. If the tick touches the limit, it fills.

---

## 5. Session Log (Reverse Chronological Audit)

### [Session 1] 2025-12-26 | Agent: Antigravity
**Goal**: Build Logic & Initial Verification  
**Actions**:
- Implemented custom Python backtest engine (`backtest/` folder).
- Solved `Databento` mapping issues (Loader now robust).
- Implemented "Golden Protocol (Original)" rules:
    - SMT Divergence (ES/NQ).
    - Sweep-Anchored Timing (7 bars).
    - Fixed 1:1 Risk Model (Entry 0.5 Fib).
- **Result**: Successfully ran backtest on Sep-Dec 2025 Data.
    - **Trades**: 447
    - **Win Rate**: ~50%
    - **PnL**: Negative (-164 pts).
    - **Conclusion**: Engine works, but base strategy needs optimization (Entry/Filters) to reach >70% WR target.
- **Artifacts**: Created `Golden_Protocol_Strategy/Backtesting/original_strategy_backtest_review.md`.

---
*End of Document*
