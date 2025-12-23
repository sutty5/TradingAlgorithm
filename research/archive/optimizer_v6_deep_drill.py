
"""
v6.0 DEEP DRILL OPTIMIZER (NQ SHORT ONLY)

Goal: Refine the "NQ Short" Alpha to > 70% WR.
Focus: Micro-parameters (Fib, Expiry, Hours, Filters)
"""
import pandas as pd
import numpy as np
import multiprocessing as mp
from itertools import product
from dataclasses import dataclass
import time

from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection

# --- CONFIGURATION ---
DBN_PATH = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
# No sprint this time, run FULL data for deep validation
MIN_TRADES = 30 

# --- PARAMETER GRID ---
# Drilled down on NQ Short specific nuances
PARAMS = {
    'timeframe': [2],
    'fib_entry': [0.55, 0.618, 0.65], # Micro-adjust entry
    'entry_expiry': [3, 5, 7, 10], # Tighter expiry?
    'breakeven_r': [0.0], # Confirmed NQ hates BE. Keep 0.
    
    # FILTERS
    'max_atr': [0.0, 4.0, 6.0, 8.0], # Maybe NQ Short needs *some* upper bound on chaos?
    'min_rvol': [0.0, 0.5, 1.0, 1.5], # Flow check
    'min_wick': [0.0, 0.1, 0.2], # Slight wick requirement?
    
    # CONTEXT
    'use_macro': [False, True], 
    'bb_expand': [False], # Keep simple unless needed
    
    # HOURS (US Session variants)
    # 0 = All (minus default blocked)
    # 1 = AM Session Only (First 3 hours)
    # 2 = PM Session Only (Last 3 hours)
    'session_mode': [0, 1, 2] 
}

@dataclass
class TestResult:
    config: dict
    wr: float
    trades: int
    pnl: float

def run_single_backtest(args):
    """
    Worker function.
    """
    cfg, es_data, nq_data = args
    
    # Create Config Object
    bt_config = BacktestConfig(
        timeframe_minutes=cfg['timeframe'],
        fib_entry=cfg['fib_entry'],
        fib_stop=1.0,
        fib_target=0.0,
        entry_expiry_candles=cfg['entry_expiry'],
        breakeven_trigger_r=cfg['breakeven_r'],
        max_atr=cfg['max_atr'],
        min_rvol=cfg['min_rvol'],
        min_wick_ratio=cfg['min_wick'],
        use_macro_filter=cfg['use_macro'],
        require_bb_expansion=cfg['bb_expand'],
        entry_mode="FIB" # Stick to FIB for Deep Drill
    )
    
    engine = GoldenProtocolBacktest(bt_config)
    res = engine.run(es_data, nq_data)
    
    # Filter for NQ SHORT
    trades = [t for t in res.trades if t.asset == "NQ" and t.sweep_direction == TradeDirection.SHORT]
    
    # SESSION FILTER
    # UTC Hours mapping to US Session (est approx)
    # US Open: 13:30 UTC -> 14.
    # AM Session: 14, 15, 16
    # PM Session: 19, 20, 21? (Close is 21:00 UTC usually)
    # Let's use simple hour sets
    
    # Default blocked: 8, 9, 18, 19
    blocked = [8, 9, 18, 19]

    if cfg['session_mode'] == 1: # AM Only
        # Keep 13, 14, 15, 16 
        valid_hours = [13, 14, 15, 16]
        trades = [t for t in trades if t.ppi_time.hour in valid_hours]
    elif cfg['session_mode'] == 2: # PM Only
        # Keep 19, 20, 21
        valid_hours = [19, 20, 21]
        trades = [t for t in trades if t.ppi_time.hour in valid_hours]
    else:
        # Standard block filter
        trades = [t for t in trades if t.ppi_time.hour not in blocked]
    
    wins = sum(1 for t in trades if t.state == TradeState.WIN)
    losses = sum(1 for t in trades if t.state == TradeState.LOSS)
    filled = wins + losses
    pnl = sum(t.pnl for t in trades)
    wr = (wins / filled * 100) if filled > 0 else 0
    
    return TestResult(
        config=cfg,
        wr=wr,
        trades=filled,
        pnl=pnl
    )

def generate_configs():
    keys, values = zip(*PARAMS.items())
    for v in product(*values):
        yield dict(zip(keys, v))

def main():
    print(f"Loading data from {DBN_PATH}...")
    es_data, nq_data = load_and_prepare_data(DBN_PATH, timeframe_minutes=2)
    
    configs = list(generate_configs())
    print(f"Generated {len(configs)} NQ Short configurations.")
    
    jobs = []
    for cfg in configs:
        jobs.append((cfg, es_data, nq_data))
        
    print(f"Starting Deep Drill on {mp.cpu_count()} cores...")
    
    start_time = time.time()
    
    with mp.Pool(processes=mp.cpu_count()) as pool:
        results = pool.map(run_single_backtest, jobs)
        
    elapsed = time.time() - start_time
    print(f"Optimization complete in {elapsed:.1f}s")
    
    # Analysis
    passed = [r for r in results if r.trades >= MIN_TRADES]
    passed.sort(key=lambda x: x.wr, reverse=True)
    
    data = []
    for r in passed:
        row = r.config.copy()
        row['wr'] = r.wr
        row['trades'] = r.trades
        row['pnl'] = r.pnl
        data.append(row)
        
    df = pd.DataFrame(data)
    df.to_csv('deep_drill_results.csv', index=False)
    print("Results saved to deep_drill_results.csv")
    
    print("\n--- TOP DEEP DRILL CANDIDATES ---")
    cols = ['fib_entry', 'entry_expiry', 'max_atr', 'min_rvol', 'session_mode', 'wr', 'trades', 'pnl']
    print(df.head(10)[cols].to_string())
    
    # Check Grail
    grails = df[df['wr'] >= 70]
    if not grails.empty:
        print("\n🏆 70% BREAKTHROUGH FOUND!")
        print(grails.head(5)[cols].to_string())

if __name__ == "__main__":
    mp.freeze_support()
    main()
