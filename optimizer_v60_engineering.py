
"""
v6.0 RE-ENGINEERING OPTIMIZER

Features:
- "Sprint" Mode: Test last 3 weeks first. Only run full backtest if > 70% WR.
- Multiprocessing: Uses all CPU cores.
- New Filters: Macro Trend, BB Expansion.
- Deep Grid: Tests thousands of permutations.
"""
import pandas as pd
import numpy as np
import multiprocessing as mp
from itertools import product
from dataclasses import dataclass
from datetime import timedelta
import time
import os

from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState

# --- CONFIGURATION ---
DBN_PATH = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
SPRINT_WEEKS = 3
MIN_SPRINT_TRADES = 15 # Minimum trades in 3 weeks to qualify
TARGET_WR = 60.0 # Relaxed slightly from 70 to capture "near miss" candidates for full run

# --- PARAMETER GRID ---
# Extensive grid for "Out of Box" discovery
PARAMS = {
    'timeframe': [2],
    'asset': ['ES', 'NQ'],
    'fib_entry': [0.5, 0.618], # Test aggressive 0.5
    'entry_expiry': [5, 12],
    'breakeven_r': [0.0, 0.5],
    
    # RISK FILTERS
    'max_atr': [0.0, 4.0, 6.0],
    'min_rvol': [0.0, 1.0, 1.5],
    'min_wick': [0.0, 0.25, 0.35],
    
    # NEW FILTERS
    'use_macro': [False, True], # 1H Alignment
    'bb_expand': [False, True], # Volatility Expansion
}

@dataclass
class TestResult:
    config: dict
    sprint_wr: float
    sprint_trades: int
    sprint_pnl: float
    full_wr: float = 0.0
    full_trades: int = 0
    full_pnl: float = 0.0
    passed_sprint: bool = False

def run_single_backtest(args):
    """
    Worker function for multiprocessing. 
    args: (config_dict, es_data, nq_data, sprint_start_date)
    """
    cfg, es_data, nq_data, sprint_start = args
    
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
        require_bb_expansion=cfg['bb_expand']
    )
    
    # RUN SPRINT FIRST (Filter data by date)
    # We slice the dataframes to keep it fast? 
    # Or just run full and filter results? Running full is expensive.
    # Slicing is better.
    
    es_sprint = es_data[es_data.index >= sprint_start]
    nq_sprint = nq_data[nq_data.index >= sprint_start]
    
    engine = GoldenProtocolBacktest(bt_config)
    res = engine.run(es_sprint, nq_sprint)
    
    # Filter for Asset
    trades = [t for t in res.trades if t.asset == cfg['asset']]
    
    # Calc Sprint Stats
    wins = sum(1 for t in trades if t.state == TradeState.WIN)
    losses = sum(1 for t in trades if t.state == TradeState.LOSS)
    filled = wins + losses
    pnl = sum(t.pnl for t in trades)
    wr = (wins / filled * 100) if filled > 0 else 0
    
    # Check Qualification
    passed = False
    full_wr = 0.0
    full_trades = 0
    full_pnl = 0.0
    
    if filled >= MIN_SPRINT_TRADES and wr >= TARGET_WR:
        passed = True
        # RUN FULL BACKTEST
        engine_full = GoldenProtocolBacktest(bt_config)
        res_full = engine_full.run(es_data, nq_data)
        
        full_trades_list = [t for t in res_full.trades if t.asset == cfg['asset']]
        f_wins = sum(1 for t in full_trades_list if t.state == TradeState.WIN)
        f_losses = sum(1 for t in full_trades_list if t.state == TradeState.LOSS)
        full_filled = f_wins + f_losses
        full_pnl = sum(t.pnl for t in full_trades_list)
        full_wr = (f_wins / full_filled * 100) if full_filled > 0 else 0
        full_trades = full_filled

    return TestResult(
        config=cfg,
        sprint_wr=wr,
        sprint_trades=filled,
        sprint_pnl=pnl,
        passed_sprint=passed,
        full_wr=full_wr,
        full_trades=full_trades,
        full_pnl=full_pnl
    )

def generate_configs():
    keys, values = zip(*PARAMS.items())
    for v in product(*values):
        yield dict(zip(keys, v))

def main():
    print(f"Loading data from {DBN_PATH}...")
    # Load FULL data once
    es_data, nq_data = load_and_prepare_data(DBN_PATH, timeframe_minutes=2)
    
    # Determine Sprint Date
    end_date = es_data.index.max()
    sprint_start = end_date - timedelta(weeks=SPRINT_WEEKS)
    print(f"Sprint Period: {sprint_start} to {end_date}")
    
    # Prepare Jobs
    configs = list(generate_configs())
    print(f"Generated {len(configs)} configurations to test.")
    
    jobs = []
    for cfg in configs:
        jobs.append((cfg, es_data, nq_data, sprint_start))
        
    print(f"Starting execution on {mp.cpu_count()} cores...")
    
    start_time = time.time()
    
    # Multiprocessing Pool
    with mp.Pool(processes=mp.cpu_count()) as pool:
        # returns List[TestResult]
        results = pool.map(run_single_backtest, jobs)
        
    elapsed = time.time() - start_time
    print(f"Optimization complete in {elapsed:.1f}s")
    
    # --- ANALYSIS ---
    passed = [r for r in results if r.passed_sprint]
    print(f"\n{len(passed)} configurations passed Sprint qualification (> {TARGET_WR}% WR).")
    
    if not passed:
        print("No candidates met the Sprint criteria. Consider relaxing filters.")
        return

    # Sort by Full PnL
    passed.sort(key=lambda x: x.full_pnl, reverse=True)
    
    # Save to CSV
    data = []
    for r in passed:
        row = r.config.copy()
        row['sprint_wr'] = r.sprint_wr
        row['sprint_pnl'] = r.sprint_pnl
        row['full_wr'] = r.full_wr
        row['full_pnl'] = r.full_pnl
        row['full_trades'] = r.full_trades
        data.append(row)
        
    df = pd.DataFrame(data)
    df.to_csv('engineering_results_v6.csv', index=False)
    print("Results saved to engineering_results_v6.csv")
    
    print("\n--- TOP 3 CANDIDATES ---")
    print(df.head(3).to_string())

if __name__ == "__main__":
    mp.freeze_support()
    main()
