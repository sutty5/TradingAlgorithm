
import modal
from modal import App, Image
import pandas as pd
import numpy as np
from dataclasses import dataclass
import sys
import os

DBN_PATH = "data/databento_trades/trades_es_nq_2025-09-21_2025-12-20.dbn"

# Define the image with dependencies AND files
image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    # Add Code (Current Dir)
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=[
            ".git", ".venv", "__pycache__", "data", "tradingview", "output",
            "*.csv", "*.txt", "*.log", "*.png"
        ]
    )
    # Add Data File
    .add_local_file(
        DBN_PATH,
        remote_path=f"/root/app/{DBN_PATH}"
    )
)

app = App("golden-protocol-cloud")

@app.function(image=image, timeout=3600, cpu=1.0)
def run_backtest_remote(config_dict):
    # Import inside function because it runs in the cloud container
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    # Reconstruct Config
    bt_config = BacktestConfig(**config_dict)
    
    # Load Data (In the cloud, we load from the mount)
    # Optimization: Loading 900MB every time is slow. 
    # For now, we load it. In v2, we pass the dataframe or use shared memory.
    # Actually, loading inside the function means loading 900MB per function call? NO.
    # We should cache the data.
    
    # BETTER: Separate Data Loading
    # But for "Grid Search", the overhead of loading might kill us if we do it per config.
    # STRATEGY: We will map `run_chunk` where one chunk tests MULTIPLE configs.
    
    # Hack for v1: Load data once per container using global variable
    if not hasattr(run_backtest_remote, "data_cache"):
        print("Loading Data on Container...")
        es, nq = load_and_prepare_data(f"/root/app/{DBN_PATH}", timeframe_minutes=2)
        run_backtest_remote.data_cache = (es, nq)
    
    es_data, nq_data = run_backtest_remote.data_cache
    
    # Run Engine
    engine = GoldenProtocolBacktest(bt_config)
    result = engine.run(es_data, nq_data)
    
    # Simple Stats
    trades = [t for t in result.trades if t.asset == "NQ" and t.sweep_direction == TradeDirection.SHORT] # Hardcoded NQ Short focus for now
    
    wins = sum(1 for t in trades if t.state == TradeState.WIN)
    total = len(trades)
    pnl = sum(t.pnl for t in trades)
    wr = (wins / total * 100) if total > 0 else 0
    
    return {
        "config": config_dict,
        "wr": wr,
        "trades": total,
        "pnl": pnl
    }

@app.local_entrypoint()
def main():
    print("🚀 Preparing Cloud Optimization...")
    
    # Define Parameter Grid (Small Test)
    configs = []
    
    # Test varying Expiry from 3 to 10
    for expiry in range(3, 11):
        for fib in [0.5, 0.55, 0.618]:
            cfg = {
                "timeframe_minutes": 2,
                "fib_entry": fib,
                "fib_stop": 1.0,
                "fib_target": 0.0,
                "entry_expiry_candles": expiry,
                "min_wick_ratio": 0.0,
                "max_atr": 0.0,
                "min_rvol": 0.0,
                "breakeven_trigger_r": 0.0,
                "use_macro_filter": False,
                "require_bb_expansion": False,
                "entry_mode": "FIB"
            }
            configs.append(cfg)
            
    print(f"Deploying {len(configs)} configurations to Modal...")
    
    results = []
    # map runs in parallel
    for res in run_backtest_remote.map(configs):
        results.append(res)
        print(f"Got result: WR={res['wr']:.1f}% Trades={res['trades']}")
        
    # Find best
    best = max(results, key=lambda x: x['pnl'])
    print("\n🏆 BEST CLOUD RESULT 🏆")
    print(best)

