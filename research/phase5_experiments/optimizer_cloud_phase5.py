
import modal
from modal import App, Image, Volume
import sys
import os
import itertools
from dataclasses import dataclass
import pandas as pd

# --- CONFIGURATION ---
APP_NAME = "golden-protocol-phase5"
VOLUME_NAME = "trading-data-vol"
DBN_FILENAME = "trades_es_nq_2025-09-21_2025-12-20.dbn"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/{DBN_FILENAME}"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt"]
    )
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=3600, cpu=1.0)
def run_backtest_chunk(configs):
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    
    # Load Data (Memoized)
    if not hasattr(run_backtest_chunk, "data_cache"):
        print(f"Loading data from {REMOTE_DBN_PATH}...")
        tf = configs[0]['timeframe_minutes']
        es, nq = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=tf)
        run_backtest_chunk.data_cache = (tf, es, nq)
    
    cached_tf, es_data, nq_data = run_backtest_chunk.data_cache
    target_tf = configs[0]['timeframe_minutes']
    if cached_tf != target_tf:
        es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=target_tf)
        run_backtest_chunk.data_cache = (target_tf, es_data, nq_data)
        
    results = []
    
    for cfg_dict in configs:
        bt_config = BacktestConfig(**cfg_dict)
        engine = GoldenProtocolBacktest(bt_config)
        res = engine.run(es_data, nq_data)
        
        for asset in ["ES", "NQ"]:
            for direction in [TradeDirection.LONG, TradeDirection.SHORT]:
                dir_str = "LONG" if direction == TradeDirection.LONG else "SHORT"
                trades = [t for t in res.trades if t.asset == asset and t.sweep_direction == direction]
                
                if not trades: continue
                    
                wins = sum(1 for t in trades if t.state == TradeState.WIN)
                total = len(trades)
                pnl = sum(t.pnl for t in trades)
                wr = (wins / total * 100)
                
                results.append({
                    "config": cfg_dict,
                    "asset": asset,
                    "direction": dir_str,
                    "wr": wr,
                    "trades": total,
                    "pnl": pnl,
                    "entry_mode": bt_config.entry_mode # Key Metric
                })
    return results

@app.local_entrypoint()
def main():
    print("🚀 PHASE 5: THE BREAKTHROUGH (Aggressive vs Defender)...")
    
    modes = ["FIB", "SWEEP_CLOSE"] # Control vs Experiment
    
    # Use only the Best Timeframes from Phase 3/4 to save compute
    # ES Short: 2m. NQ Short: 5m. NQ Long: 5m. ES Long: 5m.
    # Just iterate 2m and 5m.
    timeframes = [2, 5] 
    
    # Standard God Mode Params
    fibs = [0.5]
    stops = [1.0]
    expiries = [10, 15] 
    tfilt = [1, 9, 19] # Use the new Smart Filter for Fairness
    
    configs = []
    
    for mode, tf, exp in itertools.product(modes, timeframes, expiries):
        # We assume standard fib rules (even though SWEEP_CLOSE ignores fib entry, it needs object)
        cfg = {
            "timeframe_minutes": tf,
            "fib_entry": 0.5,
            "fib_stop": 1.0, 
            "fib_target": 0.0,
            "entry_expiry_candles": exp,
            "min_wick_ratio": 0.25, # Base filter
            "max_atr": 0.0,
            "use_macro_filter": True,
            "exclude_hours": tfilt,
            "entry_mode": mode,
            "use_trailing_fib": True
        }
        configs.append(cfg)
        
    print(f"Total Configurations: {len(configs)}")
    CHUNK_SIZE = 10
    chunks = [configs[i:i + CHUNK_SIZE] for i in range(0, len(configs), CHUNK_SIZE)]
    
    output_file = "cloud_optimization_phase5.csv"
    if os.path.exists(output_file): os.remove(output_file)
    
    for i, results in enumerate(run_backtest_chunk.map(chunks)):
        if results:
            pd.DataFrame(results).to_csv(output_file, mode='a', header=not os.path.exists(output_file), index=False)
            print(f"Saved chunk {i+1}/{len(chunks)}")

    print("Analyzing...")
    df = pd.read_csv(output_file)
    print(df.groupby(['asset', 'direction', 'entry_mode']).agg({'pnl': 'mean', 'wr': 'mean', 'trades': 'mean'}))
