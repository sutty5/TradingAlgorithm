"""
v5.0 Einstein Verification Script (Parallel)

Uses multiprocessing to max out CPU cores by running NQ and ES verifications independently.
Each process loads the data separately (leveraging OS file cache) to parallelize the costly DBN parsing.
"""
import pandas as pd
import numpy as np
import time
from multiprocessing import Pool, cpu_count
from data_loader import load_and_prepare_data
from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection

def get_config_for_setup(setup_name):
    """Factory for configs to avoid pickling complex objects"""
    if setup_name == "NQ_EINSTEIN":
        # NQ 2m Short Only
        return {
            "timeframe": 2,
            "fib_entry": 0.618,
            "use_trend_filter": False,
            "breakeven_trigger_r": 0.0,
            "asset_filter": "NQ",
            "direction_filter": "SHORT",
            "blocked_hours": [8, 9, 18, 19]
        }
    elif setup_name == "ES_EINSTEIN":
        # ES 5m Both
        return {
            "timeframe": 5,
            "fib_entry": 0.5,
            "use_trend_filter": False,
            "breakeven_trigger_r": 0.5,
            "asset_filter": "ES",
            "direction_filter": "BOTH",
            "blocked_hours": []
        }
    return None

def run_single_verification(setup_name):
    """
    Worker function to run a full verification pipeline for one setup.
    """
    print(f"[{setup_name}] Starting process...")
    start_time = time.time()
    
    cfg = get_config_for_setup(setup_name)
    dbn_path = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"
    
    # 1. Load Data (CPU Intensive Parsing)
    print(f"[{setup_name}] Loading & Aggregating Data ({cfg['timeframe']}m)...")
    try:
        # load_and_prepare_data handles loading, filtering, aggregating for BOTH assets
        # We need both because the strategy relies on PPI (divergence between ES and NQ)
        es_data, nq_data = load_and_prepare_data(dbn_path, cfg['timeframe'])
    except Exception as e:
        return f"[{setup_name}] Error: {e}"
        
    print(f"[{setup_name}] Data Ready. Rows: {len(es_data)}")

    # 2. Run Backtest
    print(f"[{setup_name}] Running Backtest...")
    bt_config = BacktestConfig(
        fib_entry=cfg['fib_entry'],
        use_trend_filter=cfg['use_trend_filter'],
        breakeven_trigger_r=cfg['breakeven_trigger_r']
    )
    engine = GoldenProtocolBacktest(bt_config)
    res = engine.run(es_data, nq_data)
    
    # 3. Filter Results
    final_trades = []
    target_asset = cfg['asset_filter']
    target_dir = cfg['direction_filter']
    blocked = cfg['blocked_hours']
    
    for t in res.trades:
        if t.asset != target_asset:
            continue
            
        # Direction Logic
        if target_dir == "SHORT" and t.sweep_direction != TradeDirection.SHORT:
            continue
        if target_dir == "LONG" and t.sweep_direction != TradeDirection.LONG:
            continue
            
        # Time Logic
        if t.ppi_time.hour in blocked:
            continue
            
        final_trades.append(t)
    
    # 4. Calculate Stats
    stats = calculate_stats(setup_name, final_trades)
    duration = time.time() - start_time
    print(f"[{setup_name}] Finished in {duration:.1f}s")
    
    return stats

def calculate_stats(name, trades):
    if not trades:
        return {
            "name": name, 
            "total": 0, 
            "wr": 0, 
            "pnl": 0, 
            "pf": 0, 
            "max_dd": 0,
            "details": "No trades found."
        }
        
    wins = [t for t in trades if t.state == TradeState.WIN]
    losses = [t for t in trades if t.state == TradeState.LOSS]
    
    # Scratch analysis logic (same as original)
    scratch_trades = [t for t in trades if abs(t.pnl) < 1.0 and t.state in (TradeState.WIN, TradeState.LOSS)]
    real_wins = [t for t in wins if t not in scratch_trades]
    real_losses = [t for t in losses if t not in scratch_trades]
    
    total = len(trades)
    win_count = len(real_wins)
    loss_count = len(real_losses)
    effective_trades = win_count + loss_count
    
    wr = (win_count / effective_trades * 100) if effective_trades > 0 else 0
    total_pnl = sum(t.pnl for t in trades)
    
    # PF
    gross_win = sum(t.pnl for t in real_wins)
    gross_loss = abs(sum(t.pnl for t in real_losses))
    pf = (gross_win / gross_loss) if gross_loss > 0 else 999.0
    
    return {
        "name": name,
        "total": total,
        "wins": win_count,
        "losses": loss_count,
        "scratches": len(scratch_trades),
        "wr": wr,
        "pnl": total_pnl,
        "pf": pf,
        "trades": trades # Return actual trades for combining later if needed? 
                         # Careful, passing objects back might be slow, but list of ~50 is fine.
    }

def print_result(stats):
    print(f"\n=== {stats['name']} STATISTICS ===")
    print(f"Total Trades:      {stats['total']}")
    print(f"  Wins:            {stats['wins']}")
    print(f"  Losses:          {stats['losses']}")
    print(f"  Scratches:       {stats['scratches']}")
    print(f"Win Rate (adj):    {stats['wr']:.2f}%")
    print(f"Net PnL:           ${stats['pnl']:,.2f}")
    print(f"Profit Factor:     {stats['pf']:.2f}")

if __name__ == "__main__":
    # Windows support for multiprocessing
    tasks = ["NQ_EINSTEIN", "ES_EINSTEIN"]
    
    print(f"Launching {len(tasks)} parallel verification tasks...")
    print("Each task will load data independently to maximize CPU usage for parsing.")
    
    with Pool(processes=2) as pool:
        results = pool.map(run_single_verification, tasks)
        
    print("\n" + "="*60)
    print("FINAL PARALLEL VERIFICATION RESULTS")
    print("="*60)
    
    total_pnl = 0
    all_trades_count = 0
    
    for res in results:
        if isinstance(res, str): # Error message
            print(res)
        else:
            print_result(res)
            total_pnl += res['pnl']
            all_trades_count += res['total']
            
    print("\n" + "-"*60)
    print(f"COMBINED PORTFOLIO PnL: ${total_pnl:,.2f}")
    print(f"TOTAL TRADES:           {all_trades_count}")
    print("-" * 60)
