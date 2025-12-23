
import modal
from modal import App, Image, Volume
import sys
import os
import itertools
from dataclasses import dataclass
import pandas as pd

# --- CONFIGURATION ---
APP_NAME = "golden-protocol-massive"
VOLUME_NAME = "trading-data-vol"
DBN_FILENAME = "trades_es_nq_2025-09-21_2025-12-20.dbn"
LOCAL_DBN_PATH = f"data/databento_trades/{DBN_FILENAME}"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/{DBN_FILENAME}"

# --- IMAGE DEFINITION ---
image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    # Add Code (Current Dir) - strict ignore list
    .add_local_dir(
        ".",
        remote_path="/root/app",
        ignore=[
            ".git", ".venv", "__pycache__", "data", "tradingview", "output",
            "*.csv", "*.txt", "*.log", "*.png"
        ]
    )
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

# --- WORKER FUNCTION ---
@app.function(
    image=image, 
    volumes={REMOTE_DATA_DIR: volume}, 
    timeout=3600, 
    cpu=1.0,
    # concurrency_limit=100 # Uncomment to limit cost if needed
)
def run_backtest_chunk(configs):
    """
    Runs a list of configurations in one container.
    Profiling: Loading data takes time, so we process a 'chunk' of configs per container
    to amortize the load cost.
    """
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    # 1. Load Data (Cached in memory for this container)
    if not hasattr(run_backtest_chunk, "data_cache"):
        print(f"Loading data from {REMOTE_DBN_PATH}...")
        if not os.path.exists(REMOTE_DBN_PATH):
            raise FileNotFoundError(f"Data file not found at {REMOTE_DBN_PATH}. Did you run the upload seed?")
            
        # We need to load ALL timeframes used in configs?
        # For efficiency, let's assume this chunk is all for SAME timeframe.
        # But to be safe, we load the timeframe requested by the first config (and hope they are grouped).
        tf = configs[0]['timeframe_minutes']
        es, nq = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=tf)
        run_backtest_chunk.data_cache = (tf, es, nq)
    
    cached_tf, es_data, nq_data = run_backtest_chunk.data_cache
    
    # Check if we need to reload for a different timeframe (rare if grouped correctly)
    target_tf = configs[0]['timeframe_minutes']
    if cached_tf != target_tf:
        print(f"Switching timeframe {cached_tf} -> {target_tf}")
        es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=target_tf)
        run_backtest_chunk.data_cache = (target_tf, es_data, nq_data)
        
    results = []
    
    for cfg_dict in configs:
        bt_config = BacktestConfig(**cfg_dict)
        engine = GoldenProtocolBacktest(bt_config)
        res = engine.run(es_data, nq_data)
        
        # EXTRACT METRICS
        for asset in ["ES", "NQ"]:
            for direction in [TradeDirection.LONG, TradeDirection.SHORT]:
                dir_str = "LONG" if direction == TradeDirection.LONG else "SHORT"
                
                trades = [t for t in res.trades if t.asset == asset and t.sweep_direction == direction]
                if not trades:
                    continue
                    
                wins = sum(1 for t in trades if t.state == TradeState.WIN)
                total = len(trades)
                pnl = sum(t.pnl for t in trades)
                wr = (wins / total * 100)
                
                # Filter for High Quality immediately to save bandwidth
                if total < 20 or wr < 55: # Min criteria to even care
                    continue
                
                results.append({
                    "config": cfg_dict,
                    "asset": asset,
                    "direction": dir_str,
                    "wr": wr,
                    "trades": total,
                    "pnl": pnl
                })
    return results

# --- LOCAL ENTRYPOINT ---
@app.local_entrypoint()
def main(action: str = "optimize"):
    if action == "seed":
        print("Seeding Volume (Manual Step Required)...")
        print(f"Run: modal volume put {VOLUME_NAME} {LOCAL_DBN_PATH} {DBN_FILENAME}")
        return

    print("Generating Configurations...")
    
    # --- MASSSIVE GRID SEARCH SPACE (Expanded per User Request & Original Protocol) ---
    timeframes = [1, 2, 3, 5, 15] # added 1m and 15m
    fibs = [0.5, 0.55, 0.618, 0.65, 0.786] # expanded fibs
    fib_stops = [1.0, 0.893] # Standard vs Original Deep Stop
    expiries = [3, 5, 7, 10, 15] # expanded timing
    wicks = [0.0, 0.25, 0.35, 0.5] # testing wick rejection
    atrs = [0.0, 4.0, 6.0, 8.0] # volatility
    rvols = [0.0, 1.2, 2.0] # volume spikes
    macros = [False, True] # trend alignment
    breakevens = [0.0, 0.5] # Test Fixed vs BE
    
    configs = []
    # Cartesian Product
    for tf, fib, fstop, exp, wick, atr, rvol, mac, be in itertools.product(timeframes, fibs, fib_stops, expiries, wicks, atrs, rvols, macros, breakevens):
        cfg = {
            "timeframe_minutes": tf,
            "fib_entry": fib,
            "fib_stop": fstop, 
            "fib_target": 0.0, # Testing High/Low target (Classic 1:1 if entry 0.5, stop 1.0)
            "entry_expiry_candles": exp,
            "min_wick_ratio": wick,
            "max_atr": atr,
            "min_rvol": rvol,
            "breakeven_trigger_r": be, 
            "use_macro_filter": mac,
            "require_bb_expansion": False,
            "entry_mode": "FIB"
        }
        configs.append(cfg)
        
    print(f"Total Configurations: {len(configs)}")
    
    CHUNK_SIZE = 50 
    chunks = [configs[i:i + CHUNK_SIZE] for i in range(0, len(configs), CHUNK_SIZE)]
    print(f"Split into {len(chunks)} chunks.")
    
    print("🚀 DISPATCHING TO CLOUD (Phase 2: Expanded Grid + Original Specs)...")
    
    output_file = "cloud_optimization_final.csv"
    # Clear file if exists or handle resume? For now, simple overwrite start.
    if os.path.exists(output_file):
        os.remove(output_file)
        
    total_chunks = len(chunks)
    total_saved = 0
    
    # Progress bar & Incremental Save
    try:
        for i, results in enumerate(run_backtest_chunk.map(chunks)):
            if not results:
                continue
                
            df_chunk = pd.DataFrame(results)
            # Append to CSV
            # If first chunk (i=0 may not be first returned), check file existence
            header = not os.path.exists(output_file)
            df_chunk.to_csv(output_file, mode='a', header=header, index=False)
            
            total_saved += len(results)
            print(f"[{i+1}/{total_chunks}] Saved {len(results)} results (Total: {total_saved})")
            
    except Exception as e:
        print(f"\n❌ RUN INTERRUPTED: {e}")
        print("✅ Partial results saved to cloud_optimization_final.csv")
        
    print("\nRun Complete. Analyzing Results...")
    # Analyze logic is separate now
    if os.path.exists(output_file):
        final_df = pd.read_csv(output_file)
        print(final_df.sort_values("wr", ascending=False).head(10))
    else:
        print("No results generated.")
