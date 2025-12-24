"""Verify Ground Truth - Debugging specific dates logic"""
import modal
from modal import App, Image, Volume
import sys

APP_NAME = "verify-ground-truth"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(".", remote_path="/root/app", ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt", "*.xlsx"])
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=600, cpu=1.0)
def run_verification():
    sys.path.append("/root/app")
    from backtest_engine import GoldenProtocolBacktest, BacktestConfig, TradeState, TradeDirection
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    output = []
    
    def log(msg):
        print(msg)
        output.append(str(msg))
    
    # Load data
    log("\n" + "="*80)
    log("VERIFYING FIXED LOGIC - DEC 18 TRADE (Shifted Macro)")
    log("="*80)
    
    # DEBUG: Check if fix is present in loaded module
    import inspect
    src = inspect.getsource(load_and_prepare_data)
    if "shift(1)" in src:
        log("SUCCESS: 'shift(1)' found in load_and_prepare_data source code!")
    else:
        log("FAILURE: 'shift(1)' NOT found in load_and_prepare_data source code!")
        log(src[-500:]) # Log last 500 chars 
    
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=2)
    
    # Filter to Dec 18
    es_day = es_data['2025-12-18':'2025-12-18']
    nq_day = nq_data['2025-12-18':'2025-12-18']
    
    log(f"Data points: {len(es_day)}")
    
    # Show macro trend around 13:00
    log("\n--- Macro Trend Check (12:40 - 13:20) ---")
    window = es_day.between_time('12:40', '13:20')
    for idx, row in window.iterrows():
        log(f"{idx} | Rate: {row['close']:.2f} | Macro: {row['macro_trend']} | ATR: {row['atr_14']:.2f} | WickUp: {row['wick_ratio_up']:.2f}")
    
    # Run backtest for this day with debug prints
    # We need to subclass to inject debug prints without modifying the engine file
    class DebugBacktest(GoldenProtocolBacktest):
        def _process_ppi_phase(self, trade, timestamp, candle):
            # Debug PPI detection
            if "12:46" in str(timestamp):
                print(f"DEBUG {timestamp}: Checking PPI...")
            super()._process_ppi_phase(trade, timestamp, candle)
            
        def _process_sweep_phase(self, trade, timestamp, candle):
            # Debug Sweep detection
            if "12:46" in str(timestamp) or "12:58" in str(timestamp):
                print(f"DEBUG {timestamp}: Checking SWEEP...")
                print(f"  Macro: {candle.get('macro_trend')}")
                print(f"  WickUp: {candle.get('wick_ratio_up')}")
            super()._process_sweep_phase(trade, timestamp, candle)
            
    config = BacktestConfig(
        timeframe_minutes=2,
        entry_expiry_candles=15,
        fib_entry=0.5, 
        fib_stop=1.0, 
        fib_target=0.0,
        min_wick_ratio=0.25,
        max_atr=6.0,
        use_macro_filter=True,
        use_trailing_fib=True
    )
    
    log("\n--- Running Backtest ---")
    engine = DebugBacktest(config)
    res = engine.run(es_day, nq_day)
    
    log(f"\nTrades found: {len(res.trades)}")
    for t in res.trades:
        log(f"Trade: {t.fill_time} | {t.sweep_direction} | {t.state}")
        
    return output

@app.local_entrypoint()
def main():
    output = run_verification.remote()
    
    with open("research/verify_ground_truth_result.txt", "w") as f:
        f.write("\n".join(output))
    
    print("\n".join(output))
