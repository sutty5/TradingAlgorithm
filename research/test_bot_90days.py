import sys
import os
import pandas as pd
import numpy as np
import logging
from datetime import timedelta

# Add root to path
sys.path.append(os.getcwd())

from alpaca_paper_trader import BarAggregator, StrategyInstance, CONFIGS, Candle, TradeState
from data_loader import load_and_prepare_data

# Logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("90DAY_TEST")

def run_90day_test():
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    if not os.path.exists(dbn_path):
        logger.error(f"Data not found at {dbn_path}")
        return

    logger.info(f"Loading 90-Day Data from {dbn_path}...")
    # Load 1m data using the standard loader (which includes Shift(1) fix)
    # data_loader.load_and_prepare_data returns 2m bars by default if not specified?
    # No, it accepts timeframe argument.
    # To test the BOT, we should feed it 1m bars and let BarAggregator handle 2m/5m.
    # But `load_and_prepare_data` returns "aggregated to timeframe" bars.
    # If we ask for 1m, we get 1m bars.
    
    es_df, nq_df = load_and_prepare_data(dbn_path, timeframe_minutes=1)
    
    logger.info(f"Data Loaded. ES: {len(es_df)}, NQ: {len(nq_df)}")
    
    # Init Bot Strategies
    # V8 Configs
    strats = [StrategyInstance(c) for c in CONFIGS if "V8" in c.name]
    
    # Aggregators for 2m and 5m
    agg_es_2m = BarAggregator(2)
    agg_nq_2m = BarAggregator(2)
    agg_es_5m = BarAggregator(5)
    agg_nq_5m = BarAggregator(5)
    
    trades = []
    
    # Merge timelines
    all_times = sorted(list(set(es_df.index).union(set(nq_df.index))))
    logger.info(f"Simulating {len(all_times)} minutes...")
    
    for ts in all_times:
        # 1. Get Bars
        candle_es = None
        candle_nq = None
        macro_val = 0
        
        if ts in es_df.index:
            row = es_df.loc[ts]
            if isinstance(row, pd.DataFrame): row = row.iloc[-1]
            candle_es = Candle(ts, float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']), "SPY") # Mapped to SPY by bot logic reqs? 
            # Wait, `alpaca_paper_trader` expects SYMBOLS to match those in CONFIG.
            # CONFIG uses "SPY" and "QQQ" or "ES" and "NQ"?
            # Let's check config.
            # `SYMBOL_ES` in alpaca_paper_trader is "SPY" (proxies).
            # But the V8 Strategy logic was optimized on ES/NQ futures data.
            # The bot logic (StrategyInstance) uses `strat.cfg.target_symbol`.
            # In `alpaca_paper_trader.py`, `SYMBOL_ES = 'SPY'`.
            # Configs are initialized using `SYMBOL_ES`.
            # So I must pass "SPY" as symbol name to match.
            
            # Extract Macro from ES data (loaded by data_loader which has 'macro_trend')
            # The `load_and_prepare_data` function adds 'macro_trend' column.
            macro_val = int(row['macro_trend'])
            
        if ts in nq_df.index:
            row = nq_df.loc[ts]
            if isinstance(row, pd.DataFrame): row = row.iloc[-1]
            candle_nq = Candle(ts, float(row['open']), float(row['high']), float(row['low']), float(row['close']), float(row['volume']), "QQQ")

        # 2. Update Aggregators
        # 2m
        es_2m = agg_es_2m.add_bar("SPY", candle_es) if candle_es else None
        nq_2m = agg_nq_2m.add_bar("QQQ", candle_nq) if candle_nq else None
        
        # 5m
        es_5m = agg_es_5m.add_bar("SPY", candle_es) if candle_es else None
        nq_5m = agg_nq_5m.add_bar("QQQ", candle_nq) if candle_nq else None
        
        # 3. Check Strategies
        for strat in strats:
            tf = strat.cfg.timeframe
            target_bar = None
            ref_bar = None
            
            if tf == 2:
                if es_2m and nq_2m and es_2m.timestamp == nq_2m.timestamp:
                    target_bar = es_2m if strat.cfg.target_symbol == "SPY" else nq_2m
                    ref_bar = nq_2m if strat.cfg.target_symbol == "SPY" else es_2m
            elif tf == 5:
                if es_5m and nq_5m and es_5m.timestamp == nq_5m.timestamp:
                    target_bar = es_5m if strat.cfg.target_symbol == "SPY" else nq_5m
                    ref_bar = nq_5m if strat.cfg.target_symbol == "SPY" else es_5m
            
            if target_bar and ref_bar:
                # Check Logic
                sig = strat.on_candles(target_bar, ref_bar, macro_val)
                
                if sig:
                    # Record Signal
                    trades.append({
                        'ts': ts,
                        'strat': strat.cfg.name,
                        'side': sig['side'],
                        'entry': sig['entry'],
                        'stop': sig['stop'],
                        'target': sig['target']
                    })
                    pass # Continue

    # Analysis
    logger.info(f"Simulation Complete. Total Signals: {len(trades)}")
    
    # Calculate Results (Simplified Backtest)
    # We iterate signals and look forward in 1m data to find outcome.
    
    total_pnl = 0.0
    wins = 0
    losses = 0
    
    logger.info("Verifying outcomes...")
    
    for t in trades:
        entry = t['entry']
        stop = t['stop']
        target = t['target']
        is_long = "BUY" in str(t['side'])
        start_ts = t['ts']
        
        # Select DF
        df = es_df if "ES" in t['strat'] else nq_df
        
        # Look forward
        subset = df[df.index > start_ts]
        outcome = "OPEN"
        pnl = 0.0
        
        filled = False
        
        for f_ts, row in subset.iterrows():
            if isinstance(row, pd.DataFrame): row = row.iloc[0]
            high = row['high']
            low = row['low']
            
            # Check Fill (Limit)
            if not filled:
                if is_long:
                    if low <= entry: filled = True
                else: 
                    if high >= entry: filled = True
            
            if filled:
                # Bracket
                if is_long:
                    if low <= stop:
                        outcome = "LOSS"
                        pnl = -abs(entry - stop)
                        break
                    if high >= target: # Target should be 0.0?
                        # V8 Strategies use Target=0.0 (Impulse End)? 
                        # Or Fixed Fib Target?
                        # In Config: fib_target is 0.0.
                        # Wait, `simulate_alpaca_week.py` logic calculated target price.
                        # `StrategyInstance` calculates `self.target_price` in `_check_bos`.
                        # Let's check logic:
                        # target_px = pivot - (rng * self.cfg.fib_target) if SHORT
                        # If fib_target is 0.0, target is Pivot Low.
                        pass
                        
                        # Wait, if strat returns Target, we use it.
                        if high >= target:
                            outcome = "WIN"
                            pnl = abs(target - entry)
                            break
                else: # Short
                    if high >= stop:
                        outcome = "LOSS"
                        pnl = -abs(stop - entry)
                        break
                    if low <= target:
                        outcome = "WIN"
                        pnl = abs(entry - target)
                        break
    
        if outcome == "WIN": wins += 1; total_pnl += pnl
        elif outcome == "LOSS": losses += 1; total_pnl += pnl
        
        # logger.info(f"{t['strat']} | {outcome} | PnL: {pnl:.2f}")

    if wins + losses > 0:
        wr = (wins / (wins + losses)) * 100
        logger.info(f"WIN RATE: {wr:.1f}% ({wins}/{wins+losses})")
        logger.info(f"TOTAL PnL Points: {total_pnl:.2f}")
    else:
        logger.info("No completed trades.")

if __name__ == "__main__":
    run_90day_test()
