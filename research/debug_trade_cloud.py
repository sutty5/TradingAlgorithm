"""Debug: Check what Python sees at specific TV trade timestamps"""
import modal
from modal import App, Image, Volume
import sys
from datetime import datetime

APP_NAME = "debug-trade"
VOLUME_NAME = "trading-data-vol"
REMOTE_DATA_DIR = "/root/data"
REMOTE_DBN_PATH = f"{REMOTE_DATA_DIR}/trades_es_nq_2025-09-21_2025-12-20.dbn"

image = (
    Image.debian_slim()
    .pip_install("pandas", "numpy", "databento")
    .add_local_dir(".", remote_path="/root/app", ignore=[".git", ".venv", "__pycache__", "data", "tradingview", "output", "*.csv", "*.txt"])
)

app = App(APP_NAME)
volume = Volume.from_name(VOLUME_NAME, create_if_missing=True)

@app.function(image=image, volumes={REMOTE_DATA_DIR: volume}, timeout=600, cpu=1.0)
def debug_trade():
    sys.path.append("/root/app")
    from data_loader import load_and_prepare_data
    import pandas as pd
    
    print("Loading 5m data...")
    es_data, nq_data = load_and_prepare_data(REMOTE_DBN_PATH, timeframe_minutes=5)
    
    # TradingView trade timestamps to investigate
    tv_trades = [
        "2025-11-28 13:40:00",
        "2025-12-01 19:00:00",
        "2025-12-03 15:10:00",
        "2025-12-05 08:25:00",
    ]
    
    print("\n" + "="*80)
    print("DEBUGGING: What Python sees at TradingView trade timestamps")
    print("="*80)
    
    results = []
    
    for ts_str in tv_trades:
        ts = pd.Timestamp(ts_str, tz='UTC')
        
        print(f"\n{'='*60}")
        print(f"TV TRADE: {ts_str}")
        print(f"{'='*60}")
        
        # Look at the 12 bars before this timestamp
        start_ts = ts - pd.Timedelta(minutes=60)  # 12 bars * 5 min = 60 min
        end_ts = ts + pd.Timedelta(minutes=5)
        
        es_window = es_data[(es_data.index >= start_ts) & (es_data.index <= end_ts)]
        nq_window = nq_data[(nq_data.index >= start_ts) & (nq_data.index <= end_ts)]
        
        print(f"\nES Candles ({len(es_window)} bars):")
        for idx, row in es_window.iterrows():
            direction = "GREEN" if row['close'] > row['open'] else "RED"
            print(f"  {idx} | O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f} | {direction}")
        
        print(f"\nNQ Candles ({len(nq_window)} bars):")
        for idx, row in nq_window.iterrows():
            direction = "GREEN" if row['close'] > row['open'] else "RED"
            print(f"  {idx} | O:{row['open']:.2f} H:{row['high']:.2f} L:{row['low']:.2f} C:{row['close']:.2f} | {direction}")
        
        # Check for PPI (divergence)
        print(f"\nDIVERGENCE CHECK:")
        for i in range(len(es_window)):
            es_row = es_window.iloc[i]
            es_idx = es_window.index[i]
            
            # Find matching NQ bar
            if es_idx in nq_window.index:
                nq_row = nq_window.loc[es_idx]
                
                es_dir = 1 if es_row['close'] > es_row['open'] else -1
                nq_dir = 1 if nq_row['close'] > nq_row['open'] else -1
                
                es_body = abs(es_row['close'] - es_row['open'])
                nq_body = abs(nq_row['close'] - nq_row['open'])
                
                # Doji check (body > 2 ticks = 0.5 for ES)
                es_doji = es_body <= 0.5
                nq_doji = nq_body <= 1.0  # NQ has larger tick
                
                is_divergence = es_dir != nq_dir and not es_doji and not nq_doji
                
                print(f"  {es_idx} | ES: {'GREEN' if es_dir > 0 else 'RED'} (doji:{es_doji}) | NQ: {'GREEN' if nq_dir > 0 else 'RED'} (doji:{nq_doji}) | DIVERGENCE: {is_divergence}")
                
                if is_divergence:
                    results.append({
                        "timestamp": str(es_idx),
                        "es_dir": "GREEN" if es_dir > 0 else "RED",
                        "nq_dir": "GREEN" if nq_dir > 0 else "RED",
                        "es_high": es_row['high'],
                        "es_low": es_row['low']
                    })
    
    return results

@app.local_entrypoint()
def main():
    results = debug_trade.remote()
    print(f"\nDivergences found: {len(results)}")
    for r in results:
        print(r)
    with open("debug_results.txt", "w") as f:
        for r in results:
            f.write(str(r) + "\n")
